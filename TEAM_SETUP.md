# CorrectCaptions Team Rollout

## Owner setup (one time)
1. Deploy the rewrite API (`src/rewrite_api.py`) to Render (or any host).
2. Set environment variables on the API service:
   - `OPENAI_API_KEY`
   - `REWRITE_API_TOKEN` (long random secret)
3. Use start command:
   - `gunicorn --bind 0.0.0.0:${PORT:-5051} src.rewrite_api:app`
4. Confirm health URL works:
   - `https://YOUR-API-URL/health`

## Teammate install (Mac)
1. Send this project folder (or repo clone instructions) to teammate.
2. Teammate opens `macos/install.command`.
3. Teammate chooses shared API mode.
4. Teammate enters:
   - `REWRITE_API_URL`
   - `REWRITE_API_TOKEN`
5. Done. It auto-runs at login.

## Verify it works
1. Download a Getty image.
2. Run `macos/status.command`.
3. Look for `Caption corrected: <filename>` in logs.

## Support commands
- Status/logs: `macos/status.command`
- Uninstall: `macos/uninstall.command`
