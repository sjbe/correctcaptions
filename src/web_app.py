#!/usr/bin/env python3
from __future__ import annotations

import io
import os
import re
import tempfile
from urllib.parse import parse_qs, urlparse

import requests
from bs4 import BeautifulSoup
from flask import Flask, Response, render_template, request

try:
    import piexif
    import piexif.helper
    from iptcinfo3 import IPTCInfo
    from PIL import Image, PngImagePlugin
except Exception:  # pragma: no cover
    piexif = None
    IPTCInfo = None
    Image = None
    PngImagePlugin = None

try:
    from photo_finder import PhotoResult, load_config, run
except ModuleNotFoundError:  # pragma: no cover
    from src.photo_finder import PhotoResult, load_config, run

app = Flask(__name__)


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


def _safe_filename(text: str) -> str:
    base = re.sub(r"[^A-Za-z0-9._-]+", "_", text).strip("._")
    return base[:80] or "photo"


def _extract_getty_candidates(detail_html: str) -> list[str]:
    soup = BeautifulSoup(detail_html, "html.parser")
    candidates: list[str] = []

    for node in soup.select('meta[property="og:image"]'):
        value = (node.get("content") or "").strip()
        if value:
            candidates.append(value)

    for match in re.findall(r"https?://[^\"'\\s>]+\\.(?:jpg|jpeg|png)(?:\\?[^\"'\\s>]*)?", detail_html, re.I):
        if "gettyimages" in match or "media" in match:
            candidates.append(match)

    # keep ordering, drop duplicates
    seen = set()
    ordered: list[str] = []
    for url in candidates:
        if url in seen:
            continue
        seen.add(url)
        ordered.append(url)
    return ordered


def _width_hint(url: str) -> int:
    qs = parse_qs(urlparse(url).query)
    width = qs.get("w", ["0"])[0]
    try:
        return int(width)
    except ValueError:
        return 0


def _pick_best_getty_url(urls: list[str], fallback_url: str) -> str:
    if not urls:
        return fallback_url
    # Prefer URL that explicitly says medium, otherwise pick largest width hint.
    medium = [u for u in urls if "medium" in u.lower()]
    if medium:
        return medium[0]
    return sorted(urls, key=_width_hint, reverse=True)[0]


def _resolve_getty_download_url(detail_url: str, fallback_url: str) -> str:
    try:
        resp = requests.get(detail_url, timeout=20)
        resp.raise_for_status()
    except requests.RequestException:
        return fallback_url
    candidates = _extract_getty_candidates(resp.text)
    return _pick_best_getty_url(candidates, fallback_url)


def _short_source_label(source_url: str) -> str:
    if "gettyimages.com" in source_url:
        return "Getty Images"
    return source_url


def _inject_iptc_jpeg(content: bytes, caption: str, source_url: str) -> bytes:
    if IPTCInfo is None:
        return content
    try:
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
            tmp.write(content)
            tmp_path = tmp.name
        try:
            info = IPTCInfo(tmp_path, force=True)
            info["caption/abstract"] = caption
            info["credit"] = _short_source_label(source_url)
            info["source"] = _short_source_label(source_url)
            info["object name"] = caption[:64]
            info["headline"] = caption[:256]
            info["special instructions"] = source_url[:200]
            info.save()
            with open(tmp_path, "rb") as f:
                return f.read()
        finally:
            try:
                os.remove(tmp_path)
            except OSError:
                pass
    except Exception:
        return content


def _inject_caption_metadata(content: bytes, caption: str, source_url: str) -> tuple[bytes, str]:
    if Image is None or piexif is None:
        if content[:3] == b"\xff\xd8\xff":
            return content, "JPEG"
        if content[:8] == b"\x89PNG\r\n\x1a\n":
            return content, "PNG"
        return content, "BIN"
    bio = io.BytesIO(content)
    with Image.open(bio) as im:
        fmt = (im.format or "").upper()
        caption = caption.strip()
        if not caption:
            return content, fmt or "BIN"

        if fmt in {"JPEG", "JPG"}:
            exif_bytes = im.info.get("exif", b"")
            exif_dict = piexif.load(exif_bytes) if exif_bytes else {"0th": {}, "Exif": {}, "GPS": {}, "1st": {}, "thumbnail": None}
            exif_dict["0th"][piexif.ImageIFD.ImageDescription] = caption.encode("utf-8", errors="ignore")
            exif_dict["0th"][piexif.ImageIFD.XPSubject] = caption.encode("utf-16le", errors="ignore")
            exif_dict["Exif"][piexif.ExifIFD.UserComment] = piexif.helper.UserComment.dump(caption, encoding="unicode")
            exif_dict["0th"][piexif.ImageIFD.Artist] = _short_source_label(source_url).encode("utf-8", errors="ignore")
            exif_dict["0th"][piexif.ImageIFD.Copyright] = f"Source: {source_url}".encode("utf-8", errors="ignore")
            out = io.BytesIO()
            im.save(out, format="JPEG", exif=piexif.dump(exif_dict), quality=95)
            jpeg_with_exif = out.getvalue()
            jpeg_with_iptc = _inject_iptc_jpeg(jpeg_with_exif, caption, source_url)
            return jpeg_with_iptc, "JPEG"

        if fmt == "PNG":
            pnginfo = PngImagePlugin.PngInfo()
            pnginfo.add_text("Description", caption)
            pnginfo.add_text("Source", source_url)
            out = io.BytesIO()
            im.save(out, format="PNG", pnginfo=pnginfo)
            return out.getvalue(), "PNG"

    return content, fmt or "BIN"


def _mime_for(fmt: str) -> str:
    if fmt == "JPEG":
        return "image/jpeg"
    if fmt == "PNG":
        return "image/png"
    return "application/octet-stream"


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


@app.post("/download/getty")
def download_getty():
    detail_url = (request.form.get("page_url") or "").strip()
    fallback_image_url = (request.form.get("image_url") or "").strip()
    edited_caption = (request.form.get("edited_caption") or "").strip()
    title = (request.form.get("title") or "").strip()

    if not fallback_image_url:
        return Response("Missing image URL.", status=400)

    download_url = _resolve_getty_download_url(detail_url, fallback_image_url)
    try:
        img_resp = requests.get(download_url, timeout=25)
        img_resp.raise_for_status()
    except requests.RequestException as exc:
        return Response(f"Could not download image: {exc}", status=502)

    payload, fmt = _inject_caption_metadata(img_resp.content, edited_caption, detail_url or download_url)
    ext = ".jpg" if fmt == "JPEG" else ".png" if fmt == "PNG" else ".bin"
    name_root = _safe_filename(title or "getty_photo")
    filename = f"{name_root}_captioned{ext}"

    return Response(
        payload,
        mimetype=_mime_for(fmt),
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


if __name__ == "__main__":
    host = os.getenv("HOST", "127.0.0.1")
    port = int(os.getenv("PORT", "5050"))
    debug = os.getenv("FLASK_DEBUG", "1") == "1"
    app.run(host=host, port=port, debug=debug)
