#!/usr/bin/env bash
# OpenCode wrapper - intercepts opencode calls to report status to mimo_monitor
# Install to ~/.local/bin/opencode (takes priority in PATH)

set -euo pipefail

MIMO_HOOK_URL="http://localhost:9100/api/hook"
REAL_OPENCODE="${HOME}/.opencode/bin/opencode"

mimo_report() {
    curl --noproxy localhost -sf -X POST "$MIMO_HOOK_URL" \
        -H "Content-Type: application/json" \
        -d "{\"tool\":\"opencode\",\"event\":\"$1\",\"status\":\"$2\",\"detail\":\"$3\",\"session_id\":\"$4\"}" \
        >/dev/null 2>&1 &
}

# Report start
mimo_report "start" "running" "OpenCode started" "opencode-$$"

# Trap exit to report stop
trap 'mimo_report "stop" "idle" "OpenCode exited (exit=$?)" "opencode-$$"' EXIT

# Run real opencode with all args
exec "$REAL_OPENCODE" "$@"
