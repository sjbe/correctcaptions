#!/usr/bin/env python3
from __future__ import annotations

import argparse
import dataclasses
import datetime as dt
import json
import os
import re
import textwrap
from typing import Iterable, Optional
from urllib.parse import quote_plus, urljoin, urlparse

import requests
import yaml
from bs4 import BeautifulSoup
from dateutil import parser as date_parser

try:
    from openai import OpenAI
except Exception:  # pragma: no cover
    OpenAI = None


USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/122.0.0.0 Safari/537.36"
)

DEFAULT_CONFIG = {
    "search": {
        "per_provider_limit": 8,
        "timeout_seconds": 20,
    },
    "ranking": {
        "provider_weight": {"getty": 1.0, "ap": 1.0},
        "freshness_half_life_days": 14,
        "min_overlap_ratio": 0.12,
        "min_overlap_terms": 1,
        "news_keywords": [
            "breaking",
            "election",
            "conflict",
            "wildfire",
            "protest",
            "government",
            "court",
            "policy",
        ],
        "keyword_boost": 0.15,
    },
    "caption": {
        "mode": "llm",  # llm | template
        "instructions": (
            "Write a concise, factual news caption. Keep AP style tone. "
            "Avoid speculation, loaded language, and unsupported claims. "
            "Include who/what/where/when when known."
        ),
        "max_words": 45,
        "openai_model": "gpt-4.1-mini",
    },
}


@dataclasses.dataclass
class PhotoResult:
    provider: str
    title: str
    page_url: str
    image_url: str = ""
    raw_caption: str = ""
    captured_at: Optional[dt.datetime] = None
    score: float = 0.0
    edited_caption: str = ""
    caption_mode_used: str = ""
    caption_error: str = ""


class BaseProvider:
    name: str

    def __init__(self, session: requests.Session, timeout: int):
        self.session = session
        self.timeout = timeout

    def search(self, prompt: str, limit: int) -> list[PhotoResult]:
        raise NotImplementedError

    def fetch(self, url: str) -> Optional[str]:
        try:
            resp = self.session.get(url, timeout=self.timeout)
            resp.raise_for_status()
            return resp.text
        except requests.RequestException:
            return None


class GettyProvider(BaseProvider):
    name = "getty"

    def search(self, prompt: str, limit: int) -> list[PhotoResult]:
        q = quote_plus(prompt)
        url = f"https://www.gettyimages.com/photos/{q}?phrase={q}&sort=best"
        html = self.fetch(url)
        if not html:
            return []

        soup = BeautifulSoup(html, "html.parser")
        cards = self._extract_candidate_links(soup, "gettyimages.com")
        results: list[PhotoResult] = []
        for link in cards[: limit * 2]:
            result = self._parse_detail(link)
            if result:
                results.append(result)
            if len(results) >= limit:
                break
        return results

    def _extract_candidate_links(self, soup: BeautifulSoup, domain: str) -> list[str]:
        links: list[str] = []
        for a in soup.select("a[href]"):
            href = a.get("href", "")
            if not href:
                continue
            if href.startswith("/"):
                href = urljoin("https://www.gettyimages.com", href)
            if domain not in href:
                continue
            parsed = urlparse(href)
            # Keep only Getty asset detail pages.
            if "/detail/" in parsed.path:
                links.append(href.split("?")[0])
        return dedupe(links)

    def _parse_detail(self, url: str) -> Optional[PhotoResult]:
        html = self.fetch(url)
        if not html:
            return None
        soup = BeautifulSoup(html, "html.parser")
        title = first_text(
            soup,
            [
                "h1",
                'meta[property="og:title"]',
                "title",
            ],
            attr="content",
        )
        caption = extract_caption(soup)
        date_value = extract_date(soup)
        image_url = first_text(soup, ['meta[property="og:image"]'], attr="content")
        return PhotoResult(
            provider=self.name,
            title=title,
            page_url=url,
            image_url=image_url,
            raw_caption=caption,
            captured_at=date_value,
        )


