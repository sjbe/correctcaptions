from src.caption_only_watcher import rewrite_caption


def test_rewrite_caption_reports_missing_key_when_no_api(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    cfg = {"caption": {"instructions": "x", "openai_model": "gpt-4.1-mini", "max_words": 30}}
    caption, reason = rewrite_caption("Original caption", {"source": "Getty"}, cfg, "", "")
    assert caption == "Original caption"
    assert "OPENAI_API_KEY missing" in reason
