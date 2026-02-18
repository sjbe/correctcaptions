#!/bin/bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
ENV_FILE="$HOME/.correctcaptions.env"

if [ -f "$ENV_FILE" ]; then
  set -a
  # shellcheck disable=SC1090
  source "$ENV_FILE"
  set +a
fi

if [ -z "${OPENAI_API_KEY:-}" ]; then
  echo "OPENAI_API_KEY is not set. Add it to $ENV_FILE" >&2
  exit 1
fi

DOWNLOADS_DIR="${DOWNLOADS_DIR:-$HOME/Downloads}"
POLL_SECONDS="${POLL_SECONDS:-2.0}"
STATE_FILE="${STATE_FILE:-$HOME/.correctcaptions_state.json}"

exec "$PROJECT_DIR/.venv/bin/python" -u \
  "$PROJECT_DIR/src/caption_only_watcher.py" \
  --downloads "$DOWNLOADS_DIR" \
  --config "$PROJECT_DIR/config.yaml" \
  --state "$STATE_FILE" \
  --poll "$POLL_SECONDS"
