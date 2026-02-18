import datetime as dt

from src.photo_finder import (
    PhotoResult,
    edit_caption,
    edit_caption_template,
    extract_detail_links_from_text,
    freshness_score,
    passes_relevance,
    score_result,
    tokenize,
)


CFG = {
    "ranking": {
        "provider_weight": {"getty": 1.0, "ap": 1.0},
        "freshness_half_life_days": 10,
        "min_overlap_ratio": 0.12,
        "min_overlap_terms": 1,
        "news_keywords": ["wildfire", "election"],
        "keyword_boost": 0.1,
    },
    "caption": {"max_words": 5},
}


def test_freshness_score_recent_higher_than_old():
    now = dt.datetime.now(dt.timezone.utc)
    recent = freshness_score(now - dt.timedelta(days=1), 10)
    old = freshness_score(now - dt.timedelta(days=30), 10)
    assert recent > old


def test_score_prefers_overlap_and_keywords():
    a = PhotoResult(
        provider="getty",
        title="Wildfire smoke covers downtown",
        page_url="https://example.com/a",
        raw_caption="Officials discuss wildfire response",
    )
    b = PhotoResult(
        provider="getty",
        title="Basketball playoff game",
        page_url="https://example.com/b",
        raw_caption="Quarterfinal action",
    )

    score_a = score_result(a, "wildfire response downtown", CFG)
    score_b = score_result(b, "wildfire response downtown", CFG)
    assert score_a > score_b


def test_template_caption_limits_words():
    result = PhotoResult(
        provider="ap",
        title="",
        page_url="https://example.com",
        raw_caption="one two three four five six seven",
    )
    edited = edit_caption_template(result, CFG)
    assert edited == "one two three four five..."


def test_tokenize_drops_generic_terms():
    tokens = tokenize("a photo for a story about the supreme court")
    assert "photo" not in tokens
    assert "story" not in tokens
    assert "supreme" in tokens
    assert "court" in tokens


def test_passes_relevance_requires_real_overlap():
    relevant = PhotoResult(
        provider="ap",
        title="U.S. Supreme Court justices during session",
        page_url="https://example.com/r",
        raw_caption="A view of the Supreme Court chamber.",
    )
    irrelevant = PhotoResult(
        provider="ap",
        title="NBA Finals pregame introductions",
        page_url="https://example.com/i",
        raw_caption="Players line up before tipoff.",
    )
    prompt = "a photo for a story about the supreme court"
    assert passes_relevance(relevant, prompt, CFG) is True
    assert passes_relevance(irrelevant, prompt, CFG) is False


def test_edit_caption_reports_llm_fallback_when_key_missing(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    result = PhotoResult(
        provider="ap",
        title="Supreme Court hearing",
        page_url="https://example.com",
        raw_caption="A justice arrives at the court.",
    )
    cfg = {
        "caption": {
            "mode": "llm",
            "instructions": "Rewrite",
            "max_words": 20,
            "openai_model": "gpt-4.1-mini",
        }
    }
    edited, mode_used, err = edit_caption(result, "supreme court", cfg)
    assert edited
    assert mode_used == "template"
    assert "OPENAI_API_KEY" in err


def test_extract_detail_links_from_text_finds_script_links():
    raw = """
    <script>
      const a = "https://newsroom.ap.org/detail/abc123def456";
      const b = "/detail/xyz999";
    </script>
    """
    links = extract_detail_links_from_text(raw, "https://newsroom.ap.org")
    assert "https://newsroom.ap.org/detail/abc123def456" in links
    assert "https://newsroom.ap.org/detail/xyz999" in links
