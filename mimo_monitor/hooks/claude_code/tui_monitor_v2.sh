#!/usr/bin/env bash
# Claude Code 侵入式状态监控 v2
# 用 strace 跟踪 TUI 输出，解析真实状态

set -e

MIMO_URL="http://localhost:9100/api/hook"
STATE_FILE="/tmp/mimo_claude_state"

# 状态关键词映射
declare -A STATUS_PATTERNS=(
    ["Thinking"]="thinking"
    ["Reading"]="running"
    ["Writing"]="running"
    ["Executing"]="running"
    ["Calling"]="running"
    ["Waiting"]="waiting"
    ["Press Enter"]="waiting"
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

# 主函数
main() {
    # 找到 Claude Code 进程
    local CLAUDE_PID=$(pgrep -f "claude" | head -1)
    
    if [[ -z "$CLAUDE_PID" ]]; then
        echo "Error: Claude Code not running"
        exit 1
    fi
    
    echo "[mimo] Monitoring Claude Code (PID: $CLAUDE_PID)..."
    echo "idle" > "$STATE_FILE"
    
    # 用 strace 跟踪 write 系统调用
    # -e trace=write: 只跟踪 write 调用
    -s 1000: 最大字符串长度
    -p $CLAUDE_PID: 附加到进程
    strace -e trace=write -s 1000 -p $CLAUDE_PID 2>&1 | while read -r line; do
        # 过滤终端输出（fd=1 是 stdout）
        if [[ "$line" == *"write(1,"* ]]; then
            # 提取写入的内容
            local content=$(echo "$line" | sed -n 's/.*write(1, "\(.*\)", [0-9]*).*/\1/p')
            if [[ -n "$content" ]]; then
                parse_status "$content"
            fi
        fi
    done
}

main "$@"
