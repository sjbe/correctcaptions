from __future__ import annotations

from typing import Tuple

from openai import OpenAI


def _norm(text: str) -> str:
    return " ".join((text or "").split()).strip().lower()


def _request_rewrite(
    client: OpenAI,
    model: str,
    instructions: str,
    user_prompt: str,
) -> str:
    resp = client.responses.create(
        model=model,
        input=[
            {"role": "system", "content": instructions},
            {"role": "user", "content": user_prompt},
        ],
        max_output_tokens=200,
    )
    text = getattr(resp, "output_text", "") or ""
    return " ".join(text.split()).strip()


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
        text = _request_rewrite(client, model, instructions, user_prompt)
        out = text or original_caption.strip()

        if _norm(out) == _norm(original_caption):
            force_instructions = (
                f"{instructions}\n"
                "You must rewrite wording and structure. "
                "Do not return the original text verbatim."
            )
            forced = _request_rewrite(client, model, force_instructions, user_prompt)
            forced_out = forced or original_caption.strip()
            if _norm(forced_out) == _norm(original_caption):
                return original_caption.strip(), "unchanged_by_model"
            return forced_out, "forced_rewrite_applied"

        return out, ""
    except Exception as exc:
        return original_caption.strip(), f"OpenAI request failed: {exc}"