class APProvider(BaseProvider):
    name = "ap"

    def search(self, prompt: str, limit: int) -> list[PhotoResult]:
        q = quote_plus(prompt)
        search_urls = [
            f"https://newsroom.ap.org/search?query={q}",
            f"https://newsroom.ap.org/editorial-photos-videos-search?query={q}",
            f"https://newsroom.ap.org/editorial-photos-videos-search?q={q}",
        ]
        links: list[str] = []
        for url in search_urls:
            html = self.fetch(url)
            if not html:
                continue
            soup = BeautifulSoup(html, "html.parser")
            links.extend(self._extract_candidate_links(soup, html))
            if len(dedupe(links)) >= limit * 2:
                break
        links = dedupe(links)
        if not links:
            return []

        results: list[PhotoResult] = []
        for link in links[: limit * 2]:
            result = self._parse_detail(link)
            if result:
                results.append(result)
            if len(results) >= limit:
                break
        return results

    def _extract_candidate_links(self, soup: BeautifulSoup, raw_html: str) -> list[str]:
        links: list[str] = []
        for a in soup.select("a[href]"):
            href = a.get("href", "")
            if not href:
                continue
            if href.startswith("/"):
                href = urljoin("https://newsroom.ap.org", href)
            if "newsroom.ap.org" not in href:
                continue
            parsed = urlparse(href)
            # Keep only AP asset detail pages.
            if "/detail/" in parsed.path:
                links.append(href.split("?")[0])
        links.extend(extract_detail_links_from_text(raw_html, "https://newsroom.ap.org"))
        return dedupe(links)

    def _parse_detail(self, url: str) -> Optional[PhotoResult]:
        html = self.fetch(url)
        if not html:
            return None
        soup = BeautifulSoup(html, "html.parser")
        title = first_text(
            soup,
            [
                "h1",
                'meta[property="og:title"]',
                "title",
            ],
            attr="content",
        )
        caption = extract_caption(soup)
        date_value = extract_date(soup)
        image_url = first_text(soup, ['meta[property="og:image"]'], attr="content")
        return PhotoResult(
            provider=self.name,
            title=title,
            page_url=url,
            image_url=image_url,
            raw_caption=caption,
            captured_at=date_value,
        )


def dedupe(items: Iterable[str]) -> list[str]:
    seen = set()
    ordered: list[str] = []
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        ordered.append(item)
    return ordered


def extract_detail_links_from_text(text: str, base_url: str) -> list[str]:
    links: list[str] = []
    # Some AP search pages render links in scripts instead of anchor tags.
    for match in re.findall(r"https?://newsroom\.ap\.org/detail/[A-Za-z0-9/_-]+", text):
        links.append(match.split("?")[0])
    for match in re.findall(r"(?<![A-Za-z0-9])(/detail/[A-Za-z0-9/_-]+)", text):
        links.append(urljoin(base_url, match).split("?")[0])
    return dedupe(links)


def first_text(soup: BeautifulSoup, selectors: list[str], attr: str | None = None) -> str:
    for selector in selectors:
        node = soup.select_one(selector)
        if not node:
            continue
        if attr:
            value = node.get(attr)
            if value:
                return normalize_ws(value)
        else:
            value = node.get_text(" ", strip=True)
            if value:
                return normalize_ws(value)
    return ""


def normalize_ws(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def extract_caption(soup: BeautifulSoup) -> str:
    selectors = [
        "[data-testid='caption']",
        ".caption",
        ".AssetDetail-caption",
        "figcaption",
        'meta[property="og:description"]',
        'meta[name="description"]',
    ]
    for selector in selectors:
        node = soup.select_one(selector)
        if not node:
            continue
        if node.name == "meta":
            val = node.get("content", "")
        else:
            val = node.get_text(" ", strip=True)
        val = normalize_ws(val)
        if val:
            return val

    # Fallback: parse JSON-LD blobs for description/caption.
    for script in soup.select("script[type='application/ld+json']"):
        try:
            data = json.loads(script.get_text())
        except Exception:
            continue
        for key in ("caption", "description", "headline"):
            val = extract_json_value(data, key)
            if val:
                return normalize_ws(val)
    return ""


def extract_json_value(obj, key: str) -> str:
    if isinstance(obj, dict):
        if key in obj and isinstance(obj[key], str):
            return obj[key]
        for value in obj.values():
            found = extract_json_value(value, key)
            if found:
                return found
    elif isinstance(obj, list):
        for item in obj:
            found = extract_json_value(item, key)
            if found:
                return found
    return ""


def extract_date(soup: BeautifulSoup) -> Optional[dt.datetime]:
    selectors = [
        'meta[property="article:published_time"]',
        'meta[name="pubdate"]',
        "time[datetime]",
    ]
    for selector in selectors:
        node = soup.select_one(selector)
        if not node:
            continue
        val = node.get("content") if node.name == "meta" else node.get("datetime")
        if not val:
            continue
        try:
            parsed = date_parser.parse(val)
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=dt.timezone.utc)
            return parsed
        except Exception:
            continue
    return None


