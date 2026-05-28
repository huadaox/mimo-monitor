#!/usr/bin/env bash
# Claude Code TUI 状态监控 - 最终方案
# 用 script 命令创建伪终端，捕获 TUI 输出

set -e

MIMO_URL="http://localhost:9100/api/hook"
STATE_FILE="/tmp/mimo_claude_state"
CAPTURE_FILE="/tmp/mimo_claude_capture.log"

# 上报状态
report() {
    local event="$1"
    local detail="$2"
    curl --noproxy localhost -sf -X POST "$MIMO_URL" \
        -H "Content-Type: application/json" \
        -d "{\"tool\":\"claude-code\",\"event\":\"$event\",\"detail\":\"$detail\"}" \
        >/dev/null 2>&1 &
}

# 解析状态
parse_status() {
    local content="$1"
    
    # 清理 ANSI 转义码
    clean=$(echo "$content" | sed 's/\x1b\[[0-9;]*[a-zA-Z]//g' | tr -d '\r')
    
    # 状态映射
    if [[ "$clean" == *"Thinking"* ]]; then
        echo "thinking"
    elif [[ "$clean" == *"Reading"* ]] || [[ "$clean" == *"Writing"* ]]; then
        echo "running"
    elif [[ "$clean" == *"Executing"* ]] || [[ "$clean" == *"Calling"* ]]; then
        echo "running"
    elif [[ "$clean" == *"Waiting"* ]] || [[ "$clean" == *"Press Enter"* ]]; then
        echo "waiting"
    elif [[ "$clean" == *"Error"* ]]; then
        echo "error"
    else
        echo ""
    fi
}

# 主监控循环
monitor() {
    echo "[mimo] Starting TUI monitor..."
    echo "idle" > "$STATE_FILE"
    report "start" "TUI monitoring started"
    
    # 清空捕获文件
    > "$CAPTURE_FILE"
    
    # 用 tail 实时跟踪捕获文件
    tail -f "$CAPTURE_FILE" 2>/dev/null | while IFS= read -r line; do
        status=$(parse_status "$line")
        
        if [[ -n "$status" ]]; then
            current=$(cat "$STATE_FILE" 2>/dev/null || echo "idle")
            
            if [[ "$status" != "$current" ]]; then
                echo "$status" > "$STATE_FILE"
                report "TUI_$status" "Detected: $line"
                echo "[mimo] State: $current → $status"
            fi
        fi
    done
}

# 清理函数
cleanup() {
    report "exit" "TUI monitoring stopped"
    rm -f "$STATE_FILE" "$CAPTURE_FILE"
    exit 0
}

trap cleanup EXIT INT TERM

# 启动
monitor &
MONITOR_PID=$!

# 启动 Claude Code 并捕获输出
script -q -f -c "claude $*" "$CAPTURE_FILE"

# 等待监控进程
wait $MONITOR_PID
