from __future__ import annotations

from enum import Enum
from pydantic import BaseModel


class ToolStatus(str, Enum):
    IDLE = "idle"
    RUNNING = "running"
    THINKING = "thinking"
    WAITING = "waiting"
    ERROR = "error"
    STOPPED = "stopped"


class ToolInfo(BaseModel):
    name: str
    pid: int | None = None
    status: ToolStatus = ToolStatus.STOPPED
    cpu_percent: float = 0.0
    memory_mb: float = 0.0
    uptime_seconds: float = 0.0
    detail: str = ""
    source: str = "process"  # "hook" | "process"


class StatusUpdate(BaseModel):
    tool: str
    status: ToolStatus
    detail: str = ""
    timestamp: float = 0.0


class HookEvent(BaseModel):
    tool: str
    event: str
    status: ToolStatus
    detail: str = ""
    session_id: str = ""
    timestamp: float = 0.0
