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

if [ -z "${REWRITE_API_URL:-}" ] && [ -z "${OPENAI_API_KEY:-}" ]; then
  echo "Set REWRITE_API_URL+REWRITE_API_TOKEN or OPENAI_API_KEY in $ENV_FILE" >&2
  exit 1
fi
if [ -n "${REWRITE_API_URL:-}" ] && [ -z "${REWRITE_API_TOKEN:-}" ]; then
  echo "REWRITE_API_URL is set but REWRITE_API_TOKEN is missing in $ENV_FILE" >&2
  exit 1
fi

DOWNLOADS_DIR="${DOWNLOADS_DIR:-$HOME/Downloads}"
POLL_SECONDS="${POLL_SECONDS:-2.0}"
STATE_FILE="${STATE_FILE:-$HOME/.correctcaptions_state.json}"

ARGS=(
  --downloads "$DOWNLOADS_DIR"
  --config "$PROJECT_DIR/config.yaml"
  --state "$STATE_FILE"
  --poll "$POLL_SECONDS"
)
if [ -n "${REWRITE_API_URL:-}" ]; then
  ARGS+=(--rewrite-api-url "$REWRITE_API_URL" --rewrite-api-token "$REWRITE_API_TOKEN")
fi

exec "$PROJECT_DIR/.venv/bin/python" -u \
  "$PROJECT_DIR/src/caption_only_watcher.py" \
  "${ARGS[@]}"
