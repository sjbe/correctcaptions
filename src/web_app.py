#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import re
import time
import uuid

from flask import Flask, Response, jsonify, redirect, render_template, request

try:
    from photo_finder import PhotoResult, load_config, run
except ModuleNotFoundError:  # pragma: no cover
    from src.photo_finder import PhotoResult, load_config, run

app = Flask(__name__)
PENDING_DOWNLOADS_FILE = os.getenv("PENDING_DOWNLOADS_FILE", "pending_downloads.json")
SYNC_TOKEN = os.getenv("SYNC_TOKEN", "")


def _search(form) -> tuple[str, int, list[PhotoResult], str, str]:
    prompt = (form.get("prompt") or "").strip()
    config_path = "config.yaml"
    top_n = int(form.get("top") or 5)

    if not prompt:
        return prompt, top_n, [], "Prompt is required.", ""

    try:
        cfg = load_config(config_path)
        results = run(prompt, cfg, top_n=top_n)
        warning = ""
        if cfg.get("caption", {}).get("mode") == "llm":
            fallback = [r for r in results if r.caption_mode_used != "llm"]
            if fallback:
                reason = fallback[0].caption_error or "LLM rewrite unavailable"
                warning = f"AI caption rules were not applied to all results. Reason: {reason}"
        return prompt, top_n, results, "", warning
    except FileNotFoundError:
        return prompt, top_n, [], f"Config not found: {config_path}", ""
    except Exception as exc:
        return prompt, top_n, [], f"Search error: {exc}", ""


def _extract_getty_asset_id(page_url: str) -> str:
    m = re.search(r"/(\d+)(?:\\?|$)", page_url)
    return m.group(1) if m else ""


def _load_pending_downloads() -> list[dict]:
    try:
        with open(PENDING_DOWNLOADS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, list) else []
    except FileNotFoundError:
        return []
    except Exception:
        return []


def _save_pending_downloads(entries: list[dict]) -> None:
    with open(PENDING_DOWNLOADS_FILE, "w", encoding="utf-8") as f:
        json.dump(entries[-500:], f, ensure_ascii=False, indent=2)


def _track_pending_download(page_url: str, title: str, caption: str) -> None:
    entries = _load_pending_downloads()
    entries.append(
        {
            "id": str(uuid.uuid4()),
            "page_url": page_url,
            "title": title,
            "caption": caption,
            "asset_id": _extract_getty_asset_id(page_url),
            "created_at": int(time.time()),
            "matched": False,
            "matched_file": "",
        }
    )
    _save_pending_downloads(entries)


def _authorized(req) -> bool:
    if not SYNC_TOKEN:
        return False
    token = (
        req.headers.get("X-Sync-Token", "")
        or req.args.get("token", "")
        or req.form.get("token", "")
    )
    return token == SYNC_TOKEN


@app.get("/")
def home():
    return render_template(
        "index.html",
        results=[],
        prompt="",
        top=5,
        error="",
        warning="",
    )


@app.post("/search")
def search():
    prompt, top_n, results, error, warning = _search(request.form)
    return render_template(
        "index.html",
        results=results,
        prompt=prompt,
        top=top_n,
        error=error,
        warning=warning,
    )


@app.get("/open/getty")
def open_getty():
    page_url = (request.args.get("page_url") or "").strip()
    title = (request.args.get("title") or "").strip()
    caption = (request.args.get("caption") or "").strip()
    if not page_url:
        return Response("Missing Getty URL.", status=400)
    _track_pending_download(page_url, title, caption)
    return redirect(page_url, code=302)


@app.get("/api/pending")
def api_pending():
    if not _authorized(request):
        return Response("Unauthorized", status=401)
    entries = _load_pending_downloads()
    recent = [e for e in entries if not e.get("matched")]
    recent.sort(key=lambda e: int(e.get("created_at") or 0), reverse=True)
    return jsonify({"pending": recent[:200]})


@app.post("/api/pending/mark")
def api_pending_mark():
    if not _authorized(request):
        return Response("Unauthorized", status=401)
    item_id = (request.form.get("id") or "").strip()
    matched_file = (request.form.get("matched_file") or "").strip()
    if not item_id:
        return Response("Missing id", status=400)
    entries = _load_pending_downloads()
    for entry in entries:
        if entry.get("id") == item_id:
            entry["matched"] = True
            entry["matched_file"] = matched_file
            entry["matched_at"] = int(time.time())
            break
    _save_pending_downloads(entries)
    return jsonify({"ok": True})


if __name__ == "__main__":
    host = os.getenv("HOST", "127.0.0.1")
    port = int(os.getenv("PORT", "5050"))
    debug = os.getenv("FLASK_DEBUG", "1") == "1"
    app.run(host=host, port=port, debug=debug)