def score_result(result: PhotoResult, prompt: str, cfg: dict) -> float:
    prompt_tokens = tokenize(prompt)
    text_tokens = tokenize(f"{result.title} {result.raw_caption}")

    overlap_terms = len(prompt_tokens & text_tokens)
    overlap = overlap_terms / max(len(prompt_tokens), 1)

    keyword_boost = 0.0
    for keyword in cfg["ranking"]["news_keywords"]:
        if keyword.lower() in f"{result.title} {result.raw_caption}".lower():
            keyword_boost += cfg["ranking"]["keyword_boost"]

    freshness = freshness_score(
        result.captured_at,
        cfg["ranking"]["freshness_half_life_days"],
    )

    provider_weight = cfg["ranking"]["provider_weight"].get(result.provider, 1.0)

    return (0.40 * overlap + 0.45 * freshness + keyword_boost) * provider_weight


def freshness_score(ts: Optional[dt.datetime], half_life_days: int) -> float:
    if not ts:
        return 0.25
    now = dt.datetime.now(dt.timezone.utc)
    age_days = max((now - ts.astimezone(dt.timezone.utc)).days, 0)
    return 0.5 ** (age_days / max(half_life_days, 1))


def tokenize(text: str) -> set[str]:
    stopwords = {
        "photo",
        "photos",
        "image",
        "images",
        "story",
        "stories",
        "about",
        "with",
        "from",
        "that",
        "this",
        "there",
        "their",
    }
    tokens = set(re.findall(r"[a-z0-9]{3,}", text.lower()))
    return {token for token in tokens if token not in stopwords}


def passes_relevance(result: PhotoResult, prompt: str, cfg: dict) -> bool:
    prompt_tokens = tokenize(prompt)
    if not prompt_tokens:
        return True
    text_tokens = tokenize(f"{result.title} {result.raw_caption}")
    overlap_terms = len(prompt_tokens & text_tokens)
    overlap_ratio = overlap_terms / max(len(prompt_tokens), 1)
    return (
        overlap_terms >= int(cfg["ranking"].get("min_overlap_terms", 1))
        and overlap_ratio >= float(cfg["ranking"].get("min_overlap_ratio", 0.12))
    )


def edit_caption(result: PhotoResult, prompt: str, cfg: dict) -> tuple[str, str, str]:
    mode = cfg["caption"].get("mode", "template")
    if mode == "llm":
        edited, err = edit_caption_llm(result, prompt, cfg)
        if edited:
            return edited, "llm", ""
        fallback = edit_caption_template(result, cfg)
        return fallback, "template", err or "LLM rewrite unavailable"
    return edit_caption_template(result, cfg), "template", ""


def edit_caption_template(result: PhotoResult, cfg: dict) -> str:
    text = result.raw_caption or result.title
    text = normalize_ws(text)
    max_words = int(cfg["caption"].get("max_words", 45))
    words = text.split()
    if len(words) > max_words:
        text = " ".join(words[:max_words]).rstrip(".,;:") + "..."
    return text


