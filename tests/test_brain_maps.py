"""Mreža za core/system/brain_maps (MAPS graf domena + sfere). Kopiraj u `<domen>/tests/`."""

from __future__ import annotations

import pytest
from core.system import brain_maps as bm
from core.system.cell_brain import default_root

SAMPLE_REGIONS = {
    "regions": [
        {"key": "personas", "label": "Personas", "icon": "file", "count": 2, "nodes": [
            {"id": "personas:a.md", "label": "A", "rel": "a/persona.md", "region": "personas", "slug": "a",
             "conn": 1, "score": 3.0, "rating": 0, "links": ["b"],
             "link_regions": [{"slug": "b", "region": "personas", "conn": 0}]},
            {"id": "personas:b.md", "label": "B", "rel": "b/persona.md", "region": "personas", "slug": "b",
             "conn": 0, "score": 1.0, "rating": 0, "links": [], "link_regions": []},
        ]},
    ],
    "total": 2,
    "meta": {"tools": [{"name": "Skener", "slug": "skener"}], "skills": [{"name": "Upload", "slug": "upload"}]},
}


def _by_id(g: dict) -> dict[str, dict]:
    return {n["id"]: n for n in g["nodes"]}


def _has_link(g: dict, s: str, t: str) -> bool:
    return any(l["source"] == s and l["target"] == t for l in g["links"])


def test_adapt_regions_to_maps_shape() -> None:
    g = bm.adapt_regions_to_maps(SAMPLE_REGIONS, "DOMEN")
    n = _by_id(g)
    assert set(g) == {"center", "nodes", "links", "areas", "stats"}
    assert n["root"]["layer"] == 0 and n["area:personas"]["kind"] == "area"
    assert n["a"]["kind"] == "file" and n["a"]["path"] == "a/persona.md" and n["a"]["layer"] == 2
    assert _has_link(g, "a", "b") and _has_link(g, "area:personas", "b")
    assert n["app:skener"]["kind"] == "app" and n["app:skener"]["layer"] == 4
    assert n["skill:upload"]["kind"] == "skill" and n["skill:upload"]["layer"] == 1
    assert g["stats"]["files"] == 3 and g["stats"]["links"] == len(g["links"])
    for node in g["nodes"]:
        assert set(node) == {"id", "kind", "label", "area", "layer", "path", "note", "changed", "links", "status"}


def test_build_maps_real_domain() -> None:
    g = bm.build_maps(default_root())
    kinds = {n["kind"] for n in g["nodes"]}
    assert "root" in kinds and g["center"]["label"]
    assert all(n["layer"] == bm.LAYER[n["kind"]] for n in g["nodes"])
    files = [n for n in g["nodes"] if n["kind"] == "file"]
    if files:
        assert any(n["changed"] for n in files), "lokalni atomi treba da imaju datum izmene"


def test_spheres_exclude_self_and_failsoft() -> None:
    own = bm.self_id(default_root())
    assert own and own in {s["id"] for s in bm.ALL_SYSTEMS}

    def boom(url: str) -> dict:
        raise OSError("offline")

    spheres = bm.list_spheres(own=own, fetch=boom, use_cache=False)
    assert own not in {s["id"] for s in spheres}
    assert "workplace" in {s["id"] for s in spheres}
    assert all(s["online"] is False for s in spheres)


def test_sphere_maps_offline_and_unknown() -> None:
    def boom(url: str) -> dict:
        raise OSError("offline")
    assert bm.sphere_maps("nepoznat", own="x", fetch=boom) is None
    with pytest.raises(bm.SphereOffline):
        bm.sphere_maps("workplace", own="x", fetch=boom)
    g = bm.sphere_maps("workplace", own="x", fetch=lambda u: SAMPLE_REGIONS)
    assert g["center"]["label"] == "WORKPLACE" and _by_id(g)["a"]["kind"] == "file"
