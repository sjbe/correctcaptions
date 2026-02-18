# News Photo Finder (Getty + AP)

Web app to:
- search public pages on Getty Images and AP Newsroom
- rank photo candidates using relevance + timeliness
- rewrite captions using your custom newsroom rules
- open Getty pages for authenticated download
- apply caption metadata to downloaded files with a local helper
- copy edited captions with one click
 - track Getty opens and apply captions to downloaded files locally

## Local Run
```bash
cd "/Users/sbecket/Documents/New project"
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export OPENAI_API_KEY="your_key_here"
python3 src/web_app.py
```

Open: http://127.0.0.1:5050

## Post-Download Caption Injector (for Getty-login flow)
If Getty download must happen on gettyimages.com (login enforced), run this helper locally.
It watches your Downloads folder and injects the edited caption metadata after the file appears.

Run in a second terminal:
```bash
cd "/Users/sbecket/Documents/New project"
source .venv/bin/activate
python3 src/post_download_captioner.py --downloads ~/Downloads
```

Keep it running while you work.

If your web app runs on Render, use hosted sync mode:
```bash
python3 src/post_download_captioner.py \
  --downloads ~/Downloads \
  --api-base "https://YOUR-RENDER-URL.onrender.com" \
  --api-token "YOUR_SYNC_TOKEN"
```

Set `SYNC_TOKEN` in Render environment variables to the same value.

## Deploy For Your Team (Render, easiest)
1. Push this folder to a GitHub repo.
2. In Render, create a new `Web Service` from that repo.
3. Use these settings:
   - Runtime: `Docker`
   - Instance type: your choice
   - Port: `5050`
4. Add environment variables in Render:
   - `OPENAI_API_KEY` = your API key
5. Deploy. Share the generated HTTPS URL with coworkers.

Render uses the included `/Users/sbecket/Documents/New project/Dockerfile`.

## Notes
- `config.yaml` contains your scoring and caption rules.
- Getty/AP markup can change; selectors may need occasional updates.
