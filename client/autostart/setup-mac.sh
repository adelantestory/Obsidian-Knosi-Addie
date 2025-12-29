#!/bin/bash
#
# Knosi Sync - macOS Auto-start Setup
# Installs a launchd agent to run knosi-sync.py at login
#

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PLIST_NAME="ai.knosi.sync"
PLIST_PATH="$HOME/Library/LaunchAgents/${PLIST_NAME}.plist"

echo "Knosi Sync - macOS Auto-start Setup"
echo "===================================="
echo

# Check if already installed
if [ -f "$PLIST_PATH" ]; then
    echo "Existing installation found."
    read -p "Uninstall and reinstall? (y/n): " choice
    if [ "$choice" = "y" ]; then
        echo "Unloading existing agent..."
        launchctl unload "$PLIST_PATH" 2>/dev/null || true
        rm "$PLIST_PATH"
    else
        echo "Aborted."
        exit 0
    fi
fi

# Get configuration
echo
read -p "Server URL (e.g., http://your-server:48550): " SERVER_URL
read -p "Vault path (e.g., ~/Documents/vault): " VAULT_PATH
read -p "API key (leave empty if not required): " API_KEY

# Expand ~ in vault path
VAULT_PATH="${VAULT_PATH/#\~/$HOME}"

# Verify vault path exists
if [ ! -d "$VAULT_PATH" ]; then
    echo "Error: Vault path does not exist: $VAULT_PATH"
    exit 1
fi

# Find Python
PYTHON_PATH=$(which python3)
if [ -z "$PYTHON_PATH" ]; then
    echo "Error: python3 not found in PATH"
    exit 1
fi

# Find knosi-sync.py
SYNC_SCRIPT="$SCRIPT_DIR/../knosi-sync.py"
if [ ! -f "$SYNC_SCRIPT" ]; then
    echo "Error: knosi-sync.py not found at $SYNC_SCRIPT"
    exit 1
fi
SYNC_SCRIPT="$(cd "$(dirname "$SYNC_SCRIPT")" && pwd)/$(basename "$SYNC_SCRIPT")"

# Build arguments
ARGS="<string>$PYTHON_PATH</string>
		<string>$SYNC_SCRIPT</string>
		<string>--server</string>
		<string>$SERVER_URL</string>
		<string>--vault</string>
		<string>$VAULT_PATH</string>"

if [ -n "$API_KEY" ]; then
    ARGS="$ARGS
		<string>--api-key</string>
		<string>$API_KEY</string>"
fi

# Create plist
mkdir -p "$HOME/Library/LaunchAgents"

cat > "$PLIST_PATH" << PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
	<key>Label</key>
	<string>${PLIST_NAME}</string>
	<key>ProgramArguments</key>
	<array>
		$ARGS
	</array>
	<key>RunAtLoad</key>
	<true/>
	<key>KeepAlive</key>
	<true/>
	<key>StandardOutPath</key>
	<string>/tmp/knosi-sync.log</string>
	<key>StandardErrorPath</key>
	<string>/tmp/knosi-sync.error.log</string>
	<key>WorkingDirectory</key>
	<string>$HOME</string>
</dict>
</plist>
PLIST

echo
echo "Created: $PLIST_PATH"

# Load agent
echo "Loading launch agent..."
launchctl load "$PLIST_PATH"

echo
echo "✅ Installation complete!"
echo
echo "The sync service will now:"
echo "  - Start automatically at login"
echo "  - Restart if it crashes"
echo "  - Log to /tmp/knosi-sync.log"
echo
echo "Useful commands:"
echo "  View logs:     tail -f /tmp/knosi-sync.log"
echo "  Stop service:  launchctl unload $PLIST_PATH"
echo "  Start service: launchctl load $PLIST_PATH"
echo "  Uninstall:     launchctl unload $PLIST_PATH && rm $PLIST_PATH"
