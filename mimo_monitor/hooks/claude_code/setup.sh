#!/usr/bin/env bash
# Setup Claude Code hooks in ~/.claude/settings.json
# Adds PreToolUse, PostToolUse, Stop, Notification hooks that call handler.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
HANDLER_PATH="$SCRIPT_DIR/handler.sh"
SETTINGS_FILE="$HOME/.claude/settings.json"

# Ensure handler is executable
chmod +x "$HANDLER_PATH"

# Create settings file if it doesn't exist
if [[ ! -f "$SETTINGS_FILE" ]]; then
    mkdir -p "$(dirname "$SETTINGS_FILE")"
    echo '{}' > "$SETTINGS_FILE"
fi

# Use python3 to merge hooks into settings.json (preserves existing content)
# Claude Code hooks format: {"matcher": "", "hooks": [{"type": "command", "command": "..."}]}
python3 - "$SETTINGS_FILE" "$HANDLER_PATH" <<'PYEOF'
import json
import sys

settings_path = sys.argv[1]
handler = sys.argv[2]

with open(settings_path) as f:
    settings = json.load(f)

hooks = settings.setdefault("hooks", {})

hook_events = ["PreToolUse", "PostToolUse", "Stop", "Notification"]
for event in hook_events:
    event_hooks = hooks.setdefault(event, [])
    cmd = f"bash {handler} {event}"
    # Avoid duplicate entries - check in hooks array within each matcher entry
    already_exists = False
    for matcher_entry in event_hooks:
        for h in matcher_entry.get("hooks", []):
            if h.get("command") == cmd:
                already_exists = True
                break
    if not already_exists:
        event_hooks.append({
            "matcher": "",
            "hooks": [{"type": "command", "command": cmd}],
        })

with open(settings_path, "w") as f:
    json.dump(settings, f, indent=2)
    f.write("\n")

print(f"Updated {settings_path} with mimo_monitor hooks")
PYEOF
