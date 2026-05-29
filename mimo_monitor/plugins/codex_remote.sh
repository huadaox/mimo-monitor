#!/usr/bin/env bash
# Mimo Monitor - Codex Remote Wrapper
#
# 启动 codex TUI 并连接到 mimo 管理的 app-server。
# 这样 monitor 可以精确追踪 thread 状态。
#
# 安装: alias codex='bash ~/mimo/mimo_monitor/plugins/codex_remote.sh'
# 或:   ln -sf ~/mimo/mimo_monitor/plugins/codex_remote.sh ~/.local/bin/codex-mimo

set -e

MIMO_APP_SERVER="${MIMO_CODEX_URL:-ws://127.0.0.1:9200}"

# 找到真实的 codex 二进制
find_real_codex() {
    # 如果自己被 symlink 或 alias 调用，需要跳过自己
    local self
    self="$(readlink -f "$0" 2>/dev/null || echo "$0")"

    for candidate in \
        "$HOME/.hermes/node/bin/codex" \
        "$(command -v codex.real 2>/dev/null)" \
        "$(which codex 2>/dev/null | while read -r p; do
            [ "$(readlink -f "$p" 2>/dev/null)" != "$self" ] && echo "$p" && break
        done)"; do
        if [[ -x "$candidate" ]]; then
            echo "$candidate"
            return
        fi
    done
    echo ""
}

REAL_CODEX=$(find_real_codex)

if [[ -z "$REAL_CODEX" ]]; then
    echo "[mimo] codex binary not found" >&2
    exit 1
fi

# 检查 app-server 是否在运行
if curl -sf "http://127.0.0.1:9200/readyz" >/dev/null 2>&1; then
    # app-server 在运行，用 --remote 连接
    exec "$REAL_CODEX" --remote "$MIMO_APP_SERVER" "$@"
else
    # app-server 未运行，直接启动（不连接 monitor）
    echo "[mimo] app-server not running at $MIMO_APP_SERVER, starting codex without monitoring" >&2
    exec "$REAL_CODEX" "$@"
fi
