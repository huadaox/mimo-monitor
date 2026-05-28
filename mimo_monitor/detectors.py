"""
Mimo Monitor - 进程检测（简化版，不依赖 psutil）
"""

import subprocess
import time
from .models import ToolInfo, ToolStatus


def check_process(name: str, pattern: str) -> ToolInfo | None:
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
            return ToolInfo(
                name=name,
                status=ToolStatus.IDLE,  # 默认空闲，由 hook 更新实际状态
                pid=pid,
                source="process"
            )
    except Exception:
        pass
    return None


def scan_tools() -> list[ToolInfo]:
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
            result.append(ToolInfo(name=name, status=ToolStatus.STOPPED))
    
    return result
