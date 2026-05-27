#!/usr/bin/env bash
# mimo_monitor one-click install script
# Detects installed AI coding tools and configures monitoring hooks
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
VERSION="1.0.0"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

info()    { echo -e "${BLUE}ℹ️  $*${NC}"; }
success() { echo -e "${GREEN}✅ $*${NC}"; }
warn()    { echo -e "${YELLOW}⚠️  $*${NC}"; }
fail()    { echo -e "${RED}❌ $*${NC}"; }

# Detect installed tools
detect_tools() {
  local tools=()
  command -v claude &>/dev/null && tools+=("claude-code")
  command -v opencode &>/dev/null && tools+=("opencode")
  command -v codex &>/dev/null && tools+=("codex")
  command -v /snap/bin/codex &>/dev/null && tools+=("codex")
  echo "${tools[@]}"
}

# Install hooks for a specific tool
install_tool() {
  local tool="$1"
  case "${tool}" in
    claude-code|claude)
      info "Configuring Claude Code hook..."
      if [ -f "${SCRIPT_DIR}/claude/setup.sh" ]; then
        bash "${SCRIPT_DIR}/claude/setup.sh"
      else
        warn "Claude Code hook not found at ${SCRIPT_DIR}/claude/"
      fi
      ;;
    opencode)
      info "Configuring OpenCode hook..."
      if [ -f "${SCRIPT_DIR}/opencode/setup.sh" ]; then
        bash "${SCRIPT_DIR}/opencode/setup.sh"
      else
        warn "OpenCode hook not found at ${SCRIPT_DIR}/opencode/"
      fi
      ;;
    codex)
      info "Configuring Codex hook..."
      if [ -f "${SCRIPT_DIR}/codex/setup.sh" ]; then
        bash "${SCRIPT_DIR}/codex/setup.sh"
      else
        warn "Codex hook not found at ${SCRIPT_DIR}/codex/"
      fi
      ;;
    *)
      fail "Unknown tool: ${tool}"
      return 1
      ;;
  esac
}

# Uninstall hooks for a specific tool
uninstall_tool() {
  local tool="$1"
  case "${tool}" in
    claude-code|claude)
      info "Removing Claude Code hook..."
      local hook_file="${HOME}/.claude/hooks/mimo-monitor.sh"
      if [ -f "${hook_file}" ]; then
        rm -f "${hook_file}"
        success "Removed ${hook_file}"
      else
        warn "Claude hook not found, nothing to remove"
      fi
      ;;
    opencode)
      info "Removing OpenCode plugin..."
      local config_file="${HOME}/.config/opencode/config.json"
      if [ -f "${config_file}" ]; then
        rm -f "${config_file}"
        success "Removed ${config_file}"
      else
        warn "OpenCode config not found, nothing to remove"
      fi
      ;;
    codex)
      info "Removing Codex wrapper..."
      local wrapper="${HOME}/.local/bin/codex"
      if [ -f "${wrapper}" ]; then
        rm -f "${wrapper}"
        success "Removed ${wrapper}"
      else
        warn "Codex wrapper not found, nothing to remove"
      fi
      ;;
    *)
      fail "Unknown tool: ${tool}"
      return 1
      ;;
  esac
}

# Usage
usage() {
  echo "mimo_monitor hooks installer v${VERSION}"
  echo ""
  echo "Usage:"
  echo "  $0              Auto-detect and install all hooks"
  echo "  $0 --all        Install hooks for all supported tools"
  echo "  $0 --tool NAME  Install hook for a specific tool"
  echo "  $0 --uninstall  Remove all installed hooks"
  echo "  $0 --uninstall --tool NAME  Remove hook for a specific tool"
  echo "  $0 --status     Show detected tools and hook status"
  echo "  $0 --help       Show this help"
  echo ""
  echo "Supported tools: claude-code, opencode, codex"
}

# Show status
show_status() {
  echo ""
  echo "🔍 mimo_monitor hooks status"
  echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━"
  echo ""

  for tool in claude-code opencode codex; do
    local icon="⬜"
    local detected="not installed"
    local hook_status="not configured"

    case "${tool}" in
      claude-code)
        if command -v claude &>/dev/null; then
          detected="installed"
          icon="🟦"
        fi
        [ -f "${HOME}/.claude/hooks/mimo-monitor.sh" ] && hook_status="configured"
        ;;
      opencode)
        if command -v opencode &>/dev/null; then
          detected="installed"
          icon="🟦"
        fi
        [ -f "${HOME}/.config/opencode/config.json" ] && hook_status="configured"
        ;;
      codex)
        if command -v codex &>/dev/null || [ -x /snap/bin/codex ]; then
          detected="installed"
          icon="🟦"
        fi
        [ -f "${HOME}/.local/bin/codex" ] && hook_status="configured"
        ;;
    esac

    echo "  ${icon} ${tool}: ${detected} | hook: ${hook_status}"
  done
  echo ""
}

# Main
UNINSTALL=false
TARGET_TOOL=""
INSTALL_ALL=false

while [[ $# -gt 0 ]]; do
  case "$1" in
    --uninstall)
      UNINSTALL=true
      shift
      ;;
    --tool)
      TARGET_TOOL="$2"
      shift 2
      ;;
    --all)
      INSTALL_ALL=true
      shift
      ;;
    --status)
      show_status
      exit 0
      ;;
    --help|-h)
      usage
      exit 0
      ;;
    *)
      fail "Unknown option: $1"
      usage
      exit 1
      ;;
  esac
done

echo ""
echo "╔══════════════════════════════════════════╗"
echo "║   mimo_monitor hooks installer v${VERSION}    ║"
echo "╚══════════════════════════════════════════╝"
echo ""

if [ "${UNINSTALL}" = true ]; then
  if [ -n "${TARGET_TOOL}" ]; then
    uninstall_tool "${TARGET_TOOL}"
  else
    info "Uninstalling all hooks..."
    for tool in claude-code opencode codex; do
      uninstall_tool "${tool}" || true
    done
  fi
  echo ""
  success "Uninstall complete!"
  exit 0
fi

if [ -n "${TARGET_TOOL}" ]; then
  install_tool "${TARGET_TOOL}"
  echo ""
  success "Installation complete!"
  exit 0
fi

# Auto-detect or install all
if [ "${INSTALL_ALL}" = true ]; then
  ALL_TOOLS="claude-code opencode codex"
else
  ALL_TOOLS=$(detect_tools)
fi

if [ -z "${ALL_TOOLS}" ]; then
  warn "No supported AI coding tools detected."
  info "Install one of: claude (Claude Code), opencode, codex"
  info "Or use --all to install all hooks regardless."
  exit 0
fi

info "Detected tools: ${ALL_TOOLS}"
echo ""

for tool in ${ALL_TOOLS}; do
  install_tool "${tool}" || warn "Failed to install hook for ${tool}"
  echo ""
done

success "All hooks installed!"
echo ""
info "Make sure mimo_monitor server is running on port 9100."
echo ""
