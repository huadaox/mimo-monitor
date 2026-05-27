from __future__ import annotations

import subprocess


def report_status(
    tool: str,
    event: str,
    status: str,
    detail: str = "",
    session_id: str = "",
    host: str = "localhost",
    port: int = 9100,
) -> None:
    """Report a hook event to mimo_monitor via HTTP POST."""
    import json
    import urllib.request

    url = f"http://{host}:{port}/api/hook"
    payload = json.dumps({
        "tool": tool,
        "event": event,
        "status": status,
        "detail": detail,
        "session_id": session_id,
    }).encode()

    req = urllib.request.Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=5):
            pass
    except Exception:
        pass


# Shell helper: prints the mimo_report function definition for sourcing
MIMO_REPORT_SHELL_FUNC = r'''
mimo_report() {
    local tool="$1"
    local event="$2"
    local status="$3"
    local detail="${4:-}"
    local session_id="${5:-}"
    curl -sf -X POST http://localhost:9100/api/hook \
        -H "Content-Type: application/json" \
        -d "{\"tool\":\"$tool\",\"event\":\"$event\",\"status\":\"$status\",\"detail\":\"$detail\",\"session_id\":\"$session_id\"}" \
        >/dev/null 2>&1 &
}
'''
