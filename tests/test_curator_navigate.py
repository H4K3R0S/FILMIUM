# tests/test_curator_navigate.py
# ========== TEST: navigate intent — Kurator prebacuje prozor na prikaz (žanr/serije/biblioteka) ==========
import pytest

from core.domains.filmium.curator.executors import VIEW_ROUTES, Executors
from core.domains.filmium.curator.intents import get_intent


def _exec() -> Executors:
    return Executors(
        retriever=None, repository=None,
        launch_vlc=lambda p: True, resolve_video_path=lambda i: None,
    )


def test_navigate_maps_view_to_route():
    assert _exec().navigate({"view": "animirano"}) == {"kind": "navigate", "route": "/filmium/animirano"}


def test_navigate_normalizes_synonym():
    assert _exec().navigate({"view": "crtani"})["route"] == "/filmium/animirano"
    assert _exec().navigate({"view": "biblioteka"})["route"] == "/filmium/library"


def test_navigate_rejects_unknown_view():
    with pytest.raises(ValueError):
        _exec().navigate({"view": "teleport"})


def test_navigate_intent_registered():
    spec = get_intent("navigate")
    assert spec is not None and spec.is_navigate and not spec.is_write and not spec.needs_media


def test_open_second_brain_map_navigates_to_maps_view():
    assert _exec().open_second_brain_map({}) == {"kind": "navigate", "route": "/second-brain?view=mapa"}


def test_navigate_with_media_type_and_sort_filters():
    out = _exec().navigate({"view": "library", "media_type": "serije", "sort": "ocena"})
    assert out["route"] == "/filmium/library"
    assert out["filters"] == {"media_type": "series", "sort": "rating"}


def test_navigate_defaults_to_library_when_only_filter():
    out = _exec().navigate({"media_type": "filmovi"})
    assert out["route"] == "/filmium/library" and out["filters"]["media_type"] == "movie"


def test_navigate_genre_filter_passthrough():
    out = _exec().navigate({"view": "animirano", "genre": "SF"})
    assert out["route"] == "/filmium/animirano" and out["filters"]["genre"] == "SF"


def test_recommend_navigates_to_real_list():
    # Preporuka mora da sleti na PRAVU listu sa sadržajem (biblioteka, poređana
    # po oceni), ne na placeholder /filmium/recommended niti na prazan top-rated.
    out = _exec().recommend({"genre": "SF"})
    assert out["kind"] == "navigate" and out["route"] == "/filmium/library"
    assert out["filters"]["genre"] == "SF"
    assert out["filters"]["sort"] == "rating"  # „preporuka" = poređaj po oceni


def test_recommend_bez_zanra_i_dalje_ima_sort():
    out = _exec().recommend({})
    assert out["route"] == "/filmium/library" and out["filters"]["sort"] == "rating"


def test_recommend_sa_recommenderom_vraca_ids():
    # Sa recommenderom → prikaži baš kuriranih ~N naslova (?ids=...), ne celu biblioteku.
    class _Rec:
        def recommend(self, *, genre=None, media_type=None, mood=None, limit=20):
            return [3, 7, 9]

    ex = Executors(
        retriever=None, repository=None,
        launch_vlc=lambda p: True, resolve_video_path=lambda i: None,
        recommender=_Rec(),
    )
    out = ex.recommend({"genre": "SF"})
    assert out["route"] == "/filmium/library"
    assert out["filters"]["ids"] == "3,7,9"
    assert out["count"] == 3


def test_all_view_routes_under_filmium():
    assert all(r.startswith("/filmium/") for r in VIEW_ROUTES.values())


# Placeholder rute (FilmiumPlaceholderPage) — Kurator NE sme da tamo šalje korisnika.
_PLACEHOLDER_ROUTES = {"/filmium/recommended", "/filmium/trending"}


def test_view_routes_avoid_placeholders():
    assert not (_PLACEHOLDER_ROUTES & set(VIEW_ROUTES.values()))
