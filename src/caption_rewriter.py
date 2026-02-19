from __future__ import annotations

from typing import Tuple

from openai import OpenAI


def rewrite_caption_with_openai(
    original_caption: str,
    metadata: dict[str, str],
    instructions: str,
    model: str,
    max_words: int,
    api_key: str,
) -> Tuple[str, str]:
    if not api_key:
        return original_caption.strip(), "OPENAI_API_KEY missing"

    user_prompt = (
        "Rewrite this Getty photo caption using the provided rules.\n"
        f"Original caption: {original_caption}\n"
        f"Source metadata: {metadata}\n"
        f"Hard limits: max {max_words} words, output only the caption."
    )

    client = OpenAI(api_key=api_key)
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
