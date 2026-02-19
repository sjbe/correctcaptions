#!/usr/bin/env python3
from __future__ import annotations

import os
from pathlib import Path

import yaml
from flask import Flask, Response, jsonify, request

try:
    from caption_rewriter import rewrite_caption_with_openai
except ModuleNotFoundError:  # pragma: no cover
    from src.caption_rewriter import rewrite_caption_with_openai

app = Flask(__name__)
CONFIG_PATH = Path(os.getenv("CONFIG_PATH", "config.yaml"))
REWRITE_API_TOKEN = os.getenv("REWRITE_API_TOKEN", "")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")


def load_config() -> dict:
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except Exception:
        return {}


def authorized() -> bool:
    if not REWRITE_API_TOKEN:
        return False
    bearer = request.headers.get("Authorization", "")
    if bearer.lower().startswith("bearer "):
        token = bearer.split(" ", 1)[1].strip()
    else:
        token = request.headers.get("X-API-Token", "")
    return token == REWRITE_API_TOKEN


@app.get("/health")
def health():
    return {
        "ok": True,
        "config_path": str(CONFIG_PATH),
        "has_openai_key": bool(OPENAI_API_KEY),
        "has_api_token": bool(REWRITE_API_TOKEN),
    }


@app.post("/rewrite")
def rewrite():
    if not authorized():
        return Response("Unauthorized", status=401)

    payload = request.get_json(silent=True) or {}
    original_caption = (payload.get("caption") or "").strip()
    metadata = payload.get("metadata") or {}
    if not original_caption:
        return Response("caption is required", status=400)

    cfg = load_config()
    caption_cfg = cfg.get("caption", {})
    instructions = caption_cfg.get("instructions", "Rewrite to concise factual caption.")
    model = caption_cfg.get("openai_model", "gpt-4.1-mini")
    max_words = int(caption_cfg.get("max_words", 45))

    rewritten, reason = rewrite_caption_with_openai(
        original_caption=original_caption,
        metadata=metadata,
        instructions=instructions,
        model=model,
        max_words=max_words,
        api_key=OPENAI_API_KEY,
    )
    return jsonify(
        {
            "caption": rewritten,
            "changed": rewritten.strip() != original_caption.strip(),
            "reason": reason,
        }
    )


if __name__ == "__main__":
    host = os.getenv("HOST", "127.0.0.1")
    port = int(os.getenv("PORT", "5051"))
    debug = os.getenv("FLASK_DEBUG", "0") == "1"
    app.run(host=host, port=port, debug=debug)
