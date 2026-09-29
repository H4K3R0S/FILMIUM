"""brain_maps — MAPS graf Second Brain-a DOMENA (varijanta za `core/system/` ćelije).

Po uzoru na `ai-os-maps-guide` `brain.json`. Ne dira `brain_regions.py`: MAPS graf se
gradi iz standardnog `build_regions()` oblika (in-process, bez HTTP limita `le=60`) +
`cell.json` (`tools` → app, `skills` → skill) + `jobs/*.py` (→ routine). Sfere = ostali
sistemi (WORKPLACE :4806 + drugi domeni) kroz njihov standardni `/regions` API, kratak
timeout, keš 30 s; ugašen sistem = `online: false`, nikad pad.

Instalacija: kopiraj u `<domen>/core/system/brain_maps.py`; rute u
`apps/api/routers/cell_brain.py` (`/maps`, `/spheres`, `/spheres/{id}/maps`).
"""

from __future__ import annotations

import json
import re
import threading
import time
import urllib.request
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from core.system.brain_regions import _get_full, build_regions
from core.system.cell_brain import default_root

LAYER = {"root": 0, "skill": 1, "area": 2, "file": 2, "routine": 3, "run": 3, "app": 4}
REGION_LIMIT = 400          # čvorova po regionu u lokalnom grafu
SPHERE_TOP_N = 60           # domenska `/regions` ruta ima `le=60`
SPHERE_REGION_LIMIT = 400   # drill `/region/{key}` za regione veće od TOP_N
SPHERE_TIMEOUT_S = 1.5
SPHERE_CACHE_TTL_S = 30.0

# Svi sistemi sa Second Brain API-jem; sopstveni domen se izostavlja (vidi `spheres_for`).
ALL_SYSTEMS: list[dict[str, Any]] = [
    {"id": "workplace", "label": "WORKPLACE", "port": 4806},
    {"id": "filmium", "label": "FILMIUM", "port": 4801},
    {"id": "codium", "label": "CODIUM", "port": 4802},
    {"id": "imperium", "label": "IMPERIUM", "port": 4803},
    {"id": "kalima", "label": "KALIMA", "port": 4804},
]

Fetch = Callable[[str], dict]


class SphereOffline(RuntimeError):
    """Sistem ne odgovara (ugašen / timeout / greška)."""


def _slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def _iso(ts: float) -> str:
    return datetime.fromtimestamp(ts, tz=timezone.utc).astimezone().replace(microsecond=0).isoformat()


