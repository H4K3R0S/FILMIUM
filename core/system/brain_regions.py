# core/system/brain_regions.py
# ==========  Second Brain: REGIONI ZNANJA (isečeni prstenovi + drill-down)  ==========
#
# SR: Gradi „regione" (kategorije atoma) za Second Brain: svaki region je isečak
#     prstena; prikazuje TOP-N čvorova po KOMBINOVANOM skoru (ocena + broj veza +
#     veličina). Klik na region → svi čvorovi tog regiona (drill-down). Keš zbog
#     velikih kolekcija (npr. 5907 glumac-atoma).
# EN: Builds knowledge "regions" for the Second Brain: each region is a ring
#     segment showing TOP-N nodes by a COMBINED score (rating + connections +
#     size). Cached because collections can be large.
from __future__ import annotations

import json
import os
import re
import threading
import time
from pathlib import Path

# --- konfiguracija regiona po domenu (ovde: FILMIUM) ---
# Svaki: (key, label, icon, [apsolutne ili root-relativne putanje foldera atoma])
_MOUNT_ACTORS = "/run/media/kalima/FILMIUM/Actors"


def region_configs(root: Path) -> list[dict]:
    """SR/EN: FILMIUM regioni — glumci (mount Actors), filmovi/serije/kolekcije
    (.ai/atomi/filmium/*). Anime se izdvaja iz filmova/serija po ključnoj reči."""
    ai = root / ".ai" / "atomi" / "filmium"
    return [
        {"key": "glumci", "label": "Glumci", "icon": "users", "dirs": [Path(_MOUNT_ACTORS)]},
        {"key": "filmovi", "label": "Filmovi", "icon": "film", "dirs": [ai / "filmovi"]},
        {"key": "serije", "label": "Serije", "icon": "tv", "dirs": [ai / "serije"]},
        {"key": "anime", "label": "Anime", "icon": "sparkles", "dirs": [], "derived": "anime"},
        {"key": "kolekcije", "label": "Kolekcije", "icon": "layers", "dirs": [ai / "kolekcije"]},
        {"key": "franshize", "label": "Franšize", "icon": "film", "dirs": [ai / "franshize"]},
    ]


_FM_RE = re.compile(r"^---\s*\n(.*?)\n---", re.DOTALL)
_LINK_RE = re.compile(r"\[\[")
_RATING_KEYS = ("imdb_rating", "mal_score", "tvmaze_rating", "rt_tomatometer",
                "rt_audience_score", "rating", "score")
_LIST_KEYS = ("professions", "signature_traits", "tags", "keywords", "known_for")


def _read_head(path: Path, limit: int = 8192) -> str:
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as fh:
            return fh.read(limit)
    except OSError:
        return ""


def _atom_metrics(path: Path) -> dict | None:
    """SR: (naziv, ocena, broj_veza, veličina). / EN: (label, rating, conn, size)."""
    try:
        size = path.stat().st_size
    except OSError:
        return None
    head = _read_head(path)
    if not head:
        return None
    fm = _FM_RE.search(head)
    fm_text = fm.group(1) if fm else ""
    # naziv: title:/name: iz frontmatter-a, inače ime fajla
    label = path.stem
    m = re.search(r"^\s*(?:title|name):\s*(.+?)\s*$", fm_text, re.MULTILINE)
    if m:
        label = m.group(1).strip().strip('"').strip("'") or label
    # ocena: najveća numerička vrednost iz poznatih ključeva (RT % -> /10)
    rating = 0.0
    for key in _RATING_KEYS:
        mm = re.search(rf"^\s*{key}:\s*([0-9]+(?:\.[0-9]+)?)", fm_text, re.MULTILINE)
        if mm:
            val = float(mm.group(1))
            if key in ("rt_tomatometer", "rt_audience_score"):
                val = val / 10.0
            rating = max(rating, val)
    # veze: [[linkovi]] u telu + stavke u listama frontmatter-a
    conn = len(_LINK_RE.findall(head))
    for key in _LIST_KEYS:
        block = re.search(rf"^{key}:\s*\n((?:\s*-\s*.+\n?)+)", fm_text, re.MULTILINE)
        if block:
            conn += block.group(1).count("- ")
        else:
            inline = re.search(rf"^{key}:\s*\[(.+?)\]", fm_text, re.MULTILINE)
            if inline:
                conn += inline.group(1).count(",") + 1
    is_anime = "anime" in head.lower()
    links = []
    for lm in re.finditer(r"\[\[([^\]|]+?)(?:\|[^\]]*)?\]\]", head):
        t = lm.group(1).strip().lower()
        if t and t not in links:
            links.append(t)
        if len(links) >= 40:
            break
    return {"label": label, "rating": rating, "conn": conn, "size": size,
            "rel": path.name, "slug": path.stem.lower(), "links": links,
            "anime": is_anime, "path": str(path)}


