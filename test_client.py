"""Test client for Mimo Monitor API."""
import asyncio
import json
import sys
import time

import httpx


BASE = "http://localhost:9100"


def test_rest():
    print("=== REST API Tests ===")

    r = httpx.get(f"{BASE}/api/health")
    print(f"GET /api/health -> {r.json()}")

    r = httpx.get(f"{BASE}/api/status")
    tools = r.json()
    print(f"GET /api/status -> {len(tools)} tools:")
    for t in tools:
        icon = {"running": "🟢", "idle": "🟡", "stopped": "⚫", "error": "🔴", "thinking": "🔵", "waiting": "🟠"}.get(t["status"], "❓")
        pid = t.get("pid") or "-"
        print(f"  {icon} {t['name']:12s}  status={t['status']:8s}  pid={pid:>6}  mem={t['memory_mb']:.0f}MB")

    r = httpx.get(f"{BASE}/api/status/claude-code")
    print(f"GET /api/status/claude-code -> {r.json()['status']}")

    r = httpx.post(f"{BASE}/api/status", json={
        "tool": "esp32-test",
        "status": "running",
        "detail": "LED breathing mode",
    })
    print(f"POST /api/status -> {r.json()['ok']}")

    r = httpx.get(f"{BASE}/api/log?limit=5")
    print(f"GET /api/log -> {len(r.json())} entries")


async def test_ws():
    print("\n=== WebSocket Test ===")
    try:
        from websockets.asyncio.client import connect
    except ImportError:
        print("websockets not installed, skipping WS test")
        return

    async with connect("ws://localhost:9100/ws") as ws:
        # Should receive init message
        msg = json.loads(await ws.recv())
        print(f"WS init: {len(msg['tools'])} tools")
        for t in msg["tools"]:
            print(f"  {t['name']:12s} -> {t['status']}")

        # Ping test
        await ws.send("ping")
        msg = json.loads(await ws.recv())
        print(f"WS ping -> {msg['event']}")

        print("WS: waiting for status changes (Ctrl+C to stop)...")
        try:
            while True:
                msg = json.loads(await ws.recv())
                print(f"  [{time.strftime('%H:%M:%S')}] {msg['event']}: {msg.get('tool', '')} -> {msg.get('status', '')}")
        except KeyboardInterrupt:
            print("WS: stopped")


if __name__ == "__main__":
    test_rest()
    if "--ws" in sys.argv:
        asyncio.run(test_ws())
