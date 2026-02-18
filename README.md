# CorrectCaptions (Getty Download Auto-Caption)

This project is now local-only.

It automatically rewrites caption metadata for newly downloaded Getty images on your Mac.

## One-Time Install (No Terminal Needed After)
1. Open Finder: `/Users/sbecket/Documents/New project/macos`
2. Double-click `install.command`
3. Paste your `OPENAI_API_KEY` when prompted
4. Done. It starts at login automatically.

## Check / Stop
- Status + logs: `/Users/sbecket/Documents/New project/macos/status.command`
- Uninstall: `/Users/sbecket/Documents/New project/macos/uninstall.command`

## Manual Run (Optional)
```bash
cd "/Users/sbecket/Documents/New project"
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export OPENAI_API_KEY="your_key_here"
python3 src/caption_only_watcher.py --downloads ~/Downloads --config config.yaml
```

## Notes
- Caption rules come from `config.yaml` (`caption.instructions`, model, max words).
- Only probable Getty images are processed by default.
- Use your own OpenAI API key; do not share `~/.correctcaptions.env`.
