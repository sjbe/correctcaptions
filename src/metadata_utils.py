from __future__ import annotations

import io
import os
import tempfile
from typing import Any

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


def short_source_label(source_url: str) -> str:
    if "gettyimages.com" in source_url:
        return "Getty Images"
    return source_url


def inject_iptc_jpeg(content: bytes, caption: str, source_url: str) -> bytes:
    if IPTCInfo is None:
        return content
    try:
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
            tmp.write(content)
            tmp_path = tmp.name
        try:
            info = IPTCInfo(tmp_path, force=True)
            info["caption/abstract"] = caption
            info["credit"] = short_source_label(source_url)
            info["source"] = short_source_label(source_url)
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


def inject_caption_metadata(content: bytes, caption: str, source_url: str) -> tuple[bytes, str]:
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
            exif_dict = (
                piexif.load(exif_bytes)
                if exif_bytes
                else {"0th": {}, "Exif": {}, "GPS": {}, "1st": {}, "thumbnail": None}
            )
            exif_dict["0th"][piexif.ImageIFD.ImageDescription] = caption.encode(
                "utf-8", errors="ignore"
            )
            exif_dict["0th"][piexif.ImageIFD.XPSubject] = caption.encode(
                "utf-16le", errors="ignore"
            )
            exif_dict["Exif"][piexif.ExifIFD.UserComment] = piexif.helper.UserComment.dump(
                caption, encoding="unicode"
            )
            exif_dict["0th"][piexif.ImageIFD.Artist] = short_source_label(
                source_url
            ).encode("utf-8", errors="ignore")
            exif_dict["0th"][piexif.ImageIFD.Copyright] = f"Source: {source_url}".encode(
                "utf-8", errors="ignore"
            )
            out = io.BytesIO()
            im.save(out, format="JPEG", exif=piexif.dump(exif_dict), quality=95)
            return inject_iptc_jpeg(out.getvalue(), caption, source_url), "JPEG"

        if fmt == "PNG":
            pnginfo = PngImagePlugin.PngInfo()
            pnginfo.add_text("Description", caption)
            pnginfo.add_text("Source", source_url)
            out = io.BytesIO()
            im.save(out, format="PNG", pnginfo=pnginfo)
            return out.getvalue(), "PNG"

    return content, fmt or "BIN"


def _decode_meta(value: Any) -> str:
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="ignore").strip()
    if value is None:
        return ""
    return str(value).strip()


def read_image_metadata(path: str) -> dict[str, str]:
    meta = {
        "caption": "",
        "source": "",
        "credit": "",
        "title": "",
        "format": "",
    }
    if Image is None:
        return meta

    try:
        with Image.open(path) as im:
            meta["format"] = (im.format or "").upper()
            if meta["format"] == "PNG":
                info = im.info or {}
                meta["caption"] = _decode_meta(info.get("Description", ""))
                meta["source"] = _decode_meta(info.get("Source", ""))
            if meta["format"] in {"JPEG", "JPG"} and piexif is not None:
                exif_bytes = im.info.get("exif", b"")
                if exif_bytes:
                    exif = piexif.load(exif_bytes)
                    z0 = exif.get("0th", {})
                    meta["caption"] = meta["caption"] or _decode_meta(
                        z0.get(piexif.ImageIFD.ImageDescription, b"")
                    )
                    meta["credit"] = meta["credit"] or _decode_meta(
                        z0.get(piexif.ImageIFD.Artist, b"")
                    )
                    meta["source"] = meta["source"] or _decode_meta(
                        z0.get(piexif.ImageIFD.Copyright, b"")
                    )
    except Exception:
        pass

    if IPTCInfo is not None and path.lower().endswith((".jpg", ".jpeg")):
        try:
            info = IPTCInfo(path, force=True)
            meta["caption"] = meta["caption"] or _decode_meta(info["caption/abstract"])
            meta["credit"] = meta["credit"] or _decode_meta(info["credit"])
            meta["source"] = meta["source"] or _decode_meta(info["source"])
            meta["title"] = meta["title"] or _decode_meta(info["headline"] or info["object name"])
        except Exception:
            pass

    return meta


def is_probably_getty(path: str, metadata: dict[str, str]) -> bool:
    haystack = " ".join(
        [
            os.path.basename(path),
            metadata.get("caption", ""),
            metadata.get("source", ""),
            metadata.get("credit", ""),
            metadata.get("title", ""),
        ]
    ).lower()
    return "getty" in haystack or "gettyimages.com" in haystack
