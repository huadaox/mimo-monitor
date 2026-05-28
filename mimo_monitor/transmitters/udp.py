"""
UDP broadcast transmitter for Mimo Monitor.

- Broadcasts all agent statuses as JSON every 2 seconds on port 9101.
- Supports device registration: any client that sends a UDP packet to 9101
  gets remembered and receives targeted pushes in addition to broadcasts.
- Reads state from the watcher (file-based protocol).
"""

from __future__ import annotations

import asyncio
import json
import logging
import socket
import time

from ..watcher import get_watcher
from ..detectors import scan_tools
from ..models import AgentState

logger = logging.getLogger("mimo.udp")

_VERSION = 1
_registered_devices: set[tuple[str, int]] = set()


class _UDPBroadcastProtocol(asyncio.DatagramProtocol):
    def connection_made(self, transport: asyncio.BaseTransport) -> None:
        self.transport: asyncio.DatagramTransport = transport  # type: ignore
        sock = self.transport.get_extra_info("socket")
        if sock is not None:
            try:
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            except Exception as exc:
                logger.warning("Could not set SO_BROADCAST: %s", exc)
        logger.info("UDP broadcast transport ready")

    def datagram_received(self, data: bytes, addr: tuple[str, int]) -> None:
        if addr not in _registered_devices:
            _registered_devices.add(addr)
            logger.info("Registered new UDP device: %s:%d", *addr)

    def error_received(self, exc: Exception) -> None:
        logger.error("UDP error: %s", exc)

    def connection_lost(self, exc: Exception | None) -> None:
        logger.warning("UDP connection lost: %s", exc)


async def start_udp_broadcast(port: int = 9101) -> None:
    """Start the UDP broadcast service."""
    loop = asyncio.get_running_loop()

    transport, protocol = await loop.create_datagram_endpoint(
        lambda: _UDPBroadcastProtocol(),
        local_addr=("0.0.0.0", port),
        allow_broadcast=True,
    )

    broadcast_addr = ("255.255.255.255", port)
    logger.info("UDP broadcast service started on port %d", port)

    # 进程检测缓存
    proc_cache = []
    proc_cache_time = 0.0

    try:
        while True:
            try:
                watcher = get_watcher()
                file_states = watcher.get_all_states()
                now = time.time()

                # 定期更新进程缓存
                if now - proc_cache_time > 5.0:
                    proc_cache = await asyncio.to_thread(scan_tools)
                    proc_cache_time = now

                known_tools = {"claude-code", "opencode", "codex", "cursor"}
                agents = []

                for tool_name in known_tools:
                    file_data = file_states.get(tool_name)
                    proc_info = next(
                        (t for t in proc_cache if t.name == tool_name), None
                    )

                    if file_data and (now - file_data.get("ts", 0) < 30):
                        agents.append({
                            "id": tool_name,
                            "status": file_data.get("state", "idle"),
                            "detail": file_data.get("detail", ""),
                            "tool": tool_name,
                            "cpu": proc_info.cpu_percent if proc_info else 0,
                            "mem_mb": proc_info.memory_mb if proc_info else 0,
                        })
                    elif proc_info:
                        agents.append({
                            "id": tool_name,
                            "status": "idle",
                            "detail": "Process detected",
                            "tool": tool_name,
                            "cpu": proc_info.cpu_percent,
                            "mem_mb": proc_info.memory_mb,
                        })

                payload = json.dumps({
                    "v": _VERSION,
                    "ts": now,
                    "agents": agents,
                }).encode("utf-8")

                try:
                    transport.sendto(payload, broadcast_addr)
                except Exception as exc:
                    logger.debug("Broadcast send error: %s", exc)

                for addr in list(_registered_devices):
                    try:
                        transport.sendto(payload, addr)
                    except Exception:
                        _registered_devices.discard(addr)

            except Exception as exc:
                logger.error("UDP broadcast tick error: %s", exc)

            await asyncio.sleep(2)
    finally:
        transport.close()
