#!/bin/bash
set -euo pipefail

LABEL="com.correctcaptions.watcher"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"

launchctl bootout "gui/$(id -u)/$LABEL" >/dev/null 2>&1 || true
launchctl disable "gui/$(id -u)/$LABEL" >/dev/null 2>&1 || true
rm -f "$PLIST"

echo "Uninstalled LaunchAgent $LABEL"
echo "Optional cleanup: remove $HOME/.correctcaptions.env and $HOME/.correctcaptions_state.json"
