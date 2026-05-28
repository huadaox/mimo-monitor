"""
Mimo Monitor - 状态模型

状态来源优先级：
1. Hook 上报（最准确，实时反映 agent 工作状态）
2. 进程检测（回退方案，当 hook 超时时使用）

状态定义：
- thinking: agent 正在思考（等待 LLM 响应/准备调用工具）
- running: agent 正在执行（工具执行中/输出生成中）
- waiting: agent 等待用户（需要权限确认/等待输入）
- idle: agent 空闲（任务完成，等待新指令）
- error: agent 出错
- stopped: agent 离线（进程不存在）
"""

from __future__ import annotations

import time
from enum import Enum
from pydantic import BaseModel, Field


class ToolStatus(str, Enum):
    """Agent 状态枚举"""
    THINKING = "thinking"   # 思考中：等待 LLM 响应，或准备调用工具
    RUNNING = "running"     # 运行中：工具执行中，或正在生成输出
    WAITING = "waiting"     # 等待中：需要用户确认权限，或等待用户输入
    IDLE = "idle"          # 空闲：任务完成，等待新指令
    ERROR = "error"        # 出错：执行出错
    STOPPED = "stopped"    # 离线：进程不存在


class ToolInfo(BaseModel):
    """工具状态信息"""
    name: str                              # 工具名称 (claude-code, opencode, codex)
    status: ToolStatus = ToolStatus.STOPPED
    detail: str = ""                       # 状态详情
    source: str = "process"                # 状态来源: "hook" | "process"
    pid: int | None = None                 # 进程 PID
    cpu_percent: float = 0.0
    memory_mb: float = 0.0
    uptime_seconds: float = 0.0
    last_hook_time: float = 0.0            # 最后一次 hook 上报时间
    last_hook_event: str = ""              # 最后一次 hook 事件类型


class HookEvent(BaseModel):
    """Hook 事件"""
    tool: str                              # 工具名称
    event: str                             # 事件类型 (PreToolUse, PostToolUse, Stop, etc.)
    status: ToolStatus | None = None       # 可选：手动指定状态（通常由 event 自动推导）
    detail: str = ""                       # 事件详情
    session_id: str = ""                   # 会话 ID
    timestamp: float = Field(default_factory=time.time)


class StatusUpdate(BaseModel):
    """外部状态更新"""
    tool: str
    status: ToolStatus
    detail: str = ""
    timestamp: float = Field(default_factory=time.time)


# Hook 事件 → 状态映射表
HOOK_STATUS_MAP = {
    # Claude Code hooks
    "PreToolUse": ToolStatus.THINKING,     # 准备调用工具 → 思考中
    "PostToolUse": ToolStatus.RUNNING,     # 工具执行完成 → 运行中（可能继续调用）
    "Notification": ToolStatus.WAITING,    # 通知用户 → 等待用户
    "Stop": ToolStatus.IDLE,              # 任务完成 → 空闲
    "SubagentStop": ToolStatus.IDLE,      # 子任务完成 → 空闲

    # OpenCode events
    "chat.message": ToolStatus.THINKING,   # 收到消息 → 思考中
    "tool.execute.before": ToolStatus.THINKING,  # 工具执行前 → 思考中
    "tool.execute.after": ToolStatus.RUNNING,    # 工具执行后 → 运行中
    "permission.ask": ToolStatus.WAITING,  # 请求权限 → 等待中

    # Codex events
    "start": ToolStatus.RUNNING,          # 开始执行 → 运行中
    "exit": ToolStatus.IDLE,              # 执行完成 → 空闲
}
