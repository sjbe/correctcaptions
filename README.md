# News Photo Finder (Getty + AP)

Web app to:
- search public pages on Getty Images and AP Newsroom
- rank photo candidates using relevance + timeliness
- rewrite captions using your custom newsroom rules
- download Getty photos with caption metadata embedded
- copy edited captions with one click

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
