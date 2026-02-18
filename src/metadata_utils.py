from __future__ import annotations

import io
import os
import tempfile

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
