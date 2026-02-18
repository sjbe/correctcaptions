from src.post_download_captioner import score_match


def test_score_match_prefers_title_overlap():
    entry = {
        "title": "President Donald Trump speaks to members of the media aboard Air Force One",
        "caption": "President Trump speaks to members of the media aboard Air Force One on Feb. 18, 2026.",
        "asset_id": "",
    }
    good = score_match("president-donald-trump-speaks-media-aboard-air-force-one.jpg", entry)
    bad = score_match("golden-state-warriors-vs-lakers.jpg", entry)
    assert good > bad


def test_score_match_boosts_asset_id():
    entry = {"title": "Anything", "caption": "Anything", "asset_id": "2261576047"}
    assert score_match("getty_2261576047.jpg", entry) > 1.0
