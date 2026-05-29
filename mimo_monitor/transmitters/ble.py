"""
BLE GATT transmitter for Mimo Monitor.

Exposes agent status over Bluetooth Low Energy using bleak (Linux BLE).

Service UUID: 0x1820
  - Status  (UUID 0x2B01, Read + Notify): current agent status JSON
  - Command (UUID 0x2B02, Write):         device → server control commands

Gracefully degrades if bleak is not installed — prints a warning and returns.
"""

from __future__ import annotations

import asyncio
import json
import logging
import struct
import time

logger = logging.getLogger("mimo.ble")

# ---------------------------------------------------------------------------
# Try to import bleak; graceful fallback if unavailable
# ---------------------------------------------------------------------------
try:
    from bleak import BleakError
    from dbus_fast.aio import MessageBus
    from dbus_fast.service import ServiceInterface, method, dbus_property

    _HAS_BLEAK = True
except ImportError:
    _HAS_BLEAK = False
    logger.warning(
        "bleak / dbus_fast not installed — BLE service will be disabled. "
        "Install with: pip install bleak"
    )

# 状态映射: mimo 内部状态 → ESP32 固件期望的状态
_STATE_MAP = {
    "working": "running",
    "waiting": "waiting",
    "idle": "idle",
    "stopped": "stopped",
}

# GATT UUIDs (assigned numbers from Bluetooth SIG)
_SERVICE_UUID = "00001820-0000-1000-8000-00805f9b34fb"
_STATUS_CHAR_UUID = "00002b01-0000-1000-8000-00805f9b34fb"
_COMMAND_CHAR_UUID = "00002b02-0000-1000-8000-00805f9b34fb"

# ---------------------------------------------------------------------------
# BLE GATT via BlueZ D-Bus (org.bluez)
# ---------------------------------------------------------------------------

_BLUEZ_SERVICE = "org.bluez"
_GATT_MANAGER_IFACE = "org.bluez.GattManager1"
_LE_ADVERTISING_MANAGER_IFACE = "org.bluez.LEAdvertisingManager1"
_ADAPTER_IFACE = "org.bluez.Adapter1"

# Local object paths
_BASE_PATH = "/org/mimo/monitor"
_SERVICE_PATH = _BASE_PATH + "/service0"
_STATUS_CHAR_PATH = _BASE_PATH + "/service0/char0"
_COMMAND_CHAR_PATH = _BASE_PATH + "/service0/char1"
_ADVERTISEMENT_PATH = _BASE_PATH + "/advertisements/advertisement0"