def _cell(root: Path) -> dict:
    try:
        data = json.loads((root / "cell.json").read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def _node(id_: str, kind: str, label: str, area: str | None, *, path: str | None = None,
          note: str = "", changed: str | None = None, status: str | None = None) -> dict[str, Any]:
    return {
        "id": id_, "kind": kind, "label": label, "area": area, "layer": LAYER[kind],
        "path": path, "note": note, "changed": changed, "links": 0, "status": status,
    }


def _finish(center_label: str, nodes: list[dict], links: list[dict], areas: list[dict]) -> dict[str, Any]:
    ids = {n["id"] for n in nodes}
    links = [l for l in links if l["source"] in ids and l["target"] in ids and l["source"] != l["target"]]
    deg: dict[str, int] = {}
    for l in links:
        deg[l["source"]] = deg.get(l["source"], 0) + 1
        deg[l["target"]] = deg.get(l["target"], 0) + 1
    for n in nodes:
        n["links"] = deg.get(n["id"], 0)
    return {
        "center": {"id": "root", "label": center_label},
        "nodes": nodes, "links": links, "areas": areas,
        "stats": {
            "files": sum(1 for n in nodes if n["kind"] in ("file", "skill")),
            "links": len(links),
            "runs": sum(1 for n in nodes if n["kind"] == "run"),
        },
    }


def adapt_regions_to_maps(regions: dict, center_label: str,
                          changed_for: Callable[[str, str], str | None] | None = None) -> dict[str, Any]:
    """Standardni `/regions` odgovor (bilo kog Second Brain-a) → MAPS graf.
    `changed_for(region_key, rel)` opciono daje datum izmene (samo lokalno)."""
    nodes: list[dict] = [_node("root", "root", center_label, None)]
    links: list[dict] = []
    areas: list[dict] = []
    for region in regions.get("regions") or []:
        key = str(region.get("key") or "")
        if not key:
            continue
        area_id = f"area:{key}"
        areas.append({"key": key, "label": region.get("label") or key, "count": int(region.get("count") or 0)})
        nodes.append(_node(area_id, "area", region.get("label") or key, key))
        links.append({"source": "root", "target": area_id})
        for a in region.get("nodes") or []:
            aid = str(a.get("slug") or a.get("id") or "")
            if not aid:
                continue
            rel = a.get("rel")
            changed = changed_for(key, rel) if (changed_for and rel) else None
            nodes.append(_node(aid, "file", a.get("label") or aid, key, path=rel, changed=changed))
            links.append({"source": area_id, "target": aid})
            for lr in a.get("link_regions") or []:
                if lr.get("slug"):
                    links.append({"source": aid, "target": str(lr["slug"])})
    meta = regions.get("meta") or {}
    for t in meta.get("tools") or []:
        tid = f"app:{_slugify(str(t.get('slug') or t.get('name') or ''))}"
        nodes.append(_node(tid, "app", t.get("name") or tid, None, note=t.get("description") or ""))
        links.append({"source": "root", "target": tid})
    for s in meta.get("skills") or []:
        sid = f"skill:{_slugify(str(s.get('slug') or s.get('name') or ''))}"
        nodes.append(_node(sid, "skill", s.get("name") or sid, None, note=s.get("description") or ""))
        links.append({"source": "root", "target": sid})
    return _finish(center_label, nodes, links, areas)


# ==========          LOKALNI GRAF DOMENA          ==========

def _routines(root: Path) -> list[dict[str, Any]]:
    """`jobs/*.py` (bez `_`/`__init__`) = rutine domena."""
    jobs = root / "jobs"
    if not jobs.is_dir():
        return []
    return [
        _node(f"routine:{p.name}", "routine", p.stem, None,
              path=p.relative_to(root).as_posix(), changed=_iso(p.stat().st_mtime))
        for p in sorted(jobs.iterdir())
        if p.is_file() and p.suffix == ".py" and not p.name.startswith("_")
    ]


def build_maps(root: Path | None = None) -> dict[str, Any]:
    """MAPS graf ovog domena: regioni (atomi) + cell.json alati/veštine + jobs rutine."""
    base = Path(root) if root else default_root()
    cell = _cell(base)
    regions = build_regions(base, top_n=REGION_LIMIT)
    regions["meta"] = {
        "tools": cell.get("tools") if isinstance(cell.get("tools"), list) else [],
        "skills": cell.get("skills") if isinstance(cell.get("skills"), list) else [],
    }
    # `rel` u domenu je slug (ime fajla bez .md); pravu putanju daje indeks slug→path.
    _, index = _get_full(base)

    def changed_for(_key: str, rel: str) -> str | None:
        ent = index.get(Path(rel).name.removesuffix(".md").lower())
        try:
            return _iso(Path(ent["path"]).stat().st_mtime) if ent else None
        except (OSError, KeyError, TypeError):
            return None

    graph = adapt_regions_to_maps(regions, str(cell.get("name") or base.name.upper()), changed_for)
    routines = _routines(base)
    graph["nodes"].extend(routines)
    graph["links"].extend({"source": "root", "target": r["id"]} for r in routines)
    return _finish(graph["center"]["label"], graph["nodes"], graph["links"], graph["areas"])


# ==========          SFERE (drugi sistemi)          ==========

def self_id(root: Path | None = None) -> str:
    cell = _cell(Path(root) if root else default_root())
    return str(cell.get("domain_id") or cell.get("name") or "").strip().lower()


def spheres_for(own: str) -> list[dict[str, Any]]:
    return [s for s in ALL_SYSTEMS if s["id"] != own]


def _http_json(url: str) -> dict:
    with urllib.request.urlopen(url, timeout=SPHERE_TIMEOUT_S) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _regions_url(sphere: dict, top_n: int) -> str:
    return f"http://127.0.0.1:{sphere['port']}/api/v1/second-brain/regions?top_n={top_n}"


_cache_lock = threading.Lock()
_cache: tuple[float, list[dict]] | None = None


def _summarize(sphere: dict, fetch: Fetch) -> dict[str, Any]:
    base = {"id": sphere["id"], "label": sphere["label"], "port": sphere["port"],
            "url": f"http://127.0.0.1:{sphere['port']}"}
    try:
        data = fetch(_regions_url(sphere, 1))
        areas = [{"key": r["key"], "label": r.get("label") or r["key"], "count": int(r.get("count") or 0)}
                 for r in data.get("regions") or [] if r.get("key")]
        return {**base, "online": True, "total": int(data.get("total") or 0), "areas": areas}
    except Exception:  # noqa: BLE001 — bilo koja greška = offline
        return {**base, "online": False, "total": 0, "areas": []}


def list_spheres(own: str | None = None, fetch: Fetch | None = None, use_cache: bool = True) -> list[dict[str, Any]]:
    """Sažetak svih sfera osim sopstvene (paralelno, fail-soft, keš 30 s)."""
    global _cache
    if use_cache:
        with _cache_lock:
            if _cache and time.monotonic() - _cache[0] < SPHERE_CACHE_TTL_S:
                return _cache[1]
    targets = spheres_for(own if own is not None else self_id())
    f = fetch or _http_json
    with ThreadPoolExecutor(max_workers=max(1, len(targets))) as pool:
        result = list(pool.map(lambda s: _summarize(s, f), targets))
    if use_cache:
        with _cache_lock:
            _cache = (time.monotonic(), result)
    return result


def sphere_maps(sphere_id: str, own: str | None = None, fetch: Fetch | None = None) -> dict[str, Any] | None:
    """MAPS graf jedne sfere; None = nepoznat id; SphereOffline = sistem ne odgovara."""
    sphere = next((s for s in spheres_for(own if own is not None else self_id()) if s["id"] == sphere_id), None)
    if sphere is None:
        return None
    f = fetch or _http_json
    try:
        data = f(_regions_url(sphere, SPHERE_TOP_N))
    except Exception as err:
        raise SphereOffline(f"{sphere['label']} ne odgovara na :{sphere['port']}") from err
    for region in data.get("regions") or []:
        if int(region.get("count") or 0) > len(region.get("nodes") or []):
            url = (f"http://127.0.0.1:{sphere['port']}/api/v1/second-brain/region/"
                   f"{region['key']}?offset=0&limit={SPHERE_REGION_LIMIT}")
            try:
                region["nodes"] = f(url).get("nodes") or region.get("nodes") or []
            except Exception:  # noqa: BLE001
                pass
    return adapt_regions_to_maps(data, sphere["label"])
