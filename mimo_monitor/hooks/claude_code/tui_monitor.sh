#!/usr/bin/env bash
# Claude Code 侵入式状态监控
# 通过 PTY 捕获 TUI 输出，解析真实状态

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
MIMO_URL="http://localhost:9100/api/hook"
STATE_FILE="/tmp/mimo_claude_state"
OUTPUT_LOG="/tmp/mimo_claude_output.log"

# 状态关键词映射
declare -A STATUS_PATTERNS=(
    ["Thinking"]="thinking"
    ["Reading"]="running"
    ["Writing"]="running"
    ["Executing"]="running"
    ["Calling"]="running"
    ["Waiting"]="waiting"
    ["Press Enter"]="waiting"
    ["? for help"]="idle"
    ["Error"]="error"
)

# 上报状态
report() {
    local event="$1"
    local detail="$2"
    curl --noproxy localhost -sf -X POST "$MIMO_URL" \
        -H "Content-Type: application/json" \
        -d "{\"tool\":\"claude-code\",\"event\":\"$event\",\"detail\":\"$detail\"}" \
        >/dev/null 2>&1 &
}

# 解析输出中的状态
parse_status() {
    local line="$1"
    
    for pattern in "${!STATUS_PATTERNS[@]}"; do
        if [[ "$line" == *"$pattern"* ]]; then
            local status="${STATUS_PATTERNS[$pattern]}"
            local current_state=$(cat "$STATE_FILE" 2>/dev/null || echo "idle")
            
            # 状态变化时上报
            if [[ "$status" != "$current_state" ]]; then
                echo "$status" > "$STATE_FILE"
                report "TUI_$status" "$pattern detected"
            fi
            break
        fi
    done
}

# 主函数：包装 Claude Code
main() {
    echo "[mimo] Starting Claude Code with TUI monitoring..."
    
    # 初始化状态
    echo "idle" > "$STATE_FILE"
    report "start" "Claude Code started with TUI monitoring"
    
    # 使用 script 命令捕获 TUI 输出
    # -q: 安静模式, -f: 实时刷新, -c: 执行命令
    script -q -f -c "claude $*" "$OUTPUT_LOG" &
    local SCRIPT_PID=$!
    
    # 实时解析输出
    tail -f "$OUTPUT_LOG" 2>/dev/null | while read -r line; do
        parse_status "$line"
    done &
    local PARSER_PID=$!
    
    # 等待 Claude Code 退出
    wait $SCRIPT_PID
    local EXIT_CODE=$?
    
    # 清理
    kill $PARSER_PID 2>/dev/null
    report "exit" "Claude Code exited with code $EXIT_CODE"
    rm -f "$STATE_FILE"
    
    exit $EXIT_CODE
}

main "$@"
