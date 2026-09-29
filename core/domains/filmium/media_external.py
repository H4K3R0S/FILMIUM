#!/usr/bin/env python3
# core/domains/filmium/media_external.py
# ==========          FILMIUM SPOLJNO OBOGAĆIVANJE (EXTERNAL ENRICHMENT)          ==========
"""Jedinstveni izvor istine za spoljno obogaćivanje FILMIUM naslova /
Single source of truth for FILMIUM external enrichment.

SR: TMDB je PRIMARNI izvor. Ovi provajderi (IMDb / Rotten Tomatoes / TVmaze /
    Jikan) rade POSLE TMDB-a, koristeći osnovne TMDB podatke (naslov/godina/
    tip/imdb_id). Oni DODAJU samo ono što TMDB nema (npr. ocene sa drugih
    sajtova, studio za anime, mrežu za seriju) i NIKAD ne gaze neprazna TMDB
    polja.
EN: TMDB stays PRIMARY. These providers (IMDb / Rotten Tomatoes / TVmaze /
    Jikan) run AFTER TMDB, using TMDB basic info (title/year/type/imdb_id).
    They ADD only what TMDB lacks (external ratings, anime studio, TV network)
    and NEVER overwrite non-empty TMDB fields.

Zakon / Laws: keyless provajderi (nema kredencijala), sve degradira lepo —
`provider.fetch(...)` vraća ``None`` na bilo koji neuspeh i nikad ne diže
izuzetak. U OVOM okruženju Jikan (504) i IMDb ocene (bot-challenge) mogu vratiti
``None`` — to je očekivano, pipeline to tretira čisto.
"""

from __future__ import annotations

import json
import sqlite3
import time
from typing import Any

# SR: relativni uvoz već izgrađenih provajder-klijenata (ne pišemo ih iznova).
# EN: relative import of the already-built provider clients (we do NOT rewrite).
from .providers import imdb as imdb_provider
from .providers import jikan as jikan_provider
from .providers import rottentomatoes as rt_provider
from .providers import tvmaze as tvmaze_provider

# ----------          KONSTANTE / CONSTANTS          ----------

# SR: nove nullable kolone na filmium_media_items (idempotentni ALTER-i).
# EN: new nullable columns on filmium_media_items (idempotent ALTERs).
_NEW_COLUMNS: list[tuple[str, str]] = [
    ("imdb_id", "TEXT"),
    ("imdb_rating", "REAL"),
    ("imdb_votes", "INTEGER"),
    ("rt_tomatometer", "INTEGER"),
    ("rt_audience_score", "INTEGER"),
    ("rt_url", "TEXT"),
    ("tvmaze_id", "INTEGER"),
    ("tvmaze_rating", "REAL"),
    ("tvmaze_network", "TEXT"),
    ("tvmaze_status", "TEXT"),
    ("tvmaze_premiered", "TEXT"),
    ("mal_id", "INTEGER"),
    ("mal_score", "REAL"),
    ("mal_studio", "TEXT"),
    ("mal_episodes", "INTEGER"),
    ("mal_status", "TEXT"),
    ("external_enriched_at", "TEXT"),
]

# SR: labela izvora koju editor („Ocene" tab) prikazuje.
# EN: source label the editor ("Ocene"/Ratings tab) displays.
_LABEL = {
    "imdb": "IMDb",
    "rottentomatoes": "Rotten Tomatoes",
    "tvmaze": "TVmaze",
    "jikan": "MAL",
}

_PROVIDERS = {
    "imdb": imdb_provider,
    "rottentomatoes": rt_provider,
    "tvmaze": tvmaze_provider,
    "jikan": jikan_provider,
}


# ----------          POMOĆNE / HELPERS          ----------

def open_connection() -> sqlite3.Connection:
    """SR: otvori konekciju ka katalog bazi (data/filmium.db) sa busy_timeout
    (NTFS + živa ćelija). EN: open the catalog DB connection with busy_timeout
    (running cell on NTFS). Poziva je ruter / auto_update (koji nemaju `con`)."""
    from core.foundation.paths import core_paths

    con = sqlite3.connect(str(core_paths.data / "filmium.db"))
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA busy_timeout=10000")
    return con


def _now_iso() -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S")


