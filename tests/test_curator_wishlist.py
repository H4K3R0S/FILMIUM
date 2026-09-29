# tests/test_curator_wishlist.py
# ========== TEST: add_to_wishlist — ako naslov nije u biblioteci, ponudi dodavanje (uz potvrdu) ==========
from types import SimpleNamespace

from core.domains.filmium.curator.executors import Executors
from core.domains.filmium.curator.intents import get_intent


class _Repo:
    def __init__(self, titles):
        self._titles = titles

    def list_all(self):
        return [SimpleNamespace(title=t) for t in self._titles]


def _exec(lib=(), wl=(), added=None) -> Executors:
    return Executors(
        retriever=None, repository=_Repo(lib),
        launch_vlc=lambda p: True, resolve_video_path=lambda i: None,
        wishlist_add=added or (lambda t: {"added": True, "title": t}),
        wishlist_titles=lambda: list(wl),
    )


def test_wishlist_intent_registered_is_write():
    spec = get_intent("add_to_wishlist")
    assert spec is not None and spec.is_write and not spec.needs_media


def test_preview_flags_new_title():
    out = _exec(lib=["Matriks"], wl=["Dina"]).preview_write({"title": "Blade Runner"}, "add_to_wishlist")
    assert out["title"] == "Blade Runner" and out["in_library"] is False and out["in_wishlist"] is False


def test_preview_detects_already_in_wishlist():
    assert _exec(wl=["Dina"]).preview_write({"title": "dina"}, "add_to_wishlist")["in_wishlist"] is True


def test_preview_detects_already_in_library():
    assert _exec(lib=["Matriks"]).preview_write({"title": "matriks"}, "add_to_wishlist")["in_library"] is True


def test_apply_adds_new():
    seen = {}
    out = _exec(added=lambda t: seen.setdefault("t", t) or {"added": True, "title": t}).apply_write(
        "add_to_wishlist", {"title": "Blade Runner"})
    assert seen["t"] == "Blade Runner" and out["added"] is True


def test_apply_skips_if_already_present():
    seen = {}
    out = _exec(wl=["Dina"], added=lambda t: seen.setdefault("t", t) or {"added": True}).apply_write(
        "add_to_wishlist", {"title": "Dina"})
    assert out["added"] is False and "t" not in seen


def test_edit_write_still_works_default_intent():
    # Postojeći media-edit put ne sme da se pokvari (intent podrazumevano edit_metadata).
    class R:
        def get_by_id(self, i):
            return SimpleNamespace(id=i, title="X")
    ex = Executors(retriever=None, repository=R(), launch_vlc=lambda p: True,
                   resolve_video_path=lambda i: None)
    out = ex.preview_write({"media_id": 5, "changes": {}})
    assert out["media_id"] == 5
