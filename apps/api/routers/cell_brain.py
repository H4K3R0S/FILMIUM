"""Router: ćelijski Second Brain (graf sopstvenog repoa)."""
from __future__ import annotations

import json

from fastapi import APIRouter, HTTPException, Query

from apps.api.schemas.cell_brain import BrainFileOut, BrainGraphOut
from core.system import brain_maps as bmaps
from core.system.brain_regions import (
    build_regions,
    read_region_file,
    region_nodes,
    resolve_slug,
    search_atoms,
)
from core.system.cell_brain import (
    BrainGraphError,
    build_cell_brain,
    default_root,
    read_cell_brain_file,
)

router = APIRouter(prefix="/api/v1/second-brain", tags=["Second Brain"])


def _cell_meta() -> tuple[str | None, list[dict]]:
    """Ime domena i lista alata iz `cell.json` (centar grafa + „Alati" obruč).

    Nedostajuć/nečitljiv manifest je bezopasan — graf pada na ime foldera i
    prazan „Alati" obruč.
    """
    try:
        data = json.loads((default_root() / "cell.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None, []
    name = data.get("name")
    tools = data.get("tools")
    skills = data.get("skills")
    return (
        str(name) if name else None,
        list(tools) if isinstance(tools, list) else [],
        list(skills) if isinstance(skills, list) else [],
    )


@router.get("/graph", response_model=BrainGraphOut)
def get_graph() -> dict:
    name, tools, _skills = _cell_meta()
    return build_cell_brain(name=name, tools=tools).to_dict()


@router.get("/regions")
def get_regions(top_n: int = Query(16, ge=1, le=60)) -> dict:
    """Regioni znanja (glumci/filmovi/serije/anime/kolekcije) — isečeni prstenovi
    sa TOP-N čvorova po kombinovanom skoru (ocena+veze+veličina)."""
    result = build_regions(default_root(), top_n=top_n)
    _name, tools, skills = _cell_meta()
    result["meta"] = {"tools": tools, "skills": skills}
    return result


@router.get("/region/{key}")
def get_region_nodes(
    key: str,
    offset: int = Query(0, ge=0),
    limit: int = Query(300, ge=1, le=2000),
    lite: int = Query(0, ge=0, le=1),
) -> dict:
    """Drill-down: čvorovi jednog regiona (paginirano). lite=1 -> bez veza (brže)."""
    return region_nodes(default_root(), key, offset=offset, limit=limit, lite=bool(lite))


@router.get("/region-file")
def get_region_file(region: str = Query(...), rel: str = Query(...)) -> dict:
    """Sadržaj jednog atom fajla regiona (za sidebar prikaz)."""
    return read_region_file(default_root(), region, rel)


@router.get("/resolve")
def get_resolve(slug: str = Query(...)) -> dict:
    """Nadji atom po slugu kroz sve regione + skills/alati (za navigaciju [[linkovima]])."""
    return resolve_slug(default_root(), slug)


@router.get("/search")
def get_search(q: str = Query(...), limit: int = Query(30, ge=1, le=100)) -> dict:
    """Napredni pretraživač atoma (naziv/slug kroz sve regione + skills/alati/problemi)."""
    return search_atoms(default_root(), q, limit)


@router.get("/file", response_model=BrainFileOut)
def get_file(path: str = Query(..., description="Putanja fajla u ćeliji")) -> dict:
    try:
        return read_cell_brain_file(path)
    except BrainGraphError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/maps")
def get_maps() -> dict:
    """MAPS graf domena (root/oblasti/atomi/alati/veštine/rutine) — podrazumevani pogled „Mapa"."""
    return bmaps.build_maps(default_root())


@router.get("/spheres")
def get_spheres() -> dict:
    """Sfere drugih sistema (WORKPLACE + ostali domeni), fail-soft, keš 30 s."""
    return {"spheres": bmaps.list_spheres(own=bmaps.self_id(default_root()))}


@router.get("/spheres/{sphere_id}/maps")
def get_sphere_maps(sphere_id: str) -> dict:
    try:
        graph = bmaps.sphere_maps(sphere_id, own=bmaps.self_id(default_root()))
    except bmaps.SphereOffline as err:
        raise HTTPException(503, str(err)) from err
    if graph is None:
        raise HTTPException(404, f"nepoznata sfera: {sphere_id}")
    return graph
