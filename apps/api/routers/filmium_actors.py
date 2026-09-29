# core/../apps/api/routers/filmium_actors.py
# ==========          FILMIUM ACTORS ROUTER          ==========
# Lista glumaca + detalj (bio, datum/mesto rođenja, galerija, filmografija sa
# statusom "u biblioteci" / "za dodavanje"). Podaci: filmium_people +
# filmium_media_people (link) + filmium_media_items (katalog). Slike se serviraju
# iz /run/media/kalima/FILMIUM/Actors/<Ime>/... Sve tolerantno.
from __future__ import annotations

import json
import re
import sqlite3
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse

from core.foundation.paths import core_paths

router = APIRouter(prefix="/api/v1/filmium", tags=["FILMIUM Actors"])

_ACTORS = Path("/run/media/kalima/FILMIUM/Actors")
_MOUNT = Path("/run/media/kalima/FILMIUM")


def _fs(n: object) -> str:
    return (re.sub(r'[<>:"/\\|?*]', "", str(n)).strip().rstrip(". ") or "unknown")[:120]


def _load_professions(raw: object) -> list:
    """SR/EN: professions JSON -> lista (bezbedno). / safe JSON->list."""
    try:
        val = json.loads(raw or "[]")
        return val if isinstance(val, list) else []
    except Exception:  # noqa: BLE001
        return []


def _con() -> sqlite3.Connection:
    con = sqlite3.connect(str(core_paths.data / "filmium.db"))
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA busy_timeout = 5000")
    return con


@router.get("/actors")
def list_actors(
    q: str = Query("", description="pretraga po imenu"),
    role: str = Query("", description="'reditelj' za samo režisere, prazno za sve"),
    only_with_image: bool = Query(True),
    limit: int = Query(300, ge=1, le=2000),
    offset: int = Query(0, ge=0),
) -> dict:
    con = _con()
    try:
        where = ["1=1"]
        params: list = []
        if q:
            where.append("p.name LIKE ?"); params.append(f"%{q}%")
        if only_with_image:
            where.append("p.image_path IS NOT NULL")
        if role == "reditelj":
            where.append("p.is_director = 1")
        sql = f"""
            SELECT p.slug, p.name, p.image_path, p.is_director, p.gallery_count, p.birthday, p.place_of_birth, p.professions,
                   (SELECT COUNT(*) FROM filmium_media_people mp WHERE mp.person_id=p.id AND mp.role='glumac') AS film_count
            FROM filmium_people p WHERE {' AND '.join(where)}
            ORDER BY film_count DESC, p.name LIMIT ? OFFSET ?
        """
        rows = con.execute(sql, (*params, limit, offset)).fetchall()
        total = con.execute(f"SELECT COUNT(*) FROM filmium_people p WHERE {' AND '.join(where)}", params).fetchone()[0]
        items = []
        for r in rows:
            d = dict(r)
            d["professions"] = _load_professions(d.pop("professions", None))
            items.append(d)
        return {"total": total, "items": items}
    except Exception as e:  # noqa: BLE001
        return {"total": 0, "items": [], "error": str(e)}
    finally:
        con.close()


