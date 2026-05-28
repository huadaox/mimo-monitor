"""
Mimo Monitor - API 服务

核心逻辑：
1. Hook 上报是状态的主要来源
2. 进程检测是回退方案（hook 超时 30 秒后启用）
3. WebSocket 实时推送状态变化
"""

from __future__ import annotations

import asyncio
import json
import time
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse

from .models import HookEvent, ToolInfo, ToolStatus, StatusUpdate, HOOK_STATUS_MAP
from .detectors import scan_tools

import logging
logger = logging.getLogger("mimo")

STATIC_DIR = Path(__file__).parent / "static"

# ============== 状态存储 ==============

# Hook 上报的状态: {tool_name: ToolInfo}
_hook_states: dict[str, ToolInfo] = {}

# 进程检测的缓存
_process_cache: list[ToolInfo] = []
_process_cache_time: float = 0.0

# 状态日志
_status_log: list[StatusUpdate] = []
MAX_LOG = 100

# WebSocket 客户端
_ws_clients: set[WebSocket] = set()

# Hook 超时时间（秒）：超过这个时间没收到 hook，回退到进程检测
HOOK_TIMEOUT = 30.0


# ============== WebSocket 广播 ==============

async def _broadcast(msg: dict):
    dead: list[WebSocket] = []
    for ws in _ws_clients:
        try:
            await ws.send_json(msg)
        except Exception:
            dead.append(ws)
    for ws in dead:
        _ws_clients.discard(ws)


# ============== 状态合并 ==============

def get_merged_status() -> list[ToolInfo]:
    """
    合并 hook 状态和进程检测状态。

    优先使用 hook 状态，如果 hook 超时则回退到进程检测。
    """
    global _process_cache, _process_cache_time
    now = time.time()

    # 定期更新进程缓存
    if now - _process_cache_time > 2.0:
        _process_cache = scan_tools()
        _process_cache_time = now

    # 已知工具列表
    known_tools = {"claude-code", "opencode", "codex", "cursor"}
    result: list[ToolInfo] = []

    for tool_name in known_tools:
        hook_info = _hook_states.get(tool_name)
        proc_info = next((t for t in _process_cache if t.name == tool_name), None)

        if hook_info and (now - hook_info.last_hook_time < HOOK_TIMEOUT):
            # Hook 状态有效，使用 hook 状态
            if proc_info:
                # 补充进程信息
                hook_info.pid = proc_info.pid
                hook_info.cpu_percent = proc_info.cpu_percent
                hook_info.memory_mb = proc_info.memory_mb
                hook_info.uptime_seconds = proc_info.uptime_seconds
            result.append(hook_info)
        elif proc_info:
            # Hook 超时或不存在，使用进程检测
            proc_info.source = "process"
            result.append(proc_info)
        else:
            # 都不存在，显示为 stopped
            result.append(ToolInfo(name=tool_name, status=ToolStatus.STOPPED))

    return result


# ============== Lifespan ==============

@asynccontextmanager
async def lifespan(app: FastAPI):
    poll_task = asyncio.create_task(_poll_loop())
    from .transmitters import start_udp_broadcast, start_ble_service
    tx_tasks = [
        asyncio.create_task(start_udp_broadcast(port=9101), name="udp-broadcast"),
        asyncio.create_task(start_ble_service(), name="ble-service"),
    ]
    logger.info("Mimo Monitor started")
    yield
    poll_task.cancel()
    for t in tx_tasks:
        t.cancel()
        try:
            await t
        except asyncio.CancelledError:
            pass


app = FastAPI(title="Mimo Monitor", version="0.2.0", lifespan=lifespan)


# ============== 后台轮询 ==============

async def _poll_loop():
    """定期检测状态变化并广播"""
    prev_states: dict[str, ToolStatus] = {}

    while True:
        tools = get_merged_status()

        for tool in tools:
            old = prev_states.get(tool.name)
            if old != tool.status:
                prev_states[tool.name] = tool.status
                await _broadcast({
                    "event": "status_change",
                    "tool": tool.name,
                    "status": tool.status.value,
                    "detail": tool.detail,
                    "source": tool.source,
                    "timestamp": time.time(),
                })

        await asyncio.sleep(2)


# ============== API 端点 ==============

@app.get("/api/status", response_model=list[ToolInfo])
async def get_all_status():
    """获取所有工具状态"""
    return get_merged_status()


@app.get("/api/status/{tool_name}", response_model=ToolInfo)
async def get_tool_status(tool_name: str):
    """获取单个工具状态"""
    tools = get_merged_status()
    for t in tools:
        if t.name == tool_name:
            return t
    return ToolInfo(name=tool_name, status=ToolStatus.STOPPED)


@app.post("/api/hook")
async def post_hook(event: HookEvent):
    """
    接收 Hook 事件，更新工具状态。

    这是状态的主要来源！
    """
    # 根据事件类型确定状态（优先用映射表，其次用手动指定，最后默认 running）
    status = HOOK_STATUS_MAP.get(event.event) or event.status or ToolStatus.RUNNING

    # 更新 hook 状态
    _hook_states[event.tool] = ToolInfo(
        name=event.tool,
        status=status,
        detail=event.detail,
        source="hook",
        last_hook_time=time.time(),
        last_hook_event=event.event,
    )

    # 记录日志
    update = StatusUpdate(
        tool=event.tool,
        status=status,
        detail=f"[{event.event}] {event.detail}",
        timestamp=time.time(),
    )
    _status_log.append(update)
    if len(_status_log) > MAX_LOG:
        _status_log.pop(0)

    # 广播状态变化
    await _broadcast({
        "event": "hook_update",
        "tool": event.tool,
        "hook_event": event.event,
        "status": status.value,
        "detail": event.detail,
        "session_id": event.session_id,
        "timestamp": time.time(),
    })

    logger.info(f"Hook: {event.tool} | {event.event} → {status.value} | {event.detail}")
    return {"ok": True, "status": status.value}


@app.post("/api/status")
async def post_status(update: StatusUpdate):
    """接收外部状态更新"""
    _status_log.append(update)
    if len(_status_log) > MAX_LOG:
        _status_log.pop(0)

    await _broadcast({
        "event": "external_update",
        "tool": update.tool,
        "status": update.status.value,
        "detail": update.detail,
        "timestamp": update.timestamp,
    })
    return {"ok": True}


@app.get("/api/log", response_model=list[StatusUpdate])
async def get_log(limit: int = 20):
    """获取状态日志"""
    return _status_log[-limit:]


@app.get("/api/health")
async def health():
    """健康检查"""
    return {
        "status": "ok",
        "tools_tracked": len(get_merged_status()),
        "hook_states": len(_hook_states),
        "ws_clients": len(_ws_clients),
    }


# ============== WebSocket ==============

@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    _ws_clients.add(ws)
    try:
        tools = get_merged_status()
        await ws.send_json({
            "event": "init",
            "tools": [t.model_dump() for t in tools],
            "timestamp": time.time(),
        })
        while True:
            data = await ws.receive_text()
            if data == "ping":
                await ws.send_json({"event": "pong"})
    except WebSocketDisconnect:
        pass
    finally:
        _ws_clients.discard(ws)


# ============== 静态文件 ==============

@app.get("/")
async def dashboard():
    return FileResponse(STATIC_DIR / "dashboard.html")