def edit_caption_llm(result: PhotoResult, prompt: str, cfg: dict) -> tuple[str, str]:
    if OpenAI is None:
        return "", "OpenAI package not installed"
    if not os.getenv("OPENAI_API_KEY"):
        return "", "OPENAI_API_KEY is not set"

    model = cfg["caption"].get("openai_model", "gpt-4.1-mini")
    instructions = cfg["caption"]["instructions"]
    max_words = int(cfg["caption"].get("max_words", 45))

    client = OpenAI()
    user_prompt = textwrap.dedent(
        f"""
        Story prompt: {prompt}
        Provider: {result.provider}
        Title: {result.title}
        Original caption: {result.raw_caption}

        Rewrite the caption per the instructions.
        Hard constraints:
        - Max {max_words} words.
        - Preserve factual meaning.
        - Output only the rewritten caption.
        """
    ).strip()

    try:
        response = client.responses.create(
            model=model,
            input=[
                {"role": "system", "content": instructions},
                {"role": "user", "content": user_prompt},
            ],
            max_output_tokens=200,
        )
    except Exception as exc:
        return "", f"OpenAI request failed: {exc}"

    text = extract_response_text(response)
    if not text:
        return "", "OpenAI returned empty text"
    return normalize_ws(text), ""


def extract_response_text(response) -> str:
    text = getattr(response, "output_text", "") or ""
    if text:
        return str(text)
    output = getattr(response, "output", None) or []
    chunks: list[str] = []
    for item in output:
        for content in getattr(item, "content", []) or []:
            if getattr(content, "type", "") == "output_text":
                value = getattr(content, "text", "")
                if value:
                    chunks.append(str(value))
    return " ".join(chunks).strip()


def load_config(path: Optional[str]) -> dict:
    cfg = json.loads(json.dumps(DEFAULT_CONFIG))
    if not path:
        return cfg
    with open(path, "r", encoding="utf-8") as f:
        user_cfg = yaml.safe_load(f) or {}
    deep_merge(cfg, user_cfg)
    return cfg


def deep_merge(base: dict, patch: dict) -> None:
    for key, value in patch.items():
        if key in base and isinstance(base[key], dict) and isinstance(value, dict):
            deep_merge(base[key], value)
        else:
            base[key] = value


def run(prompt: str, cfg: dict, top_n: int) -> list[PhotoResult]:
    timeout = int(cfg["search"]["timeout_seconds"])
    per_provider_limit = int(cfg["search"]["per_provider_limit"])

    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT})

    providers = [GettyProvider(session, timeout), APProvider(session, timeout)]

    all_results: list[PhotoResult] = []
    for provider in providers:
        all_results.extend(provider.search(prompt, per_provider_limit))

    for result in all_results:
        result.score = score_result(result, prompt, cfg)

    filtered = [r for r in all_results if passes_relevance(r, prompt, cfg)]
    ranked = sorted(filtered, key=lambda r: r.score, reverse=True)
    selected = ranked[:top_n]
    for result in selected:
        caption, mode_used, err = edit_caption(result, prompt, cfg)
        result.edited_caption = caption
        result.caption_mode_used = mode_used
        result.caption_error = err
    return selected


def print_results(results: list[PhotoResult]) -> None:
    if not results:
        print("No results found.")
        return

    for i, result in enumerate(results, start=1):
        when = (
            result.captured_at.strftime("%Y-%m-%d %H:%M %Z")
            if result.captured_at
            else "unknown"
        )
        print(f"\n[{i}] {result.provider.upper()}  score={result.score:.3f}")
        print(f"Title: {result.title}")
        print(f"Date: {when}")
        print(f"Edited Caption: {result.edited_caption or '(empty)'}")
        if result.caption_mode_used:
            print(f"Caption Engine: {result.caption_mode_used}")
        if result.caption_error:
            print(f"Caption Note: {result.caption_error}")
        print(f"Source Link: {result.page_url}")
        if result.image_url:
            print(f"Preview Image: {result.image_url}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Search Getty + AP public pages, rank photo candidates, and rewrite captions."
    )
    parser.add_argument("--prompt", required=True, help="Story/photo prompt")
    parser.add_argument("--config", help="Path to YAML config")
    parser.add_argument("--top", type=int, default=5, help="Number of results to output")
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    cfg = load_config(args.config)
    results = run(args.prompt, cfg, top_n=args.top)
    print_results(results)


if __name__ == "__main__":
    main()
