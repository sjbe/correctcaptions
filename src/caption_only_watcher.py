#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import time
from pathlib import Path

import requests
import yaml

try:
    from caption_rewriter import rewrite_caption_with_openai
    from metadata_utils import inject_caption_metadata, is_probably_getty, read_image_metadata
except Exception:  # pragma: no cover
    from src.caption_rewriter import rewrite_caption_with_openai
    from src.metadata_utils import inject_caption_metadata, is_probably_getty, read_image_metadata


def load_config(path: Path) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def rewrite_via_api(
    original_caption: str, metadata: dict[str, str], api_url: str, api_token: str
) -> tuple[str, str]:
    try:
        resp = requests.post(
            f"{api_url.rstrip('/')}/rewrite",
            json={"caption": original_caption, "metadata": metadata},
            headers={"Authorization": f"Bearer {api_token}"},
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        return (data.get("caption") or original_caption).strip(), data.get("reason", "")
    except Exception as exc:
        return original_caption.strip(), f"Rewrite API request failed: {exc}"


def rewrite_caption(
    original_caption: str, metadata: dict[str, str], cfg: dict, api_url: str, api_token: str
) -> tuple[str, str]:
    if api_url and api_token:
        rewritten, reason = rewrite_via_api(original_caption, metadata, api_url, api_token)
        if rewritten.strip() != original_caption.strip():
            return rewritten, ""
        if "Unauthorized" in reason:
            return original_caption.strip(), reason

    key = os.getenv("OPENAI_API_KEY", "")
    caption_cfg = cfg.get("caption", {})
    instructions = caption_cfg.get("instructions", "Rewrite to concise factual caption.")
    max_words = int(caption_cfg.get("max_words", 45))
    model = caption_cfg.get("openai_model", "gpt-4.1-mini")
    return rewrite_caption_with_openai(
        original_caption=original_caption,
        metadata=metadata,
        instructions=instructions,
        model=model,
        max_words=max_words,
        api_key=key,
    )


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
    parser.add_argument("--rewrite-api-url", default=os.getenv("REWRITE_API_URL", ""))
    parser.add_argument("--rewrite-api-token", default=os.getenv("REWRITE_API_TOKEN", ""))
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

            new_caption, reason = rewrite_caption(
                original_caption, metadata, cfg, args.rewrite_api_url, args.rewrite_api_token
            )
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
