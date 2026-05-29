"""
Mimo Monitor - Codex App-Server Monitor

管理 Codex app-server 守护进程，通过 WebSocket 连接监听 ThreadStatusChanged 通知，
聚合多线程状态后写入 ~/.agent-state/codex.json。

替代旧的 plugins/codex.sh wrapper 方案。

架构:
  mimo server → 启动 codex app-server (ws://127.0.0.1:9200)
  codex TUI   → codex --remote ws://127.0.0.1:9200
  monitor     → WebSocket 连接同一个 app-server
"""

from __future__ import annotations

import asyncio
import json
import logging
import shutil
import signal
import time
from pathlib import Path

from .protocol import report

logger = logging.getLogger("mimo.codex")

# app-server 配置
APP_SERVER_PORT = 9200
APP_SERVER_URL = f"ws://127.0.0.1:{APP_SERVER_PORT}"

# 重连参数
RECONNECT_INTERVAL = 2.0
CONNECTION_RETRY_INTERVAL = 5.0

# 状态优先级: 数字越大越紧急
STATE_PRIORITY = {
    "stopped": 0,
    "idle": 1,
    "working": 2,
    "waiting": 3,
}

# 全局状态
_connected = False
_app_server_process: asyncio.subprocess.Process | None = None


def is_connected() -> bool:
    """Codex app-server 是否已连接。"""
    return _connected


def get_app_server_url() -> str:
    """获取 app-server WebSocket URL，供 wrapper 脚本使用。"""
    return APP_SERVER_URL


def _find_codex_binary() -> str | None:
    """查找 codex 二进制。"""
    return shutil.which("codex")


def _map_status(status: dict) -> tuple[str, str]:
    """将 ThreadStatus 映射为 (mimo_state, detail)。

    ThreadStatus:
      - {"type": "notLoaded"}            → stopped
      - {"type": "idle"}                 → idle
      - {"type": "systemError"}          → stopped
      - {"type": "active", "activeFlags": [...]}  → 根据 flags 判断
    """
    status_type = status.get("type", "")

    if status_type == "active":
        flags = status.get("activeFlags", [])
        if "waitingOnApproval" in flags:
            return "waiting", "Waiting for approval"
        if "waitingOnUserInput" in flags:
            return "waiting", "Waiting for user input"
        return "working", "Processing"

    if status_type == "idle":
        return "idle", ""

    if status_type == "systemError":
        return "stopped", "System error"

    return "stopped", ""


def _aggregate_states(thread_states: dict[str, str]) -> tuple[str, str]:
    """聚合所有 thread 状态，取最紧急的那个。"""
    if not thread_states:
        return "idle", "No active sessions"

    best_state = "stopped"
    best_priority = -1

    for _tid, state in thread_states.items():
        priority = STATE_PRIORITY.get(state, 0)
        if priority > best_priority:
            best_priority = priority
            best_state = state

    if len(thread_states) > 1:
        parts = [f"{tid[:8]}:{s}" for tid, s in thread_states.items()]
        detail = ", ".join(parts)
    elif len(thread_states) == 1:
        tid = next(iter(thread_states))
        detail = f"thread {tid[:8]}"
    else:
        detail = ""

    return best_state, detail


