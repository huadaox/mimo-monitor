#!/usr/bin/env bash
# Codex wrapper - intercepts calls to report status to mimo_monitor
# This wrapper is installed to ~/.local/bin/codex (higher priority than /snap/bin/codex)
set -e

REAL_CODEX="${HOME}/.hermes/node/bin/codex"
MIMO_URL="http://localhost:9100/api/hook"
SESSION_ID="codex-$$"

report() {
  local event="$1"
  local status="$2"
  local detail="$3"
  curl --noproxy localhost -sf -X POST \
    -H "Content-Type: application/json" \
    -d "{\"tool\":\"codex\",\"event\":\"${event}\",\"status\":\"${status}\",\"detail\":\"${detail}\",\"session_id\":\"${SESSION_ID}\"}" \
    "${MIMO_URL}" >/dev/null 2>&1 &
}

# Report: codex starting
report "start" "running" "Codex session started (PID: $$)"

# Run real codex with all arguments
status=0
"${REAL_CODEX}" "$@" || status=$?

# Report: codex finished
if [ $status -eq 0 ]; then
  report "exit" "idle" "Codex session ended normally"
else
  report "exit" "error" "Codex session ended with exit code: ${status}"
fi

exit $status
