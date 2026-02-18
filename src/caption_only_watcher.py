#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import time
from pathlib import Path

import yaml
from openai import OpenAI

try:
    from metadata_utils import inject_caption_metadata, is_probably_getty, read_image_metadata
except Exception:  # pragma: no cover
    from src.metadata_utils import inject_caption_metadata, is_probably_getty, read_image_metadata


def load_config(path: Path) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def rewrite_caption(original_caption: str, metadata: dict[str, str], cfg: dict) -> tuple[str, str]:
    key = os.getenv("OPENAI_API_KEY", "")
    if not key:
        return original_caption.strip(), "OPENAI_API_KEY missing"

    caption_cfg = cfg.get("caption", {})
    instructions = caption_cfg.get("instructions", "Rewrite to concise factual caption.")
    max_words = int(caption_cfg.get("max_words", 45))
    model = caption_cfg.get("openai_model", "gpt-4.1-mini")

    user_prompt = (
        "Rewrite this Getty photo caption using the provided rules.\n"
        f"Original caption: {original_caption}\n"
        f"Source metadata: {metadata}\n"
        f"Hard limits: max {max_words} words, output only the caption."
    )

    client = OpenAI(api_key=key)
    try:
        resp = client.responses.create(
            model=model,
            input=[
                {"role": "system", "content": instructions},
                {"role": "user", "content": user_prompt},
            ],
            max_output_tokens=200,
        )
        text = getattr(resp, "output_text", "") or ""
        text = " ".join(text.split())
        out = text or original_caption.strip()
        return out, ""
    except Exception as exc:
        return original_caption.strip(), f"OpenAI request failed: {exc}"


def scan_downloads(downloads_dir: Path, processed: set[str]) -> list[Path]:
    now = time.time()
    out: list[Path] = []
    for p in downloads_dir.iterdir():
        if not p.is_file():
            continue
        if p.suffix.lower() not in {".jpg", ".jpeg", ".png"}:
            continue
        key = str(p.resolve())
        if key in processed:
            continue
        try:
            age = now - p.stat().st_mtime
        except OSError:
            continue
        if age > 60 * 60 * 6:
            continue
        out.append(p)
    out.sort(key=lambda x: x.stat().st_mtime)
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description="Auto-correct captions for downloaded Getty images.")
    parser.add_argument("--downloads", default=str(Path.home() / "Downloads"))
    parser.add_argument("--config", default="config.yaml")
    parser.add_argument("--state", default="caption_only_state.json")
    parser.add_argument("--poll", type=float, default=2.0)
    parser.add_argument("--all-images", action="store_true", help="Process all new images, not just probable Getty files")
    parser.add_argument("--verbose", action="store_true", help="Print skip/failure reasons")
    parser.add_argument("--once", action="store_true", help="Run one scan and exit")
    args = parser.parse_args()

    downloads_dir = Path(args.downloads).expanduser()
    config_path = Path(args.config)
    state_path = Path(args.state)

    cfg = load_config(config_path)

    try:
        processed = set(json.loads(state_path.read_text(encoding="utf-8")))
    except Exception:
        processed = set()

    print(f"Watching {downloads_dir} for downloads...")
    while True:
        for file_path in scan_downloads(downloads_dir, processed):
            key = str(file_path.resolve())
            metadata = read_image_metadata(str(file_path))
            if not args.all_images and not is_probably_getty(str(file_path), metadata):
                processed.add(key)
                if args.verbose:
                    print(f"Skipped non-Getty: {file_path.name}")
                continue

            original_caption = (metadata.get("caption") or "").strip()
            if not original_caption:
                processed.add(key)
                if args.verbose:
                    print(f"Skipped no caption metadata: {file_path.name}")
                continue

            new_caption, reason = rewrite_caption(original_caption, metadata, cfg)
            new_caption = new_caption.strip()
            if not new_caption:
                processed.add(key)
                if args.verbose:
                    print(f"Skipped empty rewritten caption: {file_path.name}")
                continue

            if reason and args.verbose:
                print(f"Using original caption for {file_path.name}: {reason}")

            if new_caption == original_caption:
                processed.add(key)
                if args.verbose:
                    print(f"No caption change: {file_path.name}")
                continue

            source = metadata.get("source") or "Getty Images"
            try:
                content = file_path.read_bytes()
                payload, _fmt = inject_caption_metadata(content, new_caption, source)
                file_path.write_bytes(payload)
                print(f"Caption corrected: {file_path.name}")
            except Exception:
                print(f"Failed to update: {file_path.name}")

            processed.add(key)
            state_path.write_text(json.dumps(sorted(processed), ensure_ascii=False, indent=2), encoding="utf-8")

        if args.once:
            break
        time.sleep(max(args.poll, 0.5))


if __name__ == "__main__":
    main()
