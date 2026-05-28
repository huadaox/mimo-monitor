"""
Mimo Monitor - 通用状态文件协议

所有工具的插件通过写文件上报状态，服务端通过读文件获取状态。
不依赖 HTTP、不依赖服务先启动。

状态文件位置: ~/.agent-state/{tool}.json
状态文件格式: {"state": "working", "detail": "...", "ts": 1716800000.123}
状态值: working | waiting | idle | stopped
"""

from __future__ import annotations

import json
import time
from pathlib import Path

# 状态文件目录
STATE_DIR = Path.home() / ".agent-state"

# 状态常量
WORKING = "working"
WAITING = "waiting"
IDLE = "idle"
STOPPED = "stopped"

# 文件超时：超过这个时间没更新，视为 stale
STALE_TIMEOUT = 60.0


def report(tool: str, state: str, detail: str = "") -> None:
    """原子写入状态文件。

    所有插件的核心函数。写入过程：
    1. 写到临时文件 {tool}.tmp
    2. rename 到 {tool}.json（原子操作）

    这样读端不会读到半写的状态。
    """
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    path = STATE_DIR / f"{tool}.json"
    tmp = STATE_DIR / f"{tool}.tmp"
    data = {
        "state": state,
        "detail": detail,
        "ts": time.time(),
    }
    tmp.write_text(json.dumps(data, separators=(",", ":")))
    tmp.rename(path)


def read_state(tool: str) -> dict | None:
    """读取单个工具的状态文件。"""
    path = STATE_DIR / f"{tool}.json"
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text())
        # 检查是否过期
        if time.time() - data.get("ts", 0) > STALE_TIMEOUT:
            return None
        return data
    except (json.JSONDecodeError, OSError):
        return None


def read_all_states() -> dict[str, dict]:
    """读取所有工具的状态文件。"""
    if not STATE_DIR.exists():
        return {}
    result = {}
    for path in STATE_DIR.glob("*.json"):
        tool = path.stem
        try:
            data = json.loads(path.read_text())
            if time.time() - data.get("ts", 0) <= STALE_TIMEOUT:
                result[tool] = data
        except (json.JSONDecodeError, OSError):
            continue
    return result


def clear_state(tool: str) -> None:
    """清除工具的状态文件。"""
    path = STATE_DIR / f"{tool}.json"
    path.unlink(missing_ok=True)


# Shell 一行版（供 bash hook 使用）
SHELL_REPORT = r'''
# 写入状态文件（一行版）
# 用法: mimo_write_state tool state detail
mimo_write_state() {
    local tool="$1" state="$2" detail="${3:-}"
    local dir="$HOME/.agent-state"
    local tmp="$dir/$tool.tmp"
    local dst="$dir/$tool.json"
    mkdir -p "$dir"
    printf '{"state":"%s","detail":"%s","ts":%s}\n' "$state" "$detail" "$(date +%s.%N)" > "$tmp"
    mv "$tmp" "$dst"
}
'''
