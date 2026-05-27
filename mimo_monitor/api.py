from __future__ import annotations

import asyncio
import json
import time
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse

from .models import HookEvent, ToolInfo, ToolStatus, StatusUpdate
from .detectors import scan_tools

STATIC_DIR = Path(__file__).parent / "static"

# In-memory status log (last 100 updates)
_status_log: list[StatusUpdate] = []
MAX_LOG = 100

# Snapshot cache
_cache: list[ToolInfo] = []
_cache_time: float = 0.0

# WebSocket clients
_ws_clients: set[WebSocket] = set()

# Previous status for change detection
_prev_status: dict[str, ToolStatus] = {}

# Hook event log (last 100 events)
_hook_log: list[HookEvent] = []

# Hook-reported status per tool (tool_name -> (HookEvent, timestamp))
_hook_status: dict[str, tuple[HookEvent, float]] = {}

HOOK_TIMEOUT = 30.0  # seconds before falling back to psutil


async def _broadcast(msg: dict):
    dead: list[WebSocket] = []
    for ws in _ws_clients:
        try:
            await ws.send_json(msg)
        except Exception:
            dead.append(ws)
    for ws in dead:
        _ws_clients.discard(ws)


async def _poll_loop():
    global _cache, _cache_time, _prev_status
    while True:
        _cache = scan_tools()
        _cache_time = time.time()

        # Merge hook status: override psutil result if hook reported recently
        for tool in _cache:
            if tool.name in _hook_status:
                hook_event, hook_time = _hook_status[tool.name]
                if _cache_time - hook_time < HOOK_TIMEOUT:
                    tool.status = hook_event.status
                    tool.detail = hook_event.detail
                    tool.source = "hook"

        # Detect status changes and broadcast
        for tool in _cache:
            old = _prev_status.get(tool.name)
            if old != tool.status:
                _prev_status[tool.name] = tool.status
                await _broadcast({
                    "event": "status_change",
                    "tool": tool.name,
                    "status": tool.status.value,
                    "detail": tool.detail,
                    "timestamp": _cache_time,
                })

        await asyncio.sleep(2)


@asynccontextmanager
async def lifespan(app: FastAPI):
    task = asyncio.create_task(_poll_loop())
    yield
    task.cancel()


app = FastAPI(title="Mimo Monitor", version="0.1.0", lifespan=lifespan)


@app.get("/api/status", response_model=list[ToolInfo])
async def get_all_status():
    if not _cache:
        return scan_tools()
    return _cache


@app.get("/api/status/{tool_name}", response_model=ToolInfo)
async def get_tool_status(tool_name: str):
    tools = _cache if _cache else scan_tools()
    for t in tools:
        if t.name == tool_name:
            return t
    return ToolInfo(name=tool_name, status=ToolStatus.STOPPED)


@app.post("/api/status")
async def post_status(update: StatusUpdate):
    update.timestamp = time.time()
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
    return {"ok": True, "received": update}


@app.post("/api/hook")
async def post_hook(event: HookEvent):
    event.timestamp = time.time()
    _hook_log.append(event)
    if len(_hook_log) > MAX_LOG:
        _hook_log.pop(0)

    # Override status for this tool
    _hook_status[event.tool] = (event, event.timestamp)

    await _broadcast({
        "event": "hook_update",
        "tool": event.tool,
        "hook_event": event.event,
        "status": event.status.value,
        "detail": event.detail,
        "session_id": event.session_id,
        "timestamp": event.timestamp,
    })
    return {"ok": True, "received": event}


@app.get("/api/log", response_model=list[StatusUpdate])
async def get_log(limit: int = 20):
    return _status_log[-limit:]


@app.get("/api/hook/log", response_model=list[HookEvent])
async def get_hook_log(limit: int = 20):
    return _hook_log[-limit:]


@app.get("/api/health")
async def health():
    return {
        "status": "ok",
        "tools_tracked": len(_cache) if _cache else 0,
        "ws_clients": len(_ws_clients),
    }


@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    _ws_clients.add(ws)
    try:
        # Send current state immediately
        tools = _cache if _cache else scan_tools()
        await ws.send_json({
            "event": "init",
            "tools": [t.model_dump() for t in tools],
            "timestamp": time.time(),
        })
        # Keep alive, listen for pings
        while True:
            data = await ws.receive_text()
            if data == "ping":
                await ws.send_json({"event": "pong"})
    except WebSocketDisconnect:
        pass
    finally:
        _ws_clients.discard(ws)


@app.get("/")
async def dashboard():
    return FileResponse(STATIC_DIR / "dashboard.html")