@router.get("/actors/{slug}")
def actor_detail(slug: str) -> dict:
    con = _con()
    try:
        p = con.execute("SELECT * FROM filmium_people WHERE slug=?", (slug,)).fetchone()
        if not p:
            raise HTTPException(status_code=404, detail="glumac nije nađen")
        p = dict(p)
        lib = con.execute(
            """SELECT mi.id AS media_id, mi.title, mi.release_year AS year, mi.media_type,
                      mi.tmdb_id, mi.poster_path, mp.role, mp.character, mp.sort_order
               FROM filmium_media_people mp JOIN filmium_media_items mi ON mi.id=mp.media_id
               WHERE mp.person_id=? ORDER BY mi.release_year DESC""",
            (p["id"],),
        ).fetchall()
        lib_by_tmdb = {r["tmdb_id"]: r["media_id"] for r in lib if r["tmdb_id"]}
        library_films = [{**dict(r), "in_library": True} for r in lib]
        # puna filmografija (TMDB) -> obeleži u biblioteci; ostali = "za dodavanje"
        try:
            filmo_raw = json.loads(p.get("filmography_json") or "[]")
        except Exception:  # noqa: BLE001
            filmo_raw = []
        filmo, seen = [], set()
        for f in filmo_raw:
            tid = f.get("tmdb_id")
            if not tid or tid in seen:
                continue
            seen.add(tid)
            filmo.append({
                "tmdb_id": tid, "title": f.get("title"), "year": f.get("year"),
                "media_type": f.get("media_type"), "character": f.get("character"),
                "role": f.get("role"),
                "in_library": tid in lib_by_tmdb, "media_id": lib_by_tmdb.get(tid),
            })
        return {
            "person": {
                "slug": p["slug"], "name": p["name"], "bio": p.get("bio"),
                "birthday": p.get("birthday"), "deathday": p.get("deathday"),
                "place_of_birth": p.get("place_of_birth"), "known_for": p.get("known_for"),
                "is_director": p.get("is_director"), "tmdb_person_id": p.get("tmdb_person_id"),
                "gallery_count": p.get("gallery_count") or 0,
                "professions": _load_professions(p.get("professions")),
                "native_name": p.get("native_name"), "imdb_id": p.get("imdb_id"),
            },
            "library_films": library_films,
            "filmography": filmo,
        }
    finally:
        con.close()


def _safe(path: Path) -> Path:
    rp = path.resolve()
    if not str(rp).startswith(str(_ACTORS.resolve())):
        raise HTTPException(status_code=403, detail="van dozvoljene putanje")
    if not rp.is_file():
        raise HTTPException(status_code=404, detail="nema slike")
    return rp


@router.get("/actors/{slug}/image")
def actor_image(slug: str):
    con = _con()
    try:
        row = con.execute("SELECT name, image_path FROM filmium_people WHERE slug=?", (slug,)).fetchone()
    finally:
        con.close()
    if not row or not row["image_path"]:
        raise HTTPException(status_code=404, detail="nema slike")
    return FileResponse(_safe(_MOUNT / row["image_path"]), media_type="image/jpeg")


@router.get("/actors/{slug}/gallery/{idx}")
def actor_gallery(slug: str, idx: int):
    con = _con()
    try:
        row = con.execute("SELECT name FROM filmium_people WHERE slug=?", (slug,)).fetchone()
    finally:
        con.close()
    if not row:
        raise HTTPException(status_code=404, detail="glumac nije nađen")
    return FileResponse(_safe(_ACTORS / _fs(row["name"]) / "gallery" / f"{idx:02d}.jpg"), media_type="image/jpeg")


@router.get("/media/{media_id}/cast")
def media_cast(media_id: int, limit: int = Query(0, ge=0, le=100)) -> dict:
    """Glumci (i reditelj) jednog filma/serije — za sekciju "Glumci" na stranici
    naslova. Sortirano po billing redosledu (sort_order); reditelj na kraju."""
    con = _con()
    try:
        rows = con.execute(
            """SELECT p.slug, p.name, p.image_path, p.is_director,
                      mp.role, mp.character, mp.sort_order
               FROM filmium_media_people mp JOIN filmium_people p ON p.id=mp.person_id
               WHERE mp.media_id=?
               ORDER BY (mp.role='reditelj') ASC, mp.sort_order ASC""",
            (media_id,),
        ).fetchall()
        items = [dict(r) for r in rows]
        if limit:
            items = items[:limit]
        return {"media_id": media_id, "total": len(rows), "cast": items}
    except Exception as e:  # noqa: BLE001
        return {"media_id": media_id, "total": 0, "cast": [], "error": str(e)}
    finally:
        con.close()
