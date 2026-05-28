#!/usr/bin/env bash
# Mimo Monitor - Codex 插件
#
# 包装 codex 命令，启动/退出时写入状态文件。
# 安装: bash plugins/install.sh codex
#
# 注意: codex 没有细粒度 hook，只能捕获启动和退出。
# 中间状态通过进程检测回退。

set -e

# 找到真实的 codex 二进制
find_real_codex() {
    # 按优先级查找
    for candidate in \
        "$HOME/.hermes/node/bin/codex" \
        "$HOME/.local/bin/codex.real" \
        "$(command -v codex.real 2>/dev/null)" \
        "/snap/bin/codex" \
        "$(which codex 2>/dev/null | grep -v mimo || true)"; do
        if [[ -x "$candidate" ]]; then
            echo "$candidate"
            return
        fi
    done
    echo ""
}

STATE_DIR="$HOME/.agent-state"
TOOL="codex"
REAL_CODEX=$(find_real_codex)

write_state() {
    local state="$1" detail="${2:-}"
    local tmp="$STATE_DIR/$TOOL.tmp"
    local dst="$STATE_DIR/$TOOL.json"
    mkdir -p "$STATE_DIR"
    printf '{"state":"%s","detail":"%s","ts":%s}\n' \
        "$state" "$detail" "$(date +%s.%N)" > "$tmp"
    mv "$tmp" "$dst"
}

if [[ -z "$REAL_CODEX" ]]; then
    echo "[mimo] codex not found" >&2
    exit 1
fi

# 报告: codex 启动
write_state "working" "Codex started (PID: $$)"

# 运行真实 codex
status=0
"$REAL_CODEX" "$@" || status=$?

# 报告: codex 退出
if [[ $status -eq 0 ]]; then
    write_state "idle" "Codex exited normally"
else
    write_state "idle" "Codex exited (code: $status)"
fi

exit $status
