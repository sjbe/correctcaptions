#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import time
from pathlib import Path

try:
    from metadata_utils import inject_caption_metadata
except Exception:  # pragma: no cover
    from src.metadata_utils import inject_caption_metadata

STOPWORDS = {
    "the",
    "and",
    "for",
    "with",
    "from",
    "photo",
    "image",
    "getty",
    "images",
    "news",
}


def tokenize(text: str) -> set[str]:
    return {t for t in re.findall(r"[a-z0-9]{3,}", text.lower()) if t not in STOPWORDS}


def load_pending(path: Path) -> list[dict]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except FileNotFoundError:
        return []
    except Exception:
        return []


def save_pending(path: Path, entries: list[dict]) -> None:
    path.write_text(json.dumps(entries[-500:], ensure_ascii=False, indent=2), encoding="utf-8")


def score_match(filename: str, entry: dict) -> float:
    name_tokens = tokenize(filename)
    if not name_tokens:
        return 0.0
    title_tokens = tokenize(entry.get("title", ""))
    caption_tokens = tokenize(entry.get("caption", ""))
    target = title_tokens | set(list(caption_tokens)[:8])
    if not target:
        return 0.0

    overlap = len(name_tokens & target) / max(len(target), 1)
    asset_id = (entry.get("asset_id") or "").strip()
    if asset_id and asset_id in filename:
        overlap += 1.0
    return overlap


def find_best_match(downloads: list[Path], pending: list[dict], processed: set[str]) -> tuple[Path | None, int | None]:
    best_score = 0.0
    best_file = None
    best_idx = None

    for idx, entry in enumerate(pending):
        if entry.get("matched"):
            continue
        caption = (entry.get("caption") or "").strip()
        if not caption:
            continue
        created_at = int(entry.get("created_at") or 0)
        if created_at and time.time() - created_at > 60 * 60 * 24:
            continue

        for file_path in downloads:
            file_key = str(file_path.resolve())
            if file_key in processed:
                continue
            score = score_match(file_path.name, entry)
            if score > best_score:
                best_score = score
                best_file = file_path
                best_idx = idx

    if best_score < 0.20:
        return None, None
    return best_file, best_idx


def inject_file(file_path: Path, caption: str, source_url: str) -> bool:
    try:
        content = file_path.read_bytes()
        out, _fmt = inject_caption_metadata(content, caption, source_url)
        file_path.write_bytes(out)
        return True
    except Exception:
        return False


def scan_downloads(downloads_dir: Path) -> list[Path]:
    exts = {".jpg", ".jpeg", ".png"}
    now = time.time()
    files: list[Path] = []
    for p in downloads_dir.iterdir():
        if not p.is_file():
            continue
        if p.suffix.lower() not in exts:
            continue
        try:
            age = now - p.stat().st_mtime
        except OSError:
            continue
        if age > 60 * 60 * 6:
            continue
        files.append(p)
    files.sort(key=lambda f: f.stat().st_mtime, reverse=True)
    return files


def main() -> None:
    parser = argparse.ArgumentParser(description="Watch Downloads and inject caption metadata after Getty download.")
    parser.add_argument("--downloads", default=str(Path.home() / "Downloads"), help="Downloads directory")
    parser.add_argument("--pending", default="pending_downloads.json", help="Pending downloads JSON path")
    parser.add_argument("--state", default="captioner_state.json", help="Processed state JSON path")
    parser.add_argument("--poll", type=float, default=2.0, help="Polling interval seconds")
    args = parser.parse_args()

    downloads_dir = Path(args.downloads).expanduser()
    pending_path = Path(args.pending)
    state_path = Path(args.state)

    try:
        processed = set(json.loads(state_path.read_text(encoding="utf-8")))
    except Exception:
        processed = set()

    print(f"Watching {downloads_dir} for new Getty downloads...")
    while True:
        pending = load_pending(pending_path)
        downloads = scan_downloads(downloads_dir)
        file_path, idx = find_best_match(downloads, pending, processed)

        if file_path is not None and idx is not None:
            entry = pending[idx]
            ok = inject_file(file_path, entry.get("caption", ""), entry.get("page_url", ""))
            key = str(file_path.resolve())
            processed.add(key)
            if ok:
                entry["matched"] = True
                entry["matched_file"] = key
                entry["matched_at"] = int(time.time())
                print(f"Caption injected: {file_path.name}")
            else:
                print(f"Failed to inject caption for: {file_path.name}")
            save_pending(pending_path, pending)
            state_path.write_text(json.dumps(sorted(processed), ensure_ascii=False, indent=2), encoding="utf-8")

        time.sleep(max(args.poll, 0.5))


if __name__ == "__main__":
    main()
