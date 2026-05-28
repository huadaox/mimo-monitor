"""
Mimo Monitor - 文件系统监控

监控 ~/.agent-state/ 目录，状态变化时触发回调。
优先用 inotify（Linux），不可用时降级为轮询。
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import struct
import time
from pathlib import Path

from .protocol import STATE_DIR, STALE_TIMEOUT

logger = logging.getLogger("mimo.watcher")

# inotify 常量
_IN_MODIFY = 0x00000002
_IN_MOVED_TO = 0x00000080
_IN_CREATE = 0x00000100
_IN_CLOSE_WRITE = 0x00000008
_IN_NONBLOCK = 0o4000

# 监控的事件
_WATCH_EVENTS = _IN_MODIFY | _IN_MOVED_TO | _IN_CREATE | _IN_CLOSE_WRITE


class StateWatcher:
    """监控 ~/.agent-state/ 目录的状态变化。"""

    def __init__(self):
        self._states: dict[str, dict] = {}
        self._callbacks: list = []
        self._running = False

    def on_change(self, callback):
        """注册状态变化回调: callback(tool: str, state: dict)"""
        self._callbacks.append(callback)

    def get_state(self, tool: str) -> dict | None:
        """获取工具当前状态。"""
        return self._states.get(tool)

    def get_all_states(self) -> dict[str, dict]:
        """获取所有工具状态。"""
        return dict(self._states)

    def _notify(self, tool: str, state: dict):
        for cb in self._callbacks:
            try:
                cb(tool, state)
            except Exception as exc:
                logger.error("Callback error: %s", exc)

    def _read_file(self, tool: str) -> dict | None:
        path = STATE_DIR / f"{tool}.json"
        if not path.exists():
            return None
        try:
            data = json.loads(path.read_text())
            if time.time() - data.get("ts", 0) > STALE_TIMEOUT:
                return None
            return data
        except (json.JSONDecodeError, OSError):
            return None

    def _scan_all(self):
        """扫描所有状态文件，返回变化的工具列表。"""
        if not STATE_DIR.exists():
            return []
        changed = []
        current_files = set()
        for path in STATE_DIR.glob("*.json"):
            tool = path.stem
            current_files.add(tool)
            new_state = self._read_file(tool)
            old_state = self._states.get(tool)
            if new_state and (not old_state or new_state != old_state):
                self._states[tool] = new_state
                changed.append((tool, new_state))
            elif not new_state and old_state:
                del self._states[tool]
                changed.append((tool, None))
        # 检查消失的工具
        for tool in list(self._states.keys()):
            if tool not in current_files:
                del self._states[tool]
                changed.append((tool, None))
        return changed

    async def start(self):
        """启动监控。优先 inotify，降级为轮询。"""
        self._running = True
        STATE_DIR.mkdir(parents=True, exist_ok=True)

        # 初始扫描
        for tool, state in self._scan_all():
            self._notify(tool, state)

        # 尝试 inotify
        try:
            await self._watch_inotify()
        except Exception as exc:
            logger.info("inotify not available (%s), using polling", exc)
            await self._watch_poll()

    async def stop(self):
        self._running = False

    async def _watch_inotify(self):
        """用 inotify 监控目录变化。"""
        fd = os.inotify_init()
        if fd < 0:
            raise RuntimeError("inotify_init failed")

        try:
            import fcntl
            flags = fcntl.fcntl(fd, fcntl.F_GETFL)
            fcntl.fcntl(fd, fcntl.F_SETFL, flags | os.O_NONBLOCK)

            wd = os.inotify_add_watch(fd, str(STATE_DIR), _WATCH_EVENTS)
            if wd < 0:
                raise RuntimeError("inotify_add_watch failed")

            logger.info("Watching %s with inotify", STATE_DIR)
            event_struct = struct.Struct("iIII")
            event_size = event_struct.size

            while self._running:
                try:
                    data = os.read(fd, 4096)
                except BlockingIOError:
                    await asyncio.sleep(0.1)
                    continue
                if not data:
                    await asyncio.sleep(0.1)
                    continue

                # 解析事件
                offset = 0
                while offset < len(data):
                    if offset + event_size > len(data):
                        break
                    wd, mask, cookie, name_len = event_struct.unpack_from(data, offset)
                    offset += event_size + name_len

                    # 只关心 .json 文件
                    for tool, state in self._scan_all():
                        self._notify(tool, state)

                await asyncio.sleep(0.05)

        finally:
            os.close(fd)

    async def _watch_poll(self):
        """轮询模式监控。"""
        logger.info("Watching %s with polling (1s interval)", STATE_DIR)
        while self._running:
            for tool, state in self._scan_all():
                self._notify(tool, state)
            await asyncio.sleep(1.0)


# 全局实例
_watcher: StateWatcher | None = None


def get_watcher() -> StateWatcher:
    global _watcher
    if _watcher is None:
        _watcher = StateWatcher()
    return _watcher
