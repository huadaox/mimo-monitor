#!/usr/bin/env bash
# Install codex wrapper to ~/.local/bin/codex
set -e

WRAPPER_SRC="$(cd "$(dirname "$0")" && pwd)/wrapper.sh"
WRAPPER_DST="${HOME}/.local/bin/codex"

echo "🔧 Installing Codex wrapper for mimo_monitor..."

# Ensure ~/.local/bin exists
mkdir -p "${HOME}/.local/bin"

# Check real codex exists
REAL_CODEX="/snap/bin/codex"
if [ ! -x "${REAL_CODEX}" ]; then
  # Try which
  REAL_CODEX="$(which codex 2>/dev/null || true)"
  if [ -z "${REAL_CODEX}" ]; then
    echo "❌ Could not find codex binary. Please install Codex first."
    exit 1
  fi
fi

# Update wrapper with actual codex path if different
if [ "${REAL_CODEX}" != "/snap/bin/codex" ]; then
  sed "s|/snap/bin/codex|${REAL_CODEX}|g" "${WRAPPER_SRC}" > "${WRAPPER_DST}"
else
  cp "${WRAPPER_SRC}" "${WRAPPER_DST}"
fi

chmod +x "${WRAPPER_DST}"

# Ensure ~/.local/bin is in PATH
SHELL_RC="${HOME}/.bashrc"
if [ -n "${ZSH_VERSION}" ]; then
  SHELL_RC="${HOME}/.zshrc"
fi

if ! echo "${PATH}" | tr ':' '\n' | grep -q "^${HOME}/.local/bin$"; then
  echo "" >> "${SHELL_RC}"
  echo "# Added by mimo_monitor codex wrapper" >> "${SHELL_RC}"
  echo 'export PATH="${HOME}/.local/bin:${PATH}"' >> "${SHELL_RC}"
  echo "   Added ~/.local/bin to PATH in ${SHELL_RC}"
fi

echo "✅ Codex wrapper installed to ${WRAPPER_DST}"
echo "   Real codex: ${REAL_CODEX}"
echo ""
echo "⚠️  Make sure mimo_monitor server is running on port 9100."
echo "   Run 'hash -r' or open a new terminal to pick up the wrapper."
