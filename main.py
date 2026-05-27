import asyncio
import logging
import uvicorn
from mimo_monitor.api import app
from mimo_monitor.transmitters import start_udp_broadcast, start_ble_service

logger = logging.getLogger("mimo")


async def _start_transmitters() -> None:
    """Launch UDP broadcast and BLE GATT tasks alongside the FastAPI server."""
    tasks = [
        asyncio.create_task(start_udp_broadcast(port=9101), name="udp-broadcast"),
        asyncio.create_task(start_ble_service(), name="ble-service"),
    ]
    logger.info("Transmitters started: UDP broadcast (9101), BLE GATT")
    # Keep references so they aren't garbage-collected
    app.state.transmitter_tasks = tasks


@app.on_event("startup")
async def _on_startup() -> None:
    await _start_transmitters()


@app.on_event("shutdown")
async def _on_shutdown() -> None:
    tasks: list[asyncio.Task] = getattr(app.state, "transmitter_tasks", [])
    for t in tasks:
        if not t.done():
            t.cancel()
            try:
                await t
            except asyncio.CancelledError:
                pass
    logger.info("Transmitter tasks stopped")


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=9100, log_level="info")
