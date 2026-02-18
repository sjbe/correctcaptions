#!/bin/bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
LABEL="com.correctcaptions.watcher"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
ENV_FILE="$HOME/.correctcaptions.env"
LOG_OUT="$HOME/Library/Logs/correctcaptions.log"
LOG_ERR="$HOME/Library/Logs/correctcaptions.error.log"

mkdir -p "$HOME/Library/LaunchAgents"
mkdir -p "$HOME/Library/Logs"

printf "Installing dependencies...\n"
cd "$PROJECT_DIR"
if [ ! -d ".venv" ]; then
  python3 -m venv .venv
fi
"$PROJECT_DIR/.venv/bin/pip" install -r requirements.txt

if [ -z "${OPENAI_API_KEY:-}" ]; then
  if [ -f "$ENV_FILE" ]; then
    # shellcheck disable=SC1090
    source "$ENV_FILE"
  fi
fi

if [ -z "${OPENAI_API_KEY:-}" ]; then
  printf "Enter OPENAI_API_KEY: "
  read -r OPENAI_API_KEY
fi

if [ -z "$OPENAI_API_KEY" ]; then
  echo "OPENAI_API_KEY is required."
  exit 1
fi

cat > "$ENV_FILE" <<ENV
OPENAI_API_KEY="$OPENAI_API_KEY"
DOWNLOADS_DIR="$HOME/Downloads"
POLL_SECONDS="2.0"
STATE_FILE="$HOME/.correctcaptions_state.json"
ENV
chmod 600 "$ENV_FILE"

cat > "$PLIST" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>$LABEL</string>
  <key>ProgramArguments</key>
  <array>
    <string>/bin/bash</string>
    <string>$PROJECT_DIR/macos/run_watcher.sh</string>
  </array>
  <key>RunAtLoad</key>
  <true/>
  <key>KeepAlive</key>
  <true/>
  <key>StandardOutPath</key>
  <string>$LOG_OUT</string>
  <key>StandardErrorPath</key>
  <string>$LOG_ERR</string>
</dict>
</plist>
PLIST

launchctl bootout "gui/$(id -u)/$LABEL" >/dev/null 2>&1 || true
launchctl bootstrap "gui/$(id -u)" "$PLIST"
launchctl enable "gui/$(id -u)/$LABEL"
launchctl kickstart -k "gui/$(id -u)/$LABEL"

printf "Installed. Status:\n"
launchctl print "gui/$(id -u)/$LABEL" | head -n 20 || true
printf "\nDone. The watcher now runs automatically at login.\n"
printf "Logs: %s and %s\n" "$LOG_OUT" "$LOG_ERR"
