#!/usr/bin/env bash
# Mimo Monitor - 插件安装脚本
#
# 用法:
#   bash install.sh              # 安装所有插件
#   bash install.sh claude-code  # 只安装 Claude Code
#   bash install.sh codex        # 只安装 Codex
#   bash install.sh opencode     # 只安装 OpenCode
#   bash install.sh --uninstall  # 卸载所有插件

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
CLAUDE_SETTINGS="$HOME/.claude/settings.json"

# ============== Claude Code ==============

install_claude_code() {
    echo "[1] Installing Claude Code plugin..."
    local handler="$SCRIPT_DIR/claude_code.sh"
    chmod +x "$handler"

    # 写入 ~/.claude/settings.json
    mkdir -p "$(dirname "$CLAUDE_SETTINGS")"
    if [[ ! -f "$CLAUDE_SETTINGS" ]]; then
        echo '{}' > "$CLAUDE_SETTINGS"
    fi

    python3 - "$CLAUDE_SETTINGS" "$handler" <<'PYEOF'
import json, sys

settings_path, handler = sys.argv[1], sys.argv[2]
with open(settings_path) as f:
    settings = json.load(f)

hooks = settings.setdefault("hooks", {})

# 新的 hook 事件
events = ["PreToolUse", "PostToolUse", "Stop", "Notification", "SubagentStop"]
for event in events:
    event_hooks = hooks.setdefault(event, [])
    cmd = f"bash {handler} {event}"
    # 检查是否已存在
    exists = False
    for entry in event_hooks:
        for h in entry.get("hooks", []):
            if h.get("command") == cmd:
                exists = True
                break
    if not exists:
        event_hooks.append({
            "matcher": "",
            "hooks": [{"type": "command", "command": cmd}],
        })

with open(settings_path, "w") as f:
    json.dump(settings, f, indent=2)
    f.write("\n")

print(f"  Updated: {settings_path}")
PYEOF

    echo "  Done. Restart Claude Code to activate."
}

# ============== Codex ==============

install_codex() {
    echo "[2] Installing Codex plugin..."
    local wrapper="$SCRIPT_DIR/codex.sh"
    chmod +x "$wrapper"

    # 安装 wrapper 到 ~/.local/bin
    local bin_dir="$HOME/.local/bin"
    mkdir -p "$bin_dir"

    # 找到真实 codex 路径
    local real_codex=""
    for candidate in "$HOME/.hermes/node/bin/codex" "/snap/bin/codex" "$(which codex 2>/dev/null)"; do
        if [[ -x "$candidate" ]] && [[ "$candidate" != "$bin_dir/codex" ]]; then
            real_codex="$candidate"
            break
        fi
    done

    if [[ -z "$real_codex" ]]; then
        echo "  Warning: codex not found, skipping"
        return
    fi

    # 创建 wrapper，内嵌真实路径
    cat > "$bin_dir/codex" <<WRAPPER
#!/usr/bin/env bash
# Mimo wrapper for codex
STATE_DIR="\$HOME/.agent-state"
TOOL="codex"
REAL="$real_codex"

write_state() {
    local state="\$1" detail="\${2:-}"
    local tmp="\$STATE_DIR/\$TOOL.tmp"
    local dst="\$STATE_DIR/\$TOOL.json"
    mkdir -p "\$STATE_DIR"
    printf '{"state":"%s","detail":"%s","ts":%s}\\n' "\$state" "\$detail" "\$(date +%s.%N)" > "\$tmp"
    mv "\$tmp" "\$dst"
}

write_state "working" "Codex started (PID: \$\$)"
status=0
"\$REAL" "\$@" || status=\$?
if [[ \$status -eq 0 ]]; then
    write_state "idle" "Codex exited"
else
    write_state "idle" "Codex exited (code: \$status)"
fi
exit \$status
WRAPPER
    chmod +x "$bin_dir/codex"

    echo "  Installed wrapper: $bin_dir/codex"
    echo "  Real binary: $real_codex"
    echo "  Ensure $bin_dir is in your PATH"
}

# ============== OpenCode ==============

install_opencode() {
    echo "[3] Installing OpenCode plugin..."
    echo "  OpenCode plugin: $SCRIPT_DIR/opencode.ts"
    echo "  Add to your OpenCode config:"
    echo "    plugins: [\"$SCRIPT_DIR/opencode.ts\"]"
}

# ============== Uninstall ==============

uninstall_all() {
    echo "Uninstalling mimo plugins..."

    # 移除 Claude Code hooks
    if [[ -f "$CLAUDE_SETTINGS" ]]; then
        python3 - "$CLAUDE_SETTINGS" <<'PYEOF'
import json, sys

path = sys.argv[1]
with open(path) as f:
    settings = json.load(f)

hooks = settings.get("hooks", {})
events = ["PreToolUse", "PostToolUse", "Stop", "Notification", "SubagentStop"]
for event in events:
    if event in hooks:
        # 移除 mimo hooks
        hooks[event] = [
            entry for entry in hooks[event]
            if not any("claude_code.sh" in h.get("command", "") for h in entry.get("hooks", []))
        ]
        if not hooks[event]:
            del hooks[event]

with open(path, "w") as f:
    json.dump(settings, f, indent=2)
    f.write("\n")
print(f"  Cleaned: {path}")
PYEOF
    fi

    # 移除 codex wrapper
    local wrapper="$HOME/.local/bin/codex"
    if [[ -f "$wrapper" ]] && grep -q "Mimo wrapper" "$wrapper" 2>/dev/null; then
        rm "$wrapper"
        echo "  Removed: $wrapper"
    fi

    # 清除状态文件
    rm -rf "$HOME/.agent-state"
    echo "  Cleared state files"

    echo "Done."
}

# ============== Main ==============

case "${1:-all}" in
    claude-code) install_claude_code ;;
    codex)       install_codex ;;
    opencode)    install_opencode ;;
    --uninstall) uninstall_all ;;
    all)
        install_claude_code
        install_codex
        install_opencode
        echo ""
        echo "All plugins installed. Restart your tools to activate."
        ;;
    *)
        echo "Usage: $0 [claude-code|codex|opencode|all|--uninstall]"
        exit 1
        ;;
esac
