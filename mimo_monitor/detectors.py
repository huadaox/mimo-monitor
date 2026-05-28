"""
Mimo Monitor - 进程检测（回退方案）

当状态文件超时时，通过进程检测判断工具是否在运行。
"""

import subprocess
import time
from .models import AgentInfo, AgentState


def check_process(name: str, pattern: str) -> AgentInfo | None:
    """检查进程是否存在"""
    try:
        result = subprocess.run(
            ["pgrep", "-f", pattern],
            capture_output=True,
            text=True,
            timeout=2
        )
        if result.returncode == 0:
            pid = int(result.stdout.strip().split("\n")[0])
            return AgentInfo(
                name=name,
                state=AgentState.IDLE,
                pid=pid,
                source="process"
            )
    except Exception:
        pass
    return None


def scan_tools() -> list[AgentInfo]:
    """扫描所有工具进程"""
    tools = [
        ("claude-code", "claude"),
        ("opencode", "opencode"),
        ("codex", "codex"),
        ("cursor", "cursor"),
    ]

    result = []
    for name, pattern in tools:
        info = check_process(name, pattern)
        if info:
            result.append(info)
        else:
            result.append(AgentInfo(name=name, state=AgentState.STOPPED))

    return result
