#!/usr/bin/env bash
# Mimo Monitor - Claude Code 插件
#
# 通过 Claude Code hooks 写入状态文件。
# 安装: bash plugins/install.sh claude-code
#
# Hook 事件 → 状态映射:
#   PreToolUse   → working (工具调用前)
#   PostToolUse  → working (工具调用后)
#   Notification → waiting (等待用户)
#   Stop         → idle    (任务完成)
#   SubagentStop → idle    (子代理完成)

set -euo pipefail

HOOK_EVENT="${1:-}"
STATE_DIR="$HOME/.agent-state"
TOOL="claude-code"

# 原子写入状态文件
write_state() {
    local state="$1" detail="${2:-}"
    local tmp="$STATE_DIR/$TOOL.tmp"
    local dst="$STATE_DIR/$TOOL.json"
    mkdir -p "$STATE_DIR"
    printf '{"state":"%s","detail":"%s","ts":%s}\n' \
        "$state" "$detail" "$(date +%s.%N)" > "$tmp"
    mv "$tmp" "$dst"
}

# 从 stdin 读取 JSON（Claude Code 通过 stdin 传入事件详情）
read_stdin() {
    if [[ -t 0 ]]; then
        echo ""
        return
    fi
    cat 2>/dev/null || echo ""
}

STDIN_DATA=$(read_stdin)

# 从 stdin 提取 tool_name
TOOL_NAME=""
if [[ -n "$STDIN_DATA" ]] && command -v python3 &>/dev/null; then
    TOOL_NAME=$(echo "$STDIN_DATA" | python3 -c "
import sys, json
try:
    d = json.load(sys.stdin)
    print(d.get('tool_name', '') or d.get('tool', ''))
except: pass
" 2>/dev/null || true)
fi

# 根据事件类型写入状态
case "$HOOK_EVENT" in
    PreToolUse)
        write_state "working" "Tool: ${TOOL_NAME:-preparing}"
        ;;
    PostToolUse)
        write_state "working" "Tool done: ${TOOL_NAME:-unknown}"
        ;;
    Notification)
        write_state "waiting" "Waiting for user"
        ;;
    Stop)
        write_state "idle" "Session stopped"
        ;;
    SubagentStop)
        write_state "idle" "Subagent done"
        ;;
    *)
        write_state "working" "$HOOK_EVENT"
        ;;
esac