def _iter_md(dirs: list[Path]):
    for d in dirs:
        if not d or not d.exists():
            continue
        for dp, dns, fns in os.walk(d):
            dns[:] = [x for x in dns if x not in ("__pycache__", ".git")]
            for n in fns:
                if n.endswith(".md"):
                    yield Path(dp, n)


def _combined(nodes: list[dict]) -> None:
    """SR: normalizuj rating/conn/size u regionu i spoji u `score` (0..1).
    Težine: ocena 0.4, veze 0.35, veličina 0.25."""
    if not nodes:
        return
    def norm(vals):
        lo, hi = min(vals), max(vals)
        rng = (hi - lo) or 1.0
        return lambda v: (v - lo) / rng
    fr = norm([n["rating"] for n in nodes])
    fc = norm([n["conn"] for n in nodes])
    fs = norm([n["size"] for n in nodes])
    for n in nodes:
        n["score"] = round(0.4 * fr(n["rating"]) + 0.35 * fc(n["conn"]) + 0.25 * fs(n["size"]), 4)


# --- keš: (potpis foldera) -> (ts, regions_full, index) ---
# SR: PERFORMANSE — (1) indeks slug->putanja (O(1) umesto os.walk kroz ~6000
#     fajlova pri svakoj navigaciji), (2) keš se UVEK servira odmah, a osvežava se
#     u POZADINSKOJ niti kad istekne TTL (nema više čekanja od ~3s), (3) keš je
#     i na disku (data/cache/brain_regions.json) pa je i hladan start trenutan.
_CACHE: dict[str, tuple[float, list[dict], dict]] = {}
_CACHE_TTL = 300.0  # 5 min — posle toga osveži u pozadini (stari se servira odmah)
_REBUILD_LOCK = threading.Lock()
_REBUILDING: set[str] = set()


def _dir_signature(d) -> str:
    """Potpis jednog direktorijuma (putanja:mtime); nedostupan -> :0."""

    try:
        st = d.stat()
        return f"{d}:{int(st.st_mtime)}"
    except OSError:
        return f"{d}:0"


def _signature(configs: list[dict]) -> str:
    parts = []
    for c in configs:
        for d in c.get("dirs", []):
            parts.append(_dir_signature(d))
    return "|".join(parts)


# --- AUX regioni (nisu prstenovi): skills/alati/problemi atomi, dostupni resolve-u ---
_AUX_DIRS = {
    "skills": lambda root: [root / ".ai" / "atomi" / "filmium" / "skills"],
    "alati": lambda root: [root / ".ai" / "atomi" / "filmium" / "alati"],
    "problemi": lambda root: [root / ".ai" / "atomi" / "filmium" / "problemi"],
}


def _all_search_dirs(root: Path) -> list[tuple[str, Path]]:
    out: list[tuple[str, Path]] = []
    for c in region_configs(root):
        for d in c.get("dirs", []):
            out.append((c["key"], d))
    for key, fn in _AUX_DIRS.items():
        for d in fn(root):
            out.append((key, d))
    return out


def _scan(root: Path, configs: list[dict]) -> list[dict]:
    """Sinhrono skeniranje svih foldera -> regions_full (sporo; radi se retko)."""
    per_region: dict[str, list[dict]] = {c["key"]: [] for c in configs}
    anime_bucket: list[dict] = []
    for c in configs:
        if c.get("derived") == "anime":
            continue
        for path in _iter_md(c["dirs"]):
            m = _atom_metrics(path)
            if not m:
                continue
            m["region"] = c["key"]
            if m.get("anime") and c["key"] in ("filmovi", "serije"):
                m["region"] = "anime"
                anime_bucket.append(m)
            else:
                per_region[c["key"]].append(m)
    per_region["anime"] = anime_bucket
    regions_full = []
    for c in configs:
        nodes = per_region.get(c["key"], [])
        _combined(nodes)
        nodes.sort(key=lambda n: n["score"], reverse=True)
        regions_full.append({"key": c["key"], "label": c["label"], "icon": c["icon"],
                             "count": len(nodes), "nodes": nodes})
    return regions_full


def _build_index(regions_full: list[dict], root: Path) -> dict:
    """slug -> {region, path, rel} za SVE atome (regioni + aux) — O(1) resolve."""
    idx: dict[str, dict] = {}
    for r in regions_full:
        for n in r["nodes"]:
            sl = n.get("slug")
            p = n.get("path")
            if sl and p and sl not in idx:
                idx[sl] = {"region": r["key"], "path": p, "rel": n.get("rel", "")}
    for key, fn in _AUX_DIRS.items():
        for d in fn(root):
            if not d or not d.exists():
                continue
            for dp, dns, fns in os.walk(d):
                dns[:] = [x for x in dns if x not in ("__pycache__", ".git")]
                for f in fns:
                    if f.endswith(".md"):
                        sl = f[:-3].lower()
                        if sl not in idx:
                            idx[sl] = {"region": key, "path": str(Path(dp, f)), "rel": f}
    return idx


