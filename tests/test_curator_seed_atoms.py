from __future__ import annotations

from pathlib import Path

from core.domains.filmium.curator.atoms import AtomLoader

_ROOT = Path(__file__).resolve().parents[1] / ".ai" / "atomi" / "personas" / "kurator"


def test_seed_atomi_postoje_i_ucitavaju_se():
    loader = AtomLoader(_ROOT)
    assert loader.persona().meta.get("type") == "persona"
    assert "filter" in loader.tool("pretraga").body.lower()
    assert "web plejer" in loader.tool("plejer").body.lower()
    assert loader.tool("izmena-info").body.strip()
    catalog = loader.command_catalog()
    for intent in ("search", "play", "edit_metadata", "save"):
        assert intent in catalog