async def _start_app_server() -> asyncio.subprocess.Process | None:
    """启动 codex app-server 作为守护进程。"""
    codex_bin = _find_codex_binary()
    if codex_bin is None:
        logger.error("codex binary not found")
        return None

    try:
        proc = await asyncio.create_subprocess_exec(
            codex_bin, "app-server",
            "--listen", f"ws://127.0.0.1:{APP_SERVER_PORT}",
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        logger.info("Started codex app-server (PID %d) on %s", proc.pid, APP_SERVER_URL)
        # 等待 server 就绪
        await asyncio.sleep(2.0)
        return proc
    except Exception as exc:
        logger.error("Failed to start app-server: %s", exc)
        return None


async def _ensure_app_server() -> asyncio.subprocess.Process | None:
    """确保 app-server 在运行，未运行则启动。"""
    global _app_server_process

    # 检查已有进程
    if _app_server_process is not None and _app_server_process.returncode is None:
        return _app_server_process

    # 尝试连接已有 server
    try:
        import websockets
        async with websockets.connect(APP_SERVER_URL, close_timeout=0.5) as ws:
            # server 已在运行
            logger.info("Codex app-server already running at %s", APP_SERVER_URL)
            return None  # 外部启动的，不需要管理
    except Exception:
        pass

    # 启动新的 server
    _app_server_process = await _start_app_server()
    return _app_server_process


class CodexMonitor:
    """通过 WebSocket 连接 Codex app-server，监听线程状态变化。"""

    def __init__(self):
        self._thread_states: dict[str, str] = {}
        self._ws = None
        self._request_id = 0

    async def start(self) -> None:
        """主循环：启动 server → 连接 → 监听 → 断开后重试。"""
        global _connected
        logger.info("Codex monitor started")

        while True:
            # 确保 app-server 在运行
            await _ensure_app_server()

            try:
                if await self._connect():
                    _connected = True
                    logger.info("Connected to codex app-server")
                    report("codex", "idle", "App-server connected")
                    await self._listen()
            except Exception as exc:
                logger.warning("Codex monitor error: %s", exc)
            finally:
                _connected = False
                self._thread_states.clear()
                report("codex", "stopped", "App-server disconnected")
                logger.info("Disconnected from codex app-server")

            await asyncio.sleep(CONNECTION_RETRY_INTERVAL)

    async def _connect(self) -> bool:
        """WebSocket 连接 + 握手。"""
        try:
            import websockets
            self._ws = await websockets.connect(
                APP_SERVER_URL,
                close_timeout=1.0,
            )
        except Exception as exc:
            logger.debug("WebSocket connection failed: %s", exc)
            return False

        if not await self._handshake():
            await self._close()
            return False

        return True

    async def _handshake(self) -> bool:
        """执行 JSON-RPC 握手。"""
        # 1. initialize
        self._request_id += 1
        init_request = {
            "id": self._request_id,
            "method": "initialize",
            "params": {
                "clientInfo": {
                    "name": "mimo-monitor",
                    "version": "0.1.0",
                },
                "capabilities": {},
            },
        }
        if not await self._send(init_request):
            return False

        response = await self._recv()
        if response is None:
            return False
        if "error" in response:
            logger.warning("Initialize rejected: %s", response["error"])
            return False
        logger.debug("Initialize OK")

        # 2. initialized notification
        if not await self._send({"method": "initialized"}):
            return False

        return True

    async def _listen(self) -> None:
        """监听通知循环，带心跳刷新。"""
        last_heartbeat = time.time()
        HEARTBEAT_INTERVAL = 10.0  # 每 10 秒刷新一次状态文件

        while True:
            # 带超时的 recv，用于心跳
            try:
                msg = await asyncio.wait_for(self._recv(), timeout=HEARTBEAT_INTERVAL)
            except asyncio.TimeoutError:
                msg = None

            if msg is not None:
                method = msg.get("method", "")
                if method == "thread/statusChanged":
                    self._handle_status_changed(msg.get("params", {}))
            else:
                # 超时：刷新状态文件（保持 ts 新鲜）
                agg_state, agg_detail = _aggregate_states(self._thread_states)
                report("codex", agg_state, agg_detail)

    def _handle_status_changed(self, params: dict) -> None:
        """处理 thread/statusChanged 通知。"""
        thread_id = params.get("threadId", params.get("thread_id", ""))
        status = params.get("status", {})

        if not thread_id:
            return

        mimo_state, detail = _map_status(status)
        self._thread_states[thread_id] = mimo_state

        agg_state, agg_detail = _aggregate_states(self._thread_states)
        report("codex", agg_state, agg_detail)

        logger.info(
            "Thread %s: %s -> aggregated: %s",
            thread_id[:8], mimo_state, agg_state,
        )

    async def _send(self, msg: dict) -> bool:
        """发送 JSON-RPC 消息。"""
        if self._ws is None:
            return False
        try:
            data = json.dumps(msg, separators=(",", ":"))
            await self._ws.send(data)
            return True
        except Exception as exc:
            logger.debug("Send failed: %s", exc)
            return False

    async def _recv(self) -> dict | None:
        """接收一条 JSON-RPC 消息。"""
        if self._ws is None:
            return None
        try:
            data = await asyncio.wait_for(self._ws.recv(), timeout=300)
            return json.loads(data)
        except Exception:
            return None

    async def _close(self) -> None:
        """关闭连接。"""
        if self._ws is not None:
            try:
                await self._ws.close()
            except Exception:
                pass
            self._ws = None


_monitor: CodexMonitor | None = None


async def start_codex_monitor() -> None:
    """启动 codex app-server 监控（供 api.py lifespan 调用）。"""
    global _monitor
    _monitor = CodexMonitor()
    await _monitor.start()


async def stop_codex_monitor() -> None:
    """停止 codex app-server 监控和守护进程。"""
    global _app_server_process
    if _app_server_process is not None and _app_server_process.returncode is None:
        logger.info("Stopping codex app-server (PID %d)", _app_server_process.pid)
        _app_server_process.terminate()
        try:
            await asyncio.wait_for(_app_server_process.wait(), timeout=5.0)
        except asyncio.TimeoutError:
            _app_server_process.kill()
        _app_server_process = None