def _disk_cache_path(root: Path) -> Path:
    return root / "data" / "cache" / "brain_regions.json"


def _load_disk(root: Path, sig: str):
    try:
        d = json.loads(_disk_cache_path(root).read_text(encoding="utf-8"))
        if d.get("sig") == sig and d.get("regions_full") is not None and d.get("index") is not None:
            return d["regions_full"], d["index"], float(d.get("ts", 0))
    except Exception:  # noqa: BLE001, S110
        pass
    return None


def _save_disk(root: Path, sig: str, ts: float, regions_full: list[dict], index: dict) -> None:
    try:
        p = _disk_cache_path(root)
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp = p.with_suffix(".tmp")
        tmp.write_text(json.dumps({"sig": sig, "ts": ts, "regions_full": regions_full, "index": index}),
                       encoding="utf-8")
        tmp.replace(p)
    except Exception:  # noqa: BLE001, S110
        pass


def _rebuild(root: Path) -> None:
    key = str(root)
    try:
        configs = region_configs(root)
        sig = _signature(configs)
        regions_full = _scan(root, configs)
        index = _build_index(regions_full, root)
        ts = time.time()
        _CACHE[sig] = (ts, regions_full, index)
        _save_disk(root, sig, ts, regions_full, index)
    finally:
        with _REBUILD_LOCK:
            _REBUILDING.discard(key)


def _spawn_rebuild(root: Path) -> None:
    key = str(root)
    with _REBUILD_LOCK:
        if key in _REBUILDING:
            return
        _REBUILDING.add(key)
    threading.Thread(target=_rebuild, args=(root,), daemon=True, name="brain-regions-rebuild").start()


def _get_full(root: Path, force: bool = False) -> tuple[list[dict], dict]:
    """(regions_full, index) — ODMAH iz memorije/diska; osveži u pozadini kad istekne."""
    configs = region_configs(root)
    sig = _signature(configs)
    now = time.time()
    hit = _CACHE.get(sig)
    if hit and not force:
        if (now - hit[0]) >= _CACHE_TTL:
            _spawn_rebuild(root)
        return hit[1], hit[2]
    if not force:
        disk = _load_disk(root, sig)
        if disk:
            regions_full, index, ts = disk
            _CACHE[sig] = (ts, regions_full, index)
            if (now - ts) >= _CACHE_TTL:
                _spawn_rebuild(root)
            return regions_full, index
    # prvi put (nema ni memorije ni diska): sinhrono
    _rebuild(root)
    hit = _CACHE.get(_signature(region_configs(root)))
    return (hit[1], hit[2]) if hit else ([], {})


def build_regions(root: Path, top_n: int = 16, force: bool = False) -> dict:
    regions_full, _ = _get_full(root, force)
    return _shape(regions_full, top_n)


def _slug_region_map(regions_full: list[dict]) -> dict:
    """slug -> {region, conn} (conn = broj veza tog atoma, za prikaz uz tačku veze)."""
    m: dict[str, dict] = {}
    for r in regions_full:
        for n in r["nodes"]:
            sl = n.get("slug")
            if sl and sl not in m:
                m[sl] = {"region": r["key"], "conn": int(n.get("conn", 0) or 0)}
    return m


def _link_regions(links: list, slug_map: dict) -> list:
    out = []
    for t in links:
        ent = slug_map.get(t)
        if ent:
            out.append({"slug": t, "region": ent["region"], "conn": ent["conn"]})
    return out


def _node_out(key: str, n: dict, slug_map: dict) -> dict:
    return {"id": f"{key}:{n['rel']}", "label": n["label"], "score": n["score"],
            "rel": n["rel"], "region": key, "slug": n.get("slug", ""),
            "links": n.get("links", []),
            "link_regions": _link_regions(n.get("links", []), slug_map),
            "rating": round(n["rating"], 2), "conn": n["conn"]}


def _shape(regions_full: list[dict], top_n: int) -> dict:
    slug_map = _slug_region_map(regions_full)
    out = []
    for r in regions_full:
        out.append({"key": r["key"], "label": r["label"], "icon": r["icon"], "count": r["count"],
                    "nodes": [_node_out(r["key"], n, slug_map) for n in r["nodes"][:top_n]]})
    return {"regions": [r for r in out if r["count"] > 0],
            "total": sum(r["count"] for r in out)}