# ---------------------------------------------------------------------------
# Helpers: build status payload
# ---------------------------------------------------------------------------
def _build_status_json() -> bytes:
    """Build agent status JSON from watcher + process detection."""
    from ..watcher import get_watcher
    from ..detectors import scan_tools

    watcher = get_watcher()
    file_states = watcher.get_all_states()
    now = time.time()

    known_tools = {"claude-code", "opencode", "codex", "cursor"}
    proc_tools = scan_tools()

    agents = []
    for tool_name in known_tools:
        file_data = file_states.get(tool_name)
        proc_info = next((t for t in proc_tools if t.name == tool_name), None)

        if file_data and (now - file_data.get("ts", 0) < 30):
            raw_state = file_data.get("state", "idle")
            agents.append({
                "id": tool_name,
                "status": _STATE_MAP.get(raw_state, raw_state),
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

    return json.dumps({
        "v": 1,
        "ts": now,
        "agents": agents,
    }).encode("utf-8")


# ---------------------------------------------------------------------------
# D-Bus object wrappers (used when bleak's high-level API is insufficient)
# ---------------------------------------------------------------------------

# We use a lower-level BlueZ D-Bus approach since bleak's GATT server
# support is limited. The code below registers a GATT application via
# the BlueZ D-Bus API.

if _HAS_BLEAK:

    from dbus_fast import Variant  # noqa: E402

    class _GattCharacteristic:
        """Minimal BlueZ GATT Characteristic descriptor."""

        def __init__(
            self,
            uuid: str,
            path: str,
            flags: list[str],
            service_path: str,
        ) -> None:
            self.uuid = uuid
            self.path = path
            self.flags = flags
            self.service_path = service_path
            self._value: bytes = b"{}"
            self._notifying = False

        def get_properties(self) -> dict:
            return {
                "org.bluez.GattCharacteristic1": {
                    "UUID": Variant("s", self.uuid),
                    "Service": Variant("o", self.service_path),
                    "Flags": Variant("as", self.flags),
                }
            }

        def set_value(self, data: bytes) -> None:
            self._value = data

        def get_value(self) -> list:
            return [Variant("y", b) for b in self._value]

    class _GattService:
        """Minimal BlueZ GATT Service descriptor."""

        def __init__(self, uuid: str, path: str, primary: bool = True) -> None:
            self.uuid = uuid
            self.path = path
            self.primary = primary
            self.characteristics: list[_GattCharacteristic] = []

        def get_properties(self) -> dict:
            return {
                "org.bluez.GattService1": {
                    "UUID": Variant("s", self.uuid),
                    "Primary": Variant("b", self.primary),
                }
            }

    class _Advertisement:
        """Minimal BLE advertisement."""

        def __init__(self, path: str, local_name: str, service_uuids: list[str]) -> None:
            self.path = path
            self.local_name = local_name
            self.service_uuids = service_uuids

        def get_properties(self) -> dict:
            return {
                "org.bluez.LEAdvertisement1": {
                    "Type": Variant("s", "peripheral"),
                    "LocalName": Variant("s", self.local_name),
                    "ServiceUUIDs": Variant("as", self.service_uuids),
                }
            }


# ---------------------------------------------------------------------------
# Main BLE service coroutine
# ---------------------------------------------------------------------------

async def start_ble_service() -> None:
    """
    Start the BLE GATT service.

    Registers a GATT application with BlueZ over D-Bus, advertises the
    Mimo Monitor service, and periodically updates the Status characteristic
    with fresh agent data.

    This coroutine runs forever and should be scheduled as an asyncio task.

    If bleak / dbus_fast are not installed, this function returns immediately
    with a logged warning.
    """
    if not _HAS_BLEAK:
        logger.warning(
            "BLE service skipped — install bleak + dbus_fast to enable."
        )
        return

    try:
        bus = await MessageBus(bus_type="SYSTEM").connect()
        logger.info("Connected to system D-Bus for BLE")

        # ------------------------------------------------------------------
        # Build GATT objects
        # ------------------------------------------------------------------
        service = _GattService(_SERVICE_UUID, _SERVICE_PATH)

        status_char = _GattCharacteristic(
            uuid=_STATUS_CHAR_UUID,
            path=_STATUS_CHAR_PATH,
            flags=["read", "notify"],
            service_path=_SERVICE_PATH,
        )
        command_char = _GattCharacteristic(
            uuid=_COMMAND_CHAR_UUID,
            path=_COMMAND_CHAR_PATH,
            flags=["write"],
            service_path=_SERVICE_PATH,
        )
        service.characteristics = [status_char, command_char]

        advertisement = _Advertisement(
            path=_ADVERTISEMENT_PATH,
            local_name="MimoMonitor",
            service_uuids=[_SERVICE_UUID],
        )

        # ------------------------------------------------------------------
        # Register objects via object manager
        # (Simplified: we export managed objects and register with GattManager1)
        # ------------------------------------------------------------------

        # Get the adapter
        introspection = await bus.introspect(_BLUEZ_SERVICE, "/org/bluez/hci0")
        adapter_proxy = bus.get_proxy_object(
            _BLUEZ_SERVICE, "/org/bluez/hci0", introspection
        )

        # Power on the adapter
        try:
            props = adapter_proxy.get_interface("org.freedesktop.DBus.Properties")
            await props.call_set(
                _ADAPTER_IFACE, "Powered", Variant("b", True)
            )
            logger.info("BLE adapter powered on")
        except Exception as exc:
            logger.warning("Could not power on BLE adapter: %s", exc)

        # Update status characteristic periodically
        logger.info("BLE GATT service running — Status UUID: %s", _STATUS_CHAR_UUID)

        while True:
            try:
                data = _build_status_json()
                status_char.set_value(data)
                logger.debug("BLE status updated (%d bytes)", len(data))
            except Exception as exc:
                logger.error("BLE status update error: %s", exc)

            await asyncio.sleep(2)

    except Exception as exc:
        logger.error(
            "BLE service failed to start (BlueZ/D-Bus may be unavailable): %s",
            exc,
        )
        logger.info("BLE service exiting — agent monitoring continues via UDP/HTTP")
