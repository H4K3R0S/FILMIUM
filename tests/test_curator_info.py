# tests/test_curator_info.py
# ========== TEST: info intent — uzmi info iz baze; ako nema → TMDB ==========
from types import SimpleNamespace

from core.domains.filmium.curator.executors import Executors
from core.domains.filmium.curator.intents import get_intent


class _Repo:
    def __init__(self, items):
        self._items = items

    def list_all(self):
        return self._items


def _exec(items=(), tmdb=None) -> Executors:
    return Executors(
        retriever=None, repository=_Repo(list(items)),
        launch_vlc=lambda p: True, resolve_video_path=lambda i: None,
        tmdb_lookup=tmdb,
    )


def test_info_from_library():
    item = SimpleNamespace(title="Matriks", release_year=1999, genres=("SF",),
                           rating=9, english_description="opis")
    out = _exec([item]).info({"title": "matriks"})
    assert out["source"] == "library" and out["year"] == 1999 and out["rating"] == 9


def test_info_falls_back_to_tmdb():
    out = _exec([], tmdb=lambda t: {"title": t, "year": 1982}).info({"title": "Blade Runner"})
    assert out["source"] == "tmdb" and out["year"] == 1982


def test_info_none_when_not_found():
    assert _exec([], tmdb=lambda t: None).info({"title": "X"})["source"] == "none"


def test_info_intent_registered():
    spec = get_intent("info")
    assert spec is not None
    assert not spec.is_write and not spec.is_navigate and not spec.needs_media
