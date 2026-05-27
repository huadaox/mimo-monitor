"""
UDP broadcast transmitter for Mimo Monitor.

- Broadcasts all agent statuses as JSON every 2 seconds on port 9101.
- Supports device registration: any client that sends a UDP packet to 9101
  gets remembered and receives targeted pushes in addition to broadcasts.
"""

from __future__ import annotations

import asyncio
import json
import logging
import socket
import time

from ..detectors import scan_tools
from ..models import ToolInfo

logger = logging.getLogger("mimo.udp")

# Protocol version
_VERSION = 1

# Registered device addresses: set of (host, port)
_registered_devices: set[tuple[str, int]] = set()


class _UDPBroadcastProtocol(asyncio.DatagramProtocol):
    """Handles incoming datagrams (device registration) and sends periodic broadcasts."""

    def connection_made(self, transport: asyncio.BaseTransport) -> None:
        self.transport: asyncio.DatagramTransport = transport  # type: ignore[assignment]
        # Enable broadcast on the socket
        sock = self.transport.get_extra_info("socket")
        if sock is not None:
            try:
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            except Exception as exc:
                logger.warning("Could not set SO_BROADCAST: %s", exc)
        logger.info("UDP broadcast transport ready")

    def datagram_received(self, data: bytes, addr: tuple[str, int]) -> None:
        """When a device sends us a packet, register it for targeted pushes."""
        if addr not in _registered_devices:
            _registered_devices.add(addr)
            logger.info("Registered new UDP device: %s:%d", *addr)
        # Try to parse as a command (optional JSON payload)
        try:
            msg = json.loads(data)
            logger.debug("Received from %s:%d: %s", *addr, msg)
        except (json.JSONDecodeError, UnicodeDecodeError):
            # Non-JSON packet — treat as registration ping
            logger.debug("Registration ping from %s:%d", *addr)

    def error_received(self, exc: Exception) -> None:
        logger.error("UDP error: %s", exc)

    def connection_lost(self, exc: Exception | None) -> None:
        logger.warning("UDP connection lost: %s", exc)


async def start_udp_broadcast(port: int = 9101) -> None:
    """
    Start the UDP broadcast service.

    - Binds to 0.0.0.0:port for both receiving (registration) and broadcasting.
    - Every 2 seconds, collects agent status via scan_tools() and sends
      a JSON payload to the broadcast address AND all registered devices.

    This coroutine runs forever and should be scheduled as an asyncio task.
    """
    loop = asyncio.get_running_loop()

    # Create the receiving endpoint
    transport, protocol = await loop.create_datagram_endpoint(
        lambda: _UDPBroadcastProtocol(),
        local_addr=("0.0.0.0", port),
        allow_broadcast=True,
    )

    broadcast_addr = ("255.255.255.255", port)

    logger.info("UDP broadcast service started on port %d", port)

    try:
        while True:
            try:
                tools: list[ToolInfo] = await asyncio.to_thread(scan_tools)
                payload = json.dumps({
                    "v": _VERSION,
                    "ts": time.time(),
                    "agents": [
                        {
                            "id": t.name,
                            "status": t.status.value,
                            "detail": t.detail,
                            "tool": t.name,
                            "cpu": t.cpu_percent,
                            "mem_mb": t.memory_mb,
                        }
                        for t in tools
                    ],
                }).encode("utf-8")

                # Broadcast to everyone
                try:
                    transport.sendto(payload, broadcast_addr)
                except Exception as exc:
                    logger.debug("Broadcast send error (non-fatal): %s", exc)

                # Targeted push to registered devices
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
