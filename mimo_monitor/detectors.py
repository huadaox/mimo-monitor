from __future__ import annotations

import re
import time
from dataclasses import dataclass, field

import psutil

from .models import ToolInfo, ToolStatus


@dataclass
class ProcessPattern:
    name: str
    match_names: list[str] = field(default_factory=list)
    match_cmdline: list[str] = field(default_factory=list)


TOOL_PATTERNS: list[ProcessPattern] = [
    ProcessPattern(
        name="claude-code",
        match_names=["claude"],
        match_cmdline=["claude"],
    ),
    ProcessPattern(
        name="cursor",
        match_names=["cursor", "Cursor"],
        match_cmdline=["cursor", "Cursor"],
    ),
    ProcessPattern(
        name="codex",
        match_names=["codex"],
        match_cmdline=["codex-cli", "codex run", "/codex"],
    ),
    ProcessPattern(
        name="opencode",
        match_names=["opencode"],
        match_cmdline=["opencode"],
    ),
    ProcessPattern(
        name="openclaw",
        match_names=["node"],
        match_cmdline=["openclaw"],
    ),
]


EXCLUDE_NAMES = {"snapfuse", "snapd", "grep", "defunct"}


def _match_process(proc: psutil.Process, pattern: ProcessPattern) -> bool:
    try:
        name = proc.name().lower()
        if name in EXCLUDE_NAMES:
            return False
        cmdline = " ".join(proc.cmdline()).lower()
        name_hit = any(n.lower() in name for n in pattern.match_names)
        cmd_hit = any(c.lower() in cmdline for c in pattern.match_cmdline)
        return name_hit or cmd_hit
    except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
        return False


def _estimate_status(proc: psutil.Process) -> tuple[ToolStatus, str]:
    try:
        cpu = proc.cpu_percent(interval=0)
        status_str = proc.status()

        if status_str in (psutil.STATUS_ZOMBIE, psutil.STATUS_DEAD):
            return ToolStatus.ERROR, f"process status: {status_str}"

        if status_str == psutil.STATUS_STOPPED:
            return ToolStatus.STOPPED, "process stopped"

        # High CPU = actively working
        if cpu > 5.0:
            return ToolStatus.RUNNING, f"cpu: {cpu:.1f}%"

        # Check children for activity
        children = proc.children(recursive=True)
        child_cpu = sum(c.cpu_percent(interval=0) for c in children
                        if c.is_running())
        if child_cpu > 5.0:
            return ToolStatus.THINKING, f"child cpu: {child_cpu:.1f}%"

        # Sleeping but alive = idle/waiting
        if status_str == psutil.STATUS_SLEEPING:
            return ToolStatus.IDLE, "sleeping"

        return ToolStatus.RUNNING, f"status: {status_str}"

    except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
        return ToolStatus.ERROR, "process inaccessible"


def scan_tools() -> list[ToolInfo]:
    results: dict[str, ToolInfo] = {}

    for pattern in TOOL_PATTERNS:
        best: ToolInfo | None = None
        for proc in psutil.process_iter(["pid", "name", "cmdline", "create_time"]):
            if _match_process(proc, pattern):
                status, detail = _estimate_status(proc)
                try:
                    mem = proc.memory_info().rss / (1024 * 1024)
                    cpu = proc.cpu_percent(interval=0)
                    uptime = time.time() - proc.create_time()
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    mem, cpu, uptime = 0.0, 0.0, 0.0

                info = ToolInfo(
                    name=pattern.name,
                    pid=proc.pid,
                    status=status,
                    cpu_percent=cpu,
                    memory_mb=round(mem, 1),
                    uptime_seconds=round(uptime, 0),
                    detail=detail,
                )
                # Pick the one with highest CPU (most active)
                if best is None or info.cpu_percent > best.cpu_percent:
                    best = info

        if best is None:
            best = ToolInfo(name=pattern.name, status=ToolStatus.STOPPED)

        results[pattern.name] = best

    return list(results.values())
