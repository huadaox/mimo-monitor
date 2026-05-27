#!/usr/bin/env bash
# Claude Code hook handler — reports to mimo_monitor via HTTP POST.
#
# Claude Code hooks provide these env vars:
#   CLAUDE_PROJECT_DIR  - project directory
#   CLAUDE_FILE_PATHS   - files being modified (JSON array)
#   CLAUDE_TOOL_INPUT   - tool parameters as JSON
#
# The hook event type is passed as $1 (PreToolUse/PostToolUse/Stop/Notification)

set -euo pipefail

HOOK_EVENT="${1:-}"
TOOL_INPUT="${CLAUDE_TOOL_INPUT:-}"

# mimo_report: report hook event to mimo_monitor
mimo_report() {
    curl --noproxy localhost -sf -X POST http://localhost:9100/api/hook \
        -H "Content-Type: application/json" \
        -d "{\"tool\":\"$1\",\"event\":\"$2\",\"status\":\"$3\",\"detail\":\"$4\",\"session_id\":\"$5\"}" \
        >/dev/null 2>&1 &
}

# Map event to status
case "$HOOK_EVENT" in
    PreToolUse)
        STATUS="thinking"
        DETAIL="Preparing tool use"
        ;;
    PostToolUse)
        STATUS="running"
        DETAIL="Tool completed"
        ;;
    Stop)
        STATUS="idle"
        DETAIL="Session stopped"
        ;;
    Notification)
        STATUS="waiting"
        DETAIL="Waiting for user"
        ;;
    *)
        STATUS="running"
        DETAIL="$HOOK_EVENT"
        ;;
esac

# Extract tool name from CLAUDE_TOOL_INPUT if available
TOOL_NAME=""
if [[ -n "$TOOL_INPUT" ]] && command -v python3 &>/dev/null; then
    TOOL_NAME=$(echo "$TOOL_INPUT" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('tool_name','') or d.get('tool',''))" 2>/dev/null || true)
fi

# Use project dir as session identifier (no session ID env var available)
SESSION_ID="${CLAUDE_PROJECT_DIR:-unknown}"

mimo_report "claude-code" "$HOOK_EVENT" "$STATUS" "${DETAIL}${TOOL_NAME:+ ($TOOL_NAME)}" "$SESSION_ID"
