#!/bin/bash
set -euo pipefail

LABEL="com.correctcaptions.watcher"
LOG_OUT="$HOME/Library/Logs/correctcaptions.log"
LOG_ERR="$HOME/Library/Logs/correctcaptions.error.log"

echo "LaunchAgent status:"
launchctl print "gui/$(id -u)/$LABEL" | head -n 40 || true

echo ""
echo "Recent watcher log:"
tail -n 20 "$LOG_OUT" 2>/dev/null || echo "No stdout log yet."

echo ""
echo "Recent watcher errors:"
tail -n 20 "$LOG_ERR" 2>/dev/null || echo "No stderr log yet."
