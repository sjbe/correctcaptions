from src.metadata_utils import is_probably_getty


def test_is_probably_getty_true_for_getty_name():
    meta = {"caption": "", "source": "", "credit": "", "title": ""}
    assert is_probably_getty("/tmp/getty-photo.jpg", meta) is True


def test_is_probably_getty_true_for_credit():
    meta = {"caption": "", "source": "", "credit": "Getty Images", "title": ""}
    assert is_probably_getty("/tmp/photo.jpg", meta) is True


def test_is_probably_getty_false_otherwise():
    meta = {"caption": "City council meeting", "source": "AP", "credit": "", "title": ""}
    assert is_probably_getty("/tmp/photo.jpg", meta) is False
