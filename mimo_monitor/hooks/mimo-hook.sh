#!/bin/bash
# mimo-hook.sh - 无感 TUI 监控
#
# 安装方法（添加到 ~/.bashrc 或 ~/.zshrc）：
#   source /path/to/mimo-hook.sh
#
# 然后直接用原命令，自动带监控：
#   claude "你的问题"    # 自动监控
#   opencode             # 自动监控
#   codex                # 自动监控

MIMO_HOOK_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MIMO_HOOK_SO="$MIMO_HOOK_DIR/mimo_hook.so"
MIMO_API="${MIMO_API:-http://localhost:9100/api/hook}"

# 编译 hook 库（如果不存在）
if [[ ! -f "$MIMO_HOOK_SO" ]]; then
    echo "[mimo] 编译 hook 库..."
    gcc -shared -fPIC -o "$MIMO_HOOK_SO" "$MIMO_HOOK_DIR/mimo_hook.c" -ldl 2>/dev/null
fi

# 包装函数
mimo_wrap() {
    local cmd="$1"
    shift
    
    # 检查 hook 库
    if [[ -f "$MIMO_HOOK_SO" ]]; then
        export LD_PRELOAD="$MIMO_HOOK_SO"
        export MIMO_HOST="${MIMO_API#http://}"
        export MIMO_HOST="${MIMO_HOST%%:*}"
        export MIMO_PORT="${MIMO_API##*:}"
        export MIMO_PORT="${MIMO_PORT%%/*}"
    fi
    
    # 执行原命令
    command "$cmd" "$@"
}

# 创建包装命令
claude() { mimo_wrap "claude" "$@"; }
opencode() { mimo_wrap "opencode" "$@"; }
codex() { mimo_wrap "codex" "$@"; }

# 导出函数
export -f claude opencode codex mimo_wrap

echo "[mimo] TUI 监控已启用 (LD_PRELOAD: $MIMO_HOOK_SO)"
echo "[mimo] 直接使用 claude/opencode/codex 即可"
