# tests/test_curator_retriever.py
# ========== TEST: MediaRetriever metapodaci nose media_id (za navigaciju na film) ==========
from types import SimpleNamespace

from core.domains.filmium.curator.retriever import MediaRetriever


def _item(item_id: int, title: str) -> SimpleNamespace:
    return SimpleNamespace(
        id=item_id, title=title, english_title="", genres=(), keywords=(),
        cast_names=(), director="", studio="", collection="", notes="",
        english_description="", release_year=2026, rating=8,
    )


def test_retrieve_ukljucuje_media_id():
    r = MediaRetriever(lambda: [_item(42, "Mutiny")])
    out = r.retrieve("mutiny")
    assert out[0]["title"] == "Mutiny"
    assert out[0]["media_id"] == 42
