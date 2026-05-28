#!/bin/bash
# install.sh - 一键安装 mimo TUI 监控
#
# 安装后，claude/opencode/codex 命令自动带状态监控，完全无感

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
HOOK_C="$SCRIPT_DIR/mimo_hook.c"
HOOK_SO="$SCRIPT_DIR/mimo_hook.so"
HOOK_SH="$SCRIPT_DIR/mimo-hook.sh"

echo "=========================================="
echo "  Mimo TUI 监控安装"
echo "=========================================="
echo ""

# 1. 编译 hook 库
echo "[1/3] 编译 hook 库..."
if command -v gcc &>/dev/null; then
    gcc -shared -fPIC -o "$HOOK_SO" "$HOOK_C" -ldl
    echo "  ✅ 编译成功: $HOOK_SO"
else
    echo "  ❌ gcc 未安装，无法编译"
    echo "  请安装 gcc: sudo apt install gcc"
    exit 1
fi

# 2. 检测 shell
echo "[2/3] 检测 shell..."
SHELL_RC=""
if [[ -n "$ZSH_VERSION" ]]; then
    SHELL_RC="$HOME/.zshrc"
elif [[ -n "$BASH_VERSION" ]]; then
    SHELL_RC="$HOME/.bashrc"
else
    SHELL_RC="$HOME/.bashrc"
fi
echo "  Shell: $SHELL_RC"

# 3. 添加到 shell 配置
echo "[3/3] 配置 shell..."
HOOK_LINE="source $HOOK_SH"

if grep -q "mimo-hook.sh" "$SHELL_RC" 2>/dev/null; then
    echo "  ⚠️  已存在，跳过"
else
    echo "" >> "$SHELL_RC"
    echo "# Mimo TUI 监控 (自动添加)" >> "$SHELL_RC"
    echo "$HOOK_LINE" >> "$SHELL_RC"
    echo "  ✅ 已添加到 $SHELL_RC"
fi

echo ""
echo "=========================================="
echo "  安装完成！"
echo "=========================================="
echo ""
echo "使用方法："
echo "  1. 重新加载 shell: source $SHELL_RC"
echo "  2. 直接使用原命令:"
echo "     claude \"你的问题\""
echo "     opencode"
echo "     codex"
echo ""
echo "状态会自动上报到 mimo monitor"
echo ""
echo "卸载："
echo "  编辑 $SHELL_RC，删除 mimo-hook.sh 相关行"
