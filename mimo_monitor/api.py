"""
Mimo Monitor - API 服务

核心逻辑：
1. watcher 监控 ~/.agent-state/ 目录（状态的主要来源）
2. 进程检测是回退方案（watcher 超时后启用）
3. 保留 /api/hook 端点（向后兼容，写入状态文件）
4. WebSocket 实时推送状态变化
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse

from .models import AgentInfo, AgentState
from .protocol import STATE_DIR, STALE_TIMEOUT, report
from .watcher import get_watcher
from .detectors import scan_tools
from .codex_monitor import start_codex_monitor, stop_codex_monitor, is_connected as codex_server_connected

logger = logging.getLogger("mimo")

STATIC_DIR = Path(__file__).parent / "static"

# 状态日志
_status_log: list[dict] = []
MAX_LOG = 100

# WebSocket 客户端
_ws_clients: set[WebSocket] = set()

# Hook 超时时间：超过这个时间没收到文件更新，回退到进程检测
FILE_TIMEOUT = 30.0


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

def get_merged_status() -> list[AgentInfo]:
    """合并文件状态和进程检测状态。"""
    watcher = get_watcher()
    file_states = watcher.get_all_states()
    now = time.time()

    # 进程检测缓存
    if not hasattr(get_merged_status, "_proc_cache"):
        get_merged_status._proc_cache = []
        get_merged_status._proc_cache_time = 0.0

    if now - get_merged_status._proc_cache_time > 2.0:
        get_merged_status._proc_cache = scan_tools()
        get_merged_status._proc_cache_time = now

    known_tools = {"claude-code", "opencode", "codex", "cursor"}
    result: list[AgentInfo] = []

    for tool_name in known_tools:
        file_data = file_states.get(tool_name)
        proc_info = next(
            (t for t in get_merged_status._proc_cache if t.name == tool_name), None
        )

        if file_data and (now - file_data.get("ts", 0) < FILE_TIMEOUT):
            # 文件状态有效
            info = AgentInfo(
                name=tool_name,
                state=AgentState(file_data.get("state", "idle")),
                detail=file_data.get("detail", ""),
                source="file",
                last_update=file_data.get("ts", 0),
            )
            if proc_info:
                info.pid = proc_info.pid
                info.cpu_percent = proc_info.cpu_percent
                info.memory_mb = proc_info.memory_mb
                info.uptime_seconds = proc_info.uptime_seconds
            result.append(info)
        elif proc_info:
            # codex: app-server 已连接时不回退到进程检测
            if tool_name == "codex" and codex_server_connected():
                result.append(AgentInfo(name=tool_name, state=AgentState.STOPPED))
            else:
                proc_info.source = "process"
                result.append(proc_info)
        else:
            result.append(AgentInfo(name=tool_name, state=AgentState.STOPPED))

    return result


# ============== Watcher 回调 ==============

def _on_state_change(tool: str, state: dict | None):
    """watcher 回调：状态变化时记录日志和广播。"""
    if state is None:
        return
    entry = {
        "event": "state_change",
        "tool": tool,
        "state": state.get("state", "unknown"),
        "detail": state.get("detail", ""),
        "timestamp": time.time(),
    }
    _status_log.append(entry)
    if len(_status_log) > MAX_LOG:
        _status_log.pop(0)

    # 广播（在事件循环中异步执行）
    try:
        loop = asyncio.get_running_loop()
        loop.create_task(_broadcast(entry))
    except RuntimeError:
        pass


# ============== Lifespan ==============

@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动 watcher
    watcher = get_watcher()
    watcher.on_change(_on_state_change)
    watcher_task = asyncio.create_task(watcher.start(), name="state-watcher")

    # 启动 transmitters
    from .transmitters import start_udp_broadcast, start_ble_service
    tx_tasks = [
        asyncio.create_task(start_udp_broadcast(port=9101), name="udp-broadcast"),
        asyncio.create_task(start_ble_service(), name="ble-service"),
    ]
    # 启动 codex app-server 监控
    codex_task = asyncio.create_task(start_codex_monitor(), name="codex-monitor")

    logger.info("Mimo Monitor started (state dir: %s)", STATE_DIR)
    yield

    watcher_task.cancel()
    codex_task.cancel()
    for t in tx_tasks:
        t.cancel()
    await stop_codex_monitor()
    for t in [watcher_task, codex_task] + tx_tasks:
        try:
            await t
        except asyncio.CancelledError:
            pass


app = FastAPI(title="Mimo Monitor", version="0.3.0", lifespan=lifespan)


# ============== API 端点 ==============

@app.get("/api/status", response_model=list[AgentInfo])
async def get_all_status():
    """获取所有工具状态"""
    return get_merged_status()


@app.get("/api/status/{tool_name}", response_model=AgentInfo)
async def get_tool_status(tool_name: str):
    """获取单个工具状态"""
    tools = get_merged_status()
    for t in tools:
        if t.name == tool_name:
            return t
    return AgentInfo(name=tool_name, state=AgentState.STOPPED)


@app.post("/api/hook")
async def post_hook(event: dict):
    """接收 Hook 事件（向后兼容）。写入状态文件。"""
    tool = event.get("tool", "unknown")
    hook_event = event.get("event", "")
    detail = event.get("detail", "")

    # 映射事件到状态
    state_map = {
        "PreToolUse": "working",
        "PostToolUse": "working",
        "Notification": "waiting",
        "Stop": "idle",
        "SubagentStop": "idle",
        "start": "working",
        "exit": "idle",
        "tool.execute.before": "working",
        "tool.execute.after": "working",
        "permission.ask": "waiting",
        "chat.message": "working",
    }
    state = state_map.get(hook_event, event.get("status", "working"))

    # 写入状态文件
    report(tool, state, f"[{hook_event}] {detail}")

    return {"ok": True, "state": state}


@app.post("/api/status")
async def post_status(update: dict):
    """接收外部状态更新（向后兼容）。写入状态文件。"""
    tool = update.get("tool", "unknown")
    state = update.get("state", update.get("status", "working"))
    detail = update.get("detail", "")
    report(tool, state, detail)
    return {"ok": True}


@app.get("/api/log")
async def get_log(limit: int = 20):
    """获取状态日志"""
    return _status_log[-limit:]


@app.get("/api/health")
async def health():
    """健康检查"""
    watcher = get_watcher()
    return {
        "status": "ok",
        "state_dir": str(STATE_DIR),
        "tools_tracked": len(watcher.get_all_states()),
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
