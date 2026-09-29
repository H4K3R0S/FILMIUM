# tests/test_curator_enrich.py
# ========== TEST: enrich intent — AI povlači info sa TMDB + spoljnih servera ==========
from core.domains.filmium.curator.executors import Executors
from core.domains.filmium.curator.intents import get_intent


def _exec(enrich=None) -> Executors:
    return Executors(
        retriever=None, repository=None,
        launch_vlc=lambda p: True, resolve_video_path=lambda i: None,
        enrich_media=enrich,
    )


def test_enrich_calls_injected_with_media_id():
    seen = {}

    def fake(mid):
        seen["id"] = mid
        return {"tmdb_matched": True, "external": True}

    out = _exec(fake).enrich({"media_id": 7})
    assert seen["id"] == 7 and out["tmdb_matched"] is True and out["kind"] == "enrich"


def test_enrich_intent_registered_needs_media():
    spec = get_intent("enrich")
    assert spec is not None
    assert spec.needs_media and not spec.is_write and not spec.is_navigate
