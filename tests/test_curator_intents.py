from __future__ import annotations

from core.domains.filmium.curator.intents import (
    INTENTS,
    get_intent,
    validate_params,
)


def test_allowlist_sadrzi_dvanaest_intenata():
    assert set(INTENTS) == {"search", "navigate", "recommend", "scan_library", "enrich",
                            "add_to_wishlist", "info", "play", "play_vlc",
                            "edit_metadata", "save", "open_second_brain_map"}


def test_open_second_brain_map_je_navigacija_bez_parametara():
    spec = INTENTS["open_second_brain_map"]
    assert spec.is_navigate is True
    assert spec.is_write is False
    assert spec.needs_media is False
    assert spec.required_params == ()


def test_navigate_je_navigacija_bez_upisa_i_medija():
    assert INTENTS["navigate"].is_navigate is True
    assert INTENTS["navigate"].is_write is False
    assert INTENTS["navigate"].needs_media is False


def test_upisi_su_oznaceni():
    assert INTENTS["edit_metadata"].is_write is True
    assert INTENTS["save"].is_write is True
    assert INTENTS["search"].is_write is False
    assert INTENTS["play"].is_navigate is True


def test_film_namere_traze_media():
    # play/edit/save traže konkretan film; search ne.
    assert INTENTS["play"].needs_media is True
    assert INTENTS["edit_metadata"].needs_media is True
    assert INTENTS["search"].needs_media is False


def test_get_intent_nepoznat_je_none():
    assert get_intent("obrisi_sve") is None


def test_validate_params_prijavi_nedostajuce():
    # `media_id` više NIJE obavezno polje (agent ga razrešava iz naslova);
    # play zato ništa ne zahteva, a edit_metadata traži samo `changes`.
    assert validate_params(INTENTS["play"], {}) == []
    assert validate_params(INTENTS["edit_metadata"], {}) == ["changes"]
    assert validate_params(INTENTS["edit_metadata"], {"changes": {}}) == []