def _as_list(raw: Any) -> list:
    """SR: tolerantno parsira JSON listu iz kolone (keywords/genres).
    EN: tolerant JSON-list parse from a column; accepts already-a-list too."""
    if not raw:
        return []
    if isinstance(raw, list):
        return raw
    try:
        value = json.loads(raw)
        return value if isinstance(value, list) else []
    except (TypeError, ValueError):
        return []


def _as_dict(raw: Any) -> dict:
    """SR/EN: tolerant JSON-object parse (editor_settings)."""
    if not raw:
        return {}
    if isinstance(raw, dict):
        return dict(raw)
    try:
        value = json.loads(raw)
        return dict(value) if isinstance(value, dict) else {}
    except (TypeError, ValueError):
        return {}


def _mostly_ascii(text: str) -> bool:
    """SR: da li je string pretežno ASCII (bira latinični naslov za engleske
    provajdere umesto npr. japanskog originala). EN: is the string mostly ASCII
    (pick a Latin title for English providers over e.g. a Japanese original)."""
    try:
        ascii_chars = sum(1 for c in text if ord(c) < 128)
        return ascii_chars >= max(1, len(text)) * 0.8
    except Exception:  # noqa: BLE001
        return False


def _query_title(item: dict) -> str | None:
    """SR: najbolji naslov za spoljno poklapanje — engleski/latinični ima
    prednost (RT/IMDb/Jikan su na engleskom). EN: best title for external
    matching — prefer an English/Latin title (RT/IMDb/Jikan are English-first)."""
    for key in ("english_title", "original_title", "title"):
        value = item.get(key)
        if value and str(value).strip() and _mostly_ascii(str(value)):
            return str(value).strip()
    fallback = item.get("title") or item.get("original_title")
    return str(fallback).strip() if fallback and str(fallback).strip() else None


def _is_empty(value: Any) -> bool:
    return value is None or (isinstance(value, str) and value.strip() == "")


# ----------          ŠEMA / SCHEMA          ----------

