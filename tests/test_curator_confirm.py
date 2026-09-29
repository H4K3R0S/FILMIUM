from __future__ import annotations

import pytest

from core.domains.filmium.curator.confirm import ConfirmStore


def test_izdat_token_se_moze_iskoristiti_jednom():
    store = ConfirmStore()
    token = store.issue("save", {"media_id": 1})
    assert store.take(token) == ("save", {"media_id": 1})
    with pytest.raises(KeyError):
        store.take(token)  # drugi put ne


def test_nepoznat_token_dize_gresku():
    with pytest.raises(KeyError):
        ConfirmStore().take("nema")


def test_istekao_token_ne_radi():
    clock = {"t": 0.0}
    store = ConfirmStore(ttl_seconds=10.0, now=lambda: clock["t"])
    token = store.issue("save", {"media_id": 1})
    clock["t"] = 11.0
    with pytest.raises(KeyError):
        store.take(token)
