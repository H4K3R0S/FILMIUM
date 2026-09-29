from __future__ import annotations

from datetime import datetime

import pytest

from core.domains.filmium.curator.executors import Executors
from core.domains.filmium.models import MediaItem, MediaType, WatchStatus


def _item(**kw) -> MediaItem:
    base = {
        "id": 5, "title": "Matriks", "media_type": MediaType.MOVIE, "original_title": None,
        "english_title": None, "release_year": 1999, "runtime_minutes": 136,
        "watch_status": WatchStatus.COMPLETED, "rating": 9, "notes": None,
        "created_at": datetime(2024, 1, 1), "updated_at": datetime(2024, 1, 1),  # noqa: DTZ001
        "english_description": None, "content_category": "regular", "cast_names": (),
        "studio": None, "director": "Wachowski", "keywords": (), "collection": None,
        "is_synchronized": False, "editor_settings": {}, "tmdb_id": None, "genres": ("SF",),
        "is_favorite": False, "related_tmdb": (),
    }
    base.update(kw)
    return MediaItem(**base)


class _Repo:
    def __init__(self, item):
        self._item = item
        self.updated = None

    def get_by_id(self, item_id):
        return self._item if item_id == self._item.id else None

    def update(self, item_id, create):
        self.updated = (item_id, create)
        return self._item


class _Retriever:
    def retrieve(self, query, top_n=10):
        return [{"title": "Matriks"}, {"title": "Incepcija"}]


def _executors(repo):
    calls = []
    return Executors(
        retriever=_Retriever(),
        repository=repo,
        launch_vlc=lambda path, sub=None: calls.append(path) or True,
        resolve_video_path=lambda media_id: "F:/Filmovi/Matriks.mkv",
    ), calls


def test_search_vrati_naslove():
    ex, _ = _executors(_Repo(_item()))
    assert ex.search({"query": "matriks"})["titles"] == ["Matriks", "Incepcija"]


def test_search_top_navigacija_kad_ima_id():
    class _RetrieverID:
        def retrieve(self, query, top_n=10):
            return [{"title": "Matriks", "media_id": 5}, {"title": "Incepcija", "media_id": 7}]

    ex = Executors(
        retriever=_RetrieverID(), repository=_Repo(_item()),
        launch_vlc=lambda p, s=None: True, resolve_video_path=lambda i: None,
    )
    out = ex.search({"query": "matriks"})
    assert out["titles"] == ["Matriks", "Incepcija"]
    assert out["top"] == {"media_id": 5, "route": "/filmium/media/5"}


def test_search_bez_id_nema_top():
    ex, _ = _executors(_Repo(_item()))  # _Retriever bez media_id
    assert "top" not in ex.search({"query": "matriks"})


def test_play_je_navigacija_ne_pusta_backend():
    ex, calls = _executors(_Repo(_item()))
    out = ex.play({"media_id": 5})
    assert out["kind"] == "navigate"
    assert out["media_id"] == 5
    assert "/filmium/media/5" in out["route"]
    assert calls == []  # VLC nije pokrenut


def test_play_vlc_pokrene_launch():
    ex, calls = _executors(_Repo(_item()))
    assert ex.play_vlc({"media_id": 5})["launched"] is True
    assert calls == ["F:/Filmovi/Matriks.mkv"]


def test_preview_write_ne_pise():
    repo = _Repo(_item())
    ex, _ = _executors(repo)
    prev = ex.preview_write({"media_id": 5, "changes": {"rating": 7}})
    assert prev["title"] == "Matriks"
    assert prev["changes"] == {"rating": 7}
    assert repo.updated is None


def test_apply_write_menja_polje():
    repo = _Repo(_item())
    ex, _ = _executors(repo)
    out = ex.apply_write("edit_metadata", {"media_id": 5, "changes": {"rating": 7}})
    assert out == {"updated": True, "media_id": 5}
    item_id, create = repo.updated
    assert item_id == 5
    assert create.rating == 7
    assert create.title == "Matriks"  # ostala polja očuvana


def test_apply_write_nepoznato_polje_odbijeno():
    repo = _Repo(_item())
    ex, _ = _executors(repo)
    with pytest.raises(ValueError):
        ex.apply_write("edit_metadata", {"media_id": 5, "changes": {"nema": 1}})


def test_apply_write_nepostojeci_id():
    repo = _Repo(_item())
    ex, _ = _executors(repo)
    with pytest.raises(LookupError):
        ex.apply_write("save", {"media_id": 999, "changes": {"rating": 7}})