def region_nodes(root: Path, key: str, offset: int = 0, limit: int = 200, lite: bool = False) -> dict:
    """Drill-down: čvorovi jednog regiona (paginirano), po skoru. `lite` = bez
    veza (links/link_regions) — mnogo manji odgovor; veze se učitaju na klik."""
    full, _ = _get_full(root)
    region = next((r for r in full if r["key"] == key), None)
    if region is None:
        return {"key": key, "count": 0, "nodes": []}
    nodes = region["nodes"][offset:offset + limit]
    if lite:
        out = [{"id": f"{key}:{n['rel']}", "label": n["label"], "score": n["score"], "rel": n["rel"],
                "region": key, "slug": n.get("slug", ""), "links": [], "link_regions": [],
                "rating": round(n["rating"], 2), "conn": n["conn"]} for n in nodes]
    else:
        slug_map = _slug_region_map(full)
        out = [_node_out(key, n, slug_map) for n in nodes]
    return {"key": key, "label": region["label"], "count": region["count"], "nodes": out}


def _find_by_walk(root: Path, target: str):
    """Rezervni spori put (samo ako indeks ne zna za fajl)."""
    for rk, d in _all_search_dirs(root):
        if not d or not d.exists():
            continue
        for dp, dns, fns in os.walk(d):
            dns[:] = [x for x in dns if x not in ("__pycache__", ".git")]
            if target in fns:
                return rk, Path(dp, target)
    return None, None


def resolve_slug(root: Path, slug: str, limit: int = 200_000) -> dict:
    """Nadji atom po slugu (O(1) preko indeksa) i vrati ceo čvor + sadržaj."""
    slug = (slug or "").strip().lower()
    if not slug:
        return {"found": False, "slug": slug}
    regions_full, index = _get_full(root)
    ent = index.get(slug)
    fp = None
    region_key = None
    if ent:
        p = Path(ent["path"])
        if p.exists():
            fp, region_key = p, ent["region"]
    if fp is None:
        region_key, fp = _find_by_walk(root, f"{slug}.md")
    if fp is None:
        return {"found": False, "slug": slug}
    m = _atom_metrics(fp) or {}
    try:
        content = fp.read_text(encoding="utf-8", errors="ignore")[:limit]
    except OSError:
        content = ""
    reg = region_key
    if m.get("anime") and region_key in ("filmovi", "serije"):
        reg = "anime"
    slug_map = _slug_region_map(regions_full)
    return {"found": True, "slug": slug, "region": reg, "rel": fp.name,
            "label": m.get("label", slug), "score": m.get("score", 0.0),
            "rating": round(m.get("rating", 0.0), 2), "conn": m.get("conn", 0),
            "links": m.get("links", []),
            "link_regions": _link_regions(m.get("links", []), slug_map),
            "content": content}


def read_region_file(root: Path, region: str, rel: str, limit: int = 200_000) -> dict:
    """Sadržaj jednog atom fajla (O(1) preko indeksa; rezervno os.walk)."""
    rel_name = Path(rel).name
    slug = (rel_name.removesuffix(".md")).lower()
    _, index = _get_full(root)
    ent = index.get(slug)
    fp = Path(ent["path"]) if ent else None
    if fp is None or not fp.exists():
        _, fp = _find_by_walk(root, rel_name)
    if fp is None:
        return {"region": region, "rel": rel_name, "content": "", "error": "not_found"}
    try:
        text = fp.read_text(encoding="utf-8", errors="ignore")[:limit]
    except OSError:
        return {"region": region, "rel": rel_name, "content": "", "error": "read"}
    return {"region": region, "rel": rel_name, "content": text}


def search_atoms(root: Path, q: str, limit: int = 30) -> dict:
    """Napredni pretraživač: naziv/slug kroz sve regione + aux (iz indeksa/keša)."""
    q = (q or "").strip().lower()
    if len(q) < 2:
        return {"query": q, "results": []}
    full, index = _get_full(root)
    results: list[dict] = []
    for r in full:
        for n in r["nodes"]:
            label = str(n.get("label", ""))
            slug = str(n.get("slug", ""))
            if q in label.lower() or q in slug.lower():
                results.append({"label": label, "slug": slug, "region": r["key"],
                                "rel": n["rel"], "conn": n.get("conn", 0), "score": n.get("score", 0)})
    for sl, ent in index.items():
        if ent.get("region") in _AUX_DIRS and q in sl:
            results.append({"label": sl, "slug": sl, "region": ent["region"],
                            "rel": ent.get("rel", f"{sl}.md"), "conn": 0, "score": 0})

    def _rank(x: dict):
        return (0 if x["label"].lower().startswith(q) else 1, -int(x.get("conn", 0)))

    results.sort(key=_rank)
    seen = set()
    uniq = []
    for x in results:
        k = (x["region"], x["slug"])
        if k in seen:
            continue
        seen.add(k)
        uniq.append(x)
    return {"query": q, "results": uniq[:limit]}
