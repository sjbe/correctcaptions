from src.web_app import _search


def test_search_requires_prompt():
    prompt, top_n, results, error, warning = _search({})
    assert prompt == ""
    assert top_n == 5
    assert results == []
    assert error == "Prompt is required."
    assert warning == ""
