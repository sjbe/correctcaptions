# CorrectCaptions (Local Getty Caption Corrector)

Automatically rewrites caption metadata for newly downloaded Getty images on Mac.

## Team Mode (Option 1: shared server key)
Use one central rewrite API with one OpenAI key, and let teammates install the watcher without personal keys.

### 1. Deploy the rewrite API once
Run on your server (or Render) with env vars:
- `OPENAI_API_KEY` = your shared OpenAI key
- `REWRITE_API_TOKEN` = shared secret token for watcher auth
- `CONFIG_PATH` = optional, default `config.yaml`

Start command:
```bash
gunicorn --bind 0.0.0.0:${PORT:-5051} src.rewrite_api:app
```

Or deploy with Docker using `Dockerfile.rewrite-api`.

Health check:
```bash
GET /health
```

Rewrite endpoint (authenticated):
```bash
POST /rewrite
Authorization: Bearer <REWRITE_API_TOKEN>
Content-Type: application/json
{"caption":"...","metadata":{"source":"..."}}
```

### 2. Teammate install (no personal OpenAI key)
1. Open Finder: `/Users/sbecket/Documents/New project/macos`
2. Double-click `install.command`
3. Choose shared API mode
4. Enter:
- `REWRITE_API_URL` (example: `https://your-api.onrender.com`)
- `REWRITE_API_TOKEN`

Done. It starts automatically at login.

## Solo Mode (local key)
If you prefer local-only, install and provide `OPENAI_API_KEY` in `install.command`.

## Status / Uninstall
- Status + logs: `/Users/sbecket/Documents/New project/macos/status.command`
- Uninstall: `/Users/sbecket/Documents/New project/macos/uninstall.command`

## Manual Run (optional)
```bash
cd "/Users/sbecket/Documents/New project"
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python3 src/caption_only_watcher.py --downloads ~/Downloads --config config.yaml
```

## Files
- Watcher: `src/caption_only_watcher.py`
- Rewrite API: `src/rewrite_api.py`
- Metadata I/O: `src/metadata_utils.py`
- OpenAI rewrite helper: `src/caption_rewriter.py`