def ensure_external_columns(con: sqlite3.Connection) -> None:
    """SR: idempotentno dodaj nullable kolone i napravi filmium_media_external
    tabelu. Bezbedno je pozvati više puta. EN: idempotently add the nullable
    columns and create the filmium_media_external table. Safe to call repeatedly."""
    existing = {row[1] for row in con.execute("PRAGMA table_info(filmium_media_items)")}
    for name, decl in _NEW_COLUMNS:
        if name not in existing:
            con.execute(
                f"ALTER TABLE filmium_media_items ADD COLUMN {name} {decl}"
            )
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS filmium_media_external (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            media_id INTEGER NOT NULL,
            source TEXT NOT NULL,
            matched INTEGER DEFAULT 0,
            payload_json TEXT,
            fetched_at TEXT,
            UNIQUE(media_id, source)
        )
        """
    )
    con.commit()


# ----------          RUTIRANJE / ROUTING          ----------

def _is_anime(item: dict) -> bool:
    """SR: detekcija animea iz TMDB osnove. EN: anime detection from TMDB basics.

    content_category=='anime' ILI 'anime' u keywords/genres ILI
    (original_language_code=='ja' I ('animation' u genres ili media_type serija)).
    """
    if (item.get("content_category") or "").strip().lower() == "anime":
        return True

    tokens = {
        str(x).strip().lower()
        for x in (*_as_list(item.get("keywords")), *_as_list(item.get("genres")))
        if x
    }
    if "anime" in tokens:
        return True

    if (item.get("original_language_code") or "").strip().lower() == "ja":
        media_type = (item.get("media_type") or "").strip().lower()
        # 'animation' (EN) ili 'animacija' (SR) u žanrovima, ili je serija.
        if tokens & {"animation", "animacija"} or media_type == "series":
            return True
    return False


def route_sources(item: dict) -> list[str]:
    """SR: iz TMDB osnove odluči koje provajdere zvati.
    EN: decide which providers to call from TMDB basics.

    movie  -> [rottentomatoes, imdb]
    series -> [tvmaze, imdb, rottentomatoes]
    anime  -> [jikan, imdb]  (dodaje jikan preko osnove kad se anime detektuje)
    """
    media_type = (item.get("media_type") or "").strip().lower()
    if media_type == "series":
        sources = ["tvmaze", "imdb", "rottentomatoes"]
    else:  # baza ima samo 'movie' | 'series'; sve ostalo tretiramo kao film.
        sources = ["rottentomatoes", "imdb"]

    # SR: anime detektovan -> DODAJ jikan (MAL je autoritet za anime), na čelo
    # da mu podaci imaju prednost pri popuni. EN: anime detected -> ADD jikan
    # (MAL is the anime authority), prepended so its data takes precedence.
    if _is_anime(item) and "jikan" not in sources:
        sources.insert(0, "jikan")
    return sources


# ----------          JEZGRO / CORE          ----------

def _load_item(con: sqlite3.Connection, media_id: int) -> dict | None:
    """SR: učitaj red + žanrove (žanrovi su u zasebnoj tabeli).
    EN: load the media row + genres (genres live in a separate table)."""
    row = con.execute(
        "SELECT * FROM filmium_media_items WHERE id=?", (media_id,)
    ).fetchone()
    if row is None:
        return None
    item = dict(row)
    try:
        genres = [
            r[0]
            for r in con.execute(
                "SELECT g.name FROM filmium_media_genres mg "
                "JOIN filmium_genres g ON g.id = mg.genre_id "
                "WHERE mg.media_id=?",
                (media_id,),
            ).fetchall()
        ]
    except Exception:  # noqa: BLE001
        genres = []
    item["genres"] = genres
    return item


def _load_existing_external(con: sqlite3.Connection, media_id: int) -> dict:
    """SR: postojeći filmium_media_external redovi {source: (matched, payload)}.
    EN: existing rows keyed by source; lets us skip re-fetching matched sources."""
    out: dict[str, dict] = {}
    try:
        for r in con.execute(
            "SELECT source, matched, payload_json FROM filmium_media_external "
            "WHERE media_id=?",
            (media_id,),
        ).fetchall():
            payload = None
            if r["payload_json"]:
                try:
                    payload = json.loads(r["payload_json"])
                except (TypeError, ValueError):
                    payload = None
            out[r["source"]] = {"matched": bool(r["matched"]), "payload": payload}
    except Exception:  # noqa: BLE001, S110
        pass
    return out


def _upsert_external(
    con: sqlite3.Connection,
    media_id: int,
    source: str,
    result: dict | None,
) -> None:
    """SR/EN: UPSERT one provider result into filmium_media_external."""
    con.execute(
        """
        INSERT INTO filmium_media_external (media_id, source, matched, payload_json, fetched_at)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(media_id, source) DO UPDATE SET
            matched = excluded.matched,
            payload_json = excluded.payload_json,
            fetched_at = excluded.fetched_at
        """,
        (
            media_id,
            source,
            1 if result else 0,
            json.dumps(result, ensure_ascii=False) if result else None,
            _now_iso(),
        ),
    )


def _collect_source_results(
    con: sqlite3.Connection, media_id: int, item: dict,
    routed: list, existing: dict, summary: dict, *, force: bool,
) -> dict:
    """Prikupi rezultate po izvoru (None ako nema poklapanja). Idempotentno:
    keširani payload se reuse-uje osim pri force; svež rezultat se UPSERT-uje.
    Menja `summary` (matched/reused)."""

    query_title = _query_title(item)
    year = item.get("release_year")
    imdb_id_in = item.get("imdb_id")
    media_type = item.get("media_type")

    results: dict[str, dict | None] = {}
    for source in routed:
        provider = _PROVIDERS.get(source)
        if provider is None:
            continue

        # SR: ako nije force i izvor je već uspešno poklopljen, iskoristi
        # keširani payload (idempotentno, bez ponovnog throttled poziva).
        # EN: reuse a previously matched payload unless force (idempotent, no
        # repeat throttled network call).
        prev = existing.get(source)
        if not force and prev and prev.get("matched") and prev.get("payload"):
            results[source] = prev["payload"]
            summary["reused"].append(source)
            summary["matched"][source] = True
            continue

        try:
            result = provider.fetch(
                query_title, year, imdb_id_in, media_type
            )
        except Exception:  # noqa: BLE001
            # Provajderi ne bi trebalo da dižu izuzetak, ali za svaki slučaj.
            result = None

        results[source] = result
        summary["matched"][source] = bool(result)
        # UPSERT sirovog (normalizovanog) rezultata — matched=bool(result).
        _upsert_external(con, media_id, source, result)
    return results


def _map_result_columns(results: dict, item: dict, summary: dict) -> dict:
    """Mapiraj rezultate provajdera u external-owned kolone. Postavi kolonu
    SAMO kad imamo vrednost (None ne briše postojeće). Vraća `updates`."""

    imdb_res = results.get("imdb")
    rt_res = results.get("rottentomatoes")
    tvmaze_res = results.get("tvmaze")
    jikan_res = results.get("jikan")

    updates: dict[str, Any] = {}

    def _set(col: str, value: Any) -> None:
        if value is not None:
            updates[col] = value
            summary["columns_filled"].append(col)

    if imdb_res:
        _set("imdb_rating", imdb_res.get("rating"))
        _set("imdb_votes", imdb_res.get("votes"))
        # imdb_id: postavi ako je provajder razrešio i kolona je prazna.
        resolved_imdb = imdb_res.get("imdb_id")
        if resolved_imdb and _is_empty(item.get("imdb_id")):
            _set("imdb_id", resolved_imdb)

    if rt_res:
        _set("rt_tomatometer", rt_res.get("tomatometer"))
        _set("rt_audience_score", rt_res.get("audience_score"))
        _set("rt_url", rt_res.get("url"))

    if tvmaze_res:
        _set("tvmaze_id", tvmaze_res.get("tvmaze_id"))
        _set("tvmaze_rating", tvmaze_res.get("rating"))
        _set("tvmaze_network", tvmaze_res.get("network"))
        _set("tvmaze_status", tvmaze_res.get("status"))
        _set("tvmaze_premiered", tvmaze_res.get("premiered"))

    if jikan_res:
        _set("mal_id", jikan_res.get("mal_id"))
        _set("mal_score", jikan_res.get("score"))
        _set("mal_studio", jikan_res.get("studio"))
        _set("mal_episodes", jikan_res.get("episodes"))
        _set("mal_status", jikan_res.get("status"))
    return updates


def _fill_tmdb_gaps(item: dict, results: dict, updates: dict,
                    summary: dict) -> None:
    """Popuni SAMO ono što TMDB nema (studio, runtime). Nikad ne gazi TMDB
    vrednost. Menja `updates` i `summary['tmdb_gaps_filled']`."""

    jikan_res = results.get("jikan")
    tvmaze_res = results.get("tvmaze")
    imdb_res = results.get("imdb")
    rt_res = results.get("rottentomatoes")

    # SR: studio prazan -> mal_studio (anime) inače tvmaze_network.
    # EN: studio empty -> mal_studio (anime) else tvmaze_network. Never overwrite.
    if _is_empty(item.get("studio")):
        studio_fill = None
        if _is_anime(item) and jikan_res and jikan_res.get("studio"):
            studio_fill = jikan_res.get("studio")
        elif tvmaze_res and tvmaze_res.get("network"):
            studio_fill = tvmaze_res.get("network")
        if studio_fill:
            updates["studio"] = studio_fill
            summary["tmdb_gaps_filled"]["studio"] = studio_fill

    # SR: runtime prazan i neki izvor ima trajanje -> postavi. (Normalizovani
    # izlazi provajdera ga trenutno ne izlažu, pa je ovo defanzivni guard.)
    # EN: runtime empty and a source exposes one -> set it (defensive; current
    # normalized provider outputs do not carry runtime).
    if _is_empty(item.get("runtime_minutes")) or not item.get("runtime_minutes"):
        for res in (jikan_res, tvmaze_res, imdb_res, rt_res):
            if not res:
                continue
            runtime = res.get("runtime_minutes") or res.get("runtime")
            try:
                runtime = int(runtime) if runtime else None
            except (TypeError, ValueError):
                runtime = None
            if runtime and runtime > 0:
                updates["runtime_minutes"] = runtime
                summary["tmdb_gaps_filled"]["runtime_minutes"] = runtime
                break


def _merge_imdb_rating(imdb_res: dict, updates: dict, item: dict,
                       external: dict, votes: dict) -> None:
    """IMDb ocena/glasovi u external+votes (url iz razrešenog imdb_id).
    Menja `external` i `votes`."""

    rating = imdb_res.get("rating")
    imdb_id_val = updates.get("imdb_id") or item.get("imdb_id") or imdb_res.get("imdb_id")
    if rating is not None or imdb_id_val:
        external[_LABEL["imdb"]] = {
            "score": rating,
            "scale": 10,
            "url": f"https://www.imdb.com/title/{imdb_id_val}/" if imdb_id_val else None,
        }
    if imdb_res.get("votes") is not None:
        votes[_LABEL["imdb"]] = imdb_res.get("votes")


def _merge_external_ratings(item: dict, results: dict, updates: dict) -> tuple:
    """Spoji spoljne ocene u editor_settings["ratings"]["external"/"votes"]
    (ključ = labela izvora). Čuva sve ostale ključeve. Vraća
    (external, votes, ratings_changed, settings)."""

    imdb_res = results.get("imdb")
    rt_res = results.get("rottentomatoes")
    tvmaze_res = results.get("tvmaze")
    jikan_res = results.get("jikan")

    settings = _as_dict(item.get("editor_settings"))
    ratings = dict(settings.get("ratings") or {})
    external = dict(ratings.get("external") or {})
    votes = dict(ratings.get("votes") or {})

    if imdb_res:
        _merge_imdb_rating(imdb_res, updates, item, external, votes)

    if rt_res and (rt_res.get("tomatometer") is not None or rt_res.get("audience_score") is not None):
        external[_LABEL["rottentomatoes"]] = {
            "tomatometer": rt_res.get("tomatometer"),
            "audience": rt_res.get("audience_score"),
            "scale": 100,
            "url": rt_res.get("url"),
        }

    if tvmaze_res and tvmaze_res.get("rating") is not None:
        external[_LABEL["tvmaze"]] = {
            "score": tvmaze_res.get("rating"),
            "scale": 10,
            "network": tvmaze_res.get("network"),
        }

    if jikan_res and jikan_res.get("score") is not None:
        external[_LABEL["jikan"]] = {
            "score": jikan_res.get("score"),
            "scale": 10,
            "studio": jikan_res.get("studio"),
            "episodes": jikan_res.get("episodes"),
        }

    ratings_changed = False
    if external:
        ratings["external"] = external
        ratings_changed = True
    if votes:
        ratings["votes"] = votes
        ratings_changed = True
    if ratings_changed:
        settings["ratings"] = ratings
    return external, votes, ratings_changed, settings


def apply_external_enrichment(
    con: sqlite3.Connection, media_id: int, *, force: bool = False
) -> dict:
    """SR: jezgro — pozovi rutirane provajdere, UPSERT-uj sirove rezultate,
    mapiraj u nove kolone, POPUNI SAMO ono što TMDB nema, i uglavi spoljne
    ocene u editor_settings. EN: the core — call routed providers, UPSERT raw
    results, map into new columns, FILL ONLY WHAT TMDB LACKS, and merge external
    ratings into editor_settings. Idempotentno; None se tretira čisto."""
    ensure_external_columns(con)

    item = _load_item(con, media_id)
    if item is None:
        return {"media_id": media_id, "error": "not_found"}

    summary: dict[str, Any] = {
        "media_id": media_id,
        "title": item.get("title"),
        "media_type": item.get("media_type"),
        "is_anime": _is_anime(item),
        "routed": [],
        "matched": {},
        "columns_filled": [],
        "tmdb_gaps_filled": {},
        "reused": [],
    }

    routed = route_sources(item)
    summary["routed"] = list(routed)

    existing = _load_existing_external(con, media_id)
    results = _collect_source_results(
        con, media_id, item, routed, existing, summary, force=force
    )

    updates = _map_result_columns(results, item, summary)
    _fill_tmdb_gaps(item, results, updates, summary)
    external, votes, ratings_changed, settings = _merge_external_ratings(
        item, results, updates
    )

    # ----------  UPIS U BAZU (batch UPDATE)  ----------
    updates["external_enriched_at"] = _now_iso()
    if ratings_changed:
        updates["editor_settings"] = json.dumps(settings, ensure_ascii=False)

    set_clause = ", ".join(f"{col}=?" for col in updates)
    params = list(updates.values()) + [media_id]
    con.execute(
        f"UPDATE filmium_media_items SET {set_clause} WHERE id=?", params
    )

    summary["ratings_external"] = external
    summary["ratings_votes"] = votes
    return summary


# ----------          MARKDOWN ZA ATOM / MARKDOWN FOR ATOM          ----------

def _ratings_imdb_line(data: dict) -> str | None:
    """IMDb linija: ocena (+glasovi/url) ili samo identitet bez ocene."""

    if data.get("imdb_rating") is not None:
        votes = data.get("imdb_votes")
        votes_txt = f" ({int(votes):,} glasova)" if votes else ""
        url = f"https://www.imdb.com/title/{data['imdb_id']}/" if data.get("imdb_id") else None
        suffix = f" — {url}" if url else ""
        return f"- IMDb: {data['imdb_rating']}/10{votes_txt}{suffix}"
    if data.get("imdb_id"):
        # SR: imamo IMDb identitet ali ne i ocenu (bot-challenge u ovom okruženju).
        return (
            f"- IMDb: (ocena nedostupna) — https://www.imdb.com/title/{data['imdb_id']}/"
        )
    return None


def _ratings_rt_line(data: dict) -> str | None:
    """Rotten Tomatoes linija (Tomatometer i/ili publika)."""

    if data.get("rt_tomatometer") is None and data.get("rt_audience_score") is None:
        return None
    parts = []
    if data.get("rt_tomatometer") is not None:
        parts.append(f"Tomatometer {data['rt_tomatometer']}%")
    if data.get("rt_audience_score") is not None:
        parts.append(f"publika {data['rt_audience_score']}%")
    url = data.get("rt_url")
    suffix = f" — {url}" if url else ""
    return f"- Rotten Tomatoes: {', '.join(parts)}{suffix}"


def _ratings_tvmaze_line(data: dict) -> str | None:
    """TVmaze linija (ocena + mreža)."""

    if data.get("tvmaze_rating") is None:
        return None
    net = f", {data['tvmaze_network']}" if data.get("tvmaze_network") else ""
    return f"- TVmaze: {data['tvmaze_rating']}/10{net}"


def _ratings_mal_line(data: dict) -> str | None:
    """MAL (MyAnimeList) linija (ocena/studio/epizode)."""

    if data.get("mal_score") is None and not data.get("mal_studio"):
        return None
    parts = []
    if data.get("mal_score") is not None:
        parts.append(f"{data['mal_score']}/10")
    if data.get("mal_studio"):
        parts.append(f"studio {data['mal_studio']}")
    if data.get("mal_episodes"):
        parts.append(f"{data['mal_episodes']} epizoda")
    if parts:
        return f"- MAL (MyAnimeList): {', '.join(parts)}"
    return None


def build_ratings_section(con: sqlite3.Connection, media_id: int) -> str:
    """SR: markdown blok „## ⭐ OCENE I SPOLJNI IZVORI" sa svim spoljnim ocenama
    koje postoje; "" ako nema nijedne. EN: markdown block listing whatever
    external ratings exist; returns "" if none. Guarded so a missing column
    never breaks atom generation."""
    try:
        row = con.execute(
            "SELECT imdb_id, imdb_rating, imdb_votes, "
            "rt_tomatometer, rt_audience_score, rt_url, "
            "tvmaze_rating, tvmaze_network, tvmaze_status, "
            "mal_score, mal_studio, mal_episodes, mal_status "
            "FROM filmium_media_items WHERE id=?",
            (media_id,),
        ).fetchone()
    except Exception:  # noqa: BLE001
        # SR: kolone možda još ne postoje (npr. stari DB). Ne ruši atom.
        # EN: columns may not exist yet; never break the atom.
        return ""
    if row is None:
        return ""

    data = dict(row)
    lines: list[str] = []
    for line in (
        _ratings_imdb_line(data),
        _ratings_rt_line(data),
        _ratings_tvmaze_line(data),
        _ratings_mal_line(data),
    ):
        if line:
            lines.append(line)

    if not lines:
        return ""

    return "## ⭐ OCENE I SPOLJNI IZVORI\n" + "\n".join(lines) + "\n"
