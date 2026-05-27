#!/usr/bin/env bash
# Install mimo-monitor plugin into OpenCode configuration
set -e

PLUGIN_DIR="$(cd "$(dirname "$0")" && pwd)"
OPENCODE_CONFIG_DIR="${HOME}/.config/opencode"

echo "🔧 Installing mimo-monitor plugin for OpenCode..."
echo "   Plugin source: ${PLUGIN_DIR}"

# Create config directory if needed
mkdir -p "${OPENCODE_CONFIG_DIR}"

# Create or update opencode config
CONFIG_FILE="${OPENCODE_CONFIG_DIR}/config.json"

if [ -f "${CONFIG_FILE}" ]; then
  # Backup existing config
  cp "${CONFIG_FILE}" "${CONFIG_FILE}.bak.$(date +%s)"
  echo "   Backed up existing config to ${CONFIG_FILE}.bak.*"
fi

# Write plugin reference into opencode config
# OpenCode loads plugins from the config file
cat > "${CONFIG_FILE}" << 'CONFIGEOF'
{
  "plugins": [
    {
      "name": "mimo-monitor",
      "path": "PLUGIN_DIR_PLACEHOLDER/plugin.ts"
    }
  ]
}
CONFIGEOF

# Replace placeholder with actual path
sed -i "s|PLUGIN_DIR_PLACEHOLDER|${PLUGIN_DIR}|g" "${CONFIG_FILE}"

echo "✅ mimo-monitor plugin installed successfully!"
echo "   Config written to: ${CONFIG_FILE}"
echo ""
echo "⚠️  Make sure mimo_monitor server is running on port 9100 before using OpenCode."
