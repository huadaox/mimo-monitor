"""
Mimo Monitor - 数据模型

状态定义（4 个核心状态）：
- working:  工具正在执行（API 调用中、工具运行中）
- waiting:  等待用户（权限确认、等待输入）
- idle:     空闲（任务完成，等待新指令）
- stopped:  离线（进程不存在、超时无响应）
"""

from __future__ import annotations

import time
from enum import Enum
from pydantic import BaseModel, Field


class AgentState(str, Enum):
    """Agent 状态枚举"""
    WORKING = "working"
    WAITING = "waiting"
    IDLE = "idle"
    STOPPED = "stopped"


class AgentInfo(BaseModel):
    """Agent 状态信息"""
    name: str                                  # 工具名称 (claude-code, opencode, codex)
    state: AgentState = AgentState.STOPPED
    detail: str = ""                           # 状态详情
    source: str = "file"                       # 状态来源: "file" | "process"
    pid: int | None = None
    cpu_percent: float = 0.0
    memory_mb: float = 0.0
    uptime_seconds: float = 0.0
    last_update: float = 0.0                   # 最后一次状态更新时间
