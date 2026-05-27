#!/usr/bin/env bash
# Install mimo-monitor plugin into OpenCode configuration
set -e

PLUGIN_DIR="$(cd "$(dirname "$0")" && pwd)"
OPENCODE_CONFIG_DIR="${HOME}/.config/opencode"
CONFIG_FILE="${OPENCODE_CONFIG_DIR}/opencode.jsonc"

echo "Installing mimo-monitor plugin for OpenCode..."
echo "   Plugin source: ${PLUGIN_DIR}"

# Create config directory if needed
mkdir -p "${OPENCODE_CONFIG_DIR}"

# Read existing config or create empty
if [ -f "${CONFIG_FILE}" ]; then
  cp "${CONFIG_FILE}" "${CONFIG_FILE}.bak.$(date +%s)"
  echo "   Backed up existing config"
fi

# Write config with plugin reference
# OpenCode loads plugins from the "plugin" array in config
cat > "${CONFIG_FILE}" << CONFIGEOF
{
  "\$schema": "https://opencode.ai/config.json",
  "plugin": [
    "${PLUGIN_DIR}/plugin.ts"
  ]
}
CONFIGEOF

echo "✅ Plugin config written to: ${CONFIG_FILE}"
echo ""
echo "⚠️  Make sure mimo_monitor server is running on port 9100 before using OpenCode."
echo "   Start it with: cd ~/mimo && .venv/bin/python main.py"
