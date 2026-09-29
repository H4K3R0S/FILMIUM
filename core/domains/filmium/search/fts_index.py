# core/domains/filmium/search/fts_index.py
# ==========          FTS5 INDEKS ATOMA (leksicki sloj)          ==========
# SQLite FTS5 nad atomima ove ćelije (.ai/atomi/**/*.md) + globalnim vault-om.
# Namerno u `core/domains/filmium/` (a ne u generisanom `core/rag/`) da preživi
# eventualni budući `--update`/`build_cell` prepis CORE-a (v. UNAPREDJENJE
# 01-ARHITEKTURA/02-hibridna-pretraga.md, [CAVEAT]).
#
# NAJVAŽNIJE: ovaj sloj NE zavisi od Postgresa/mreže — radi i kad je RAG dole.
# Sve funkcije su tolerantne: greška -> prazna lista / no-op / 0, nikad izuzetak
# napolje (isti duh kao `LocalRetriever`/`fallthrough.py`).
from __future__ import annotations

import logging
import re
import sqlite3
from pathlib import Path

from core.foundation.paths import core_paths

_logger = logging.getLogger(__name__)

# Maks. dužina snippeta (isti ugovor kao LocalRetriever/CORE `_search`).
_SNIPPET_MAX = 400

_DB_PATH = core_paths.data / "search" / "atoms_fts.db"
_TABLE = "atom_fts"
_META_TABLE = "atom_fts_meta"

# Izvori atoma: sopstvena baza ćelije (personas/tools/commands + nauceno/, ako
# postoji) + globalni vault (deljen medju domenima, van ove ćelije).
_ATOM_ROOTS: tuple[Path, ...] = (core_paths.root / ".ai" / "atomi",)
def _resolve_ai_runtime() -> Path | None:
    import os
    for _c in (os.environ.get("AI_RUNTIME"), str(Path.home() / "ai" / "core-infrastructure"),
               str(Path.home() / ".local" / "share" / "ai-runtime"), "/opt/ai-runtime"):
        if _c and (Path(_c) / "runtime.json").is_file():
            return Path(_c)
    return None

_AI_RUNTIME = _resolve_ai_runtime()
_GLOBAL_VAULT = (_AI_RUNTIME / "vector-dbs" / "global_graph_vault") if _AI_RUNTIME else None
# FILMIUM Actors folder (person atomi žive tu, deljeno na mount root-u).
_ACTORS_ROOT = Path("/run/media/kalima/FILMIUM/Actors")

# bm25() težine za (title, tags, body) — naslov najbitniji, telo najmanje.
_BM25_WEIGHTS = "3.0, 2.0, 1.0"

_TOKEN_RE = re.compile(r"[^0-9A-Za-zčćšđžČĆŠĐŽ]+")
_DJ_RE = re.compile(r"[dD][jJ]")


def _connect() -> sqlite3.Connection:
    """Otvori (i po potrebi napravi) FTS5 bazu. NIKAD na NTFS — `data/search/`
    je uvek na lokalnom (ext4) disku ćelije preko `core_paths.data`."""
    _DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(str(_DB_PATH))
    # Performanse (v. 09-performanse-i-odziv.md, poluga #5).
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("PRAGMA synchronous=NORMAL")
    con.execute("PRAGMA cache_size=-8000")  # ~8MB keš stranica
    con.execute(
        f"""
        CREATE VIRTUAL TABLE IF NOT EXISTS {_TABLE} USING fts5(
            id UNINDEXED,
            title,
            tags,
            type UNINDEXED,
            status UNINDEXED,
            confidence UNINDEXED,
            updated UNINDEXED,
            body,
            path UNINDEXED,
            mtime UNINDEXED,
            tokenize='unicode61 remove_diacritics 2'
        )
        """
    )
    con.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {_META_TABLE} (
            path TEXT PRIMARY KEY,
            mtime REAL NOT NULL
        )
        """
    )
    return con


def _parse_frontmatter(text: str) -> tuple[dict[str, str], str]:
    """Prost parser YAML-like frontmatter-a (bez ugnježdenih mapa).

    Podržava `---\\nkey: value\\n---\\ntelo` i liste u obliku `[a, b, c]`
    (spljoštene u tekst razdvojen razmakom — dovoljno za FTS pretragu).
    Tolerantan na CRLF (atomi u ovoj ćeliji imaju `\\r\\n` završetke).
    """
    norm = text.replace("\r\n", "\n").replace("\r", "\n")
    meta: dict[str, str] = {}
    if not norm.startswith("---"):
        return meta, norm.strip()
    end = norm.find("\n---", 3)
    if end == -1:
        return meta, norm.strip()
    raw_meta = norm[3:end].strip("\n")
    nl = norm.find("\n", end + 1)
    body = norm[nl + 1 :] if nl != -1 else ""
    for line in raw_meta.splitlines():
        if ":" not in line or line.strip().startswith("#"):
            continue
        key, _, val = line.partition(":")
        key = key.strip().lower()
        val = val.strip()
        if val.startswith("[") and val.endswith("]"):
            val = " ".join(v.strip() for v in val[1:-1].split(",") if v.strip())
        meta[key] = val
    return meta, body.strip()


def _iter_atom_files() -> list[Path]:
    """Svi `.md` atomi za indeksiranje (domenska baza + globalni vault)."""
    seen: set[Path] = set()
    out: list[Path] = []
    for root in filter(None, (*_ATOM_ROOTS, _GLOBAL_VAULT, _ACTORS_ROOT)):
        try:
            if not root.exists():
                continue
            for p in sorted(root.rglob("*.md")):
                rp = p.resolve()
                if rp not in seen and p.is_file():
                    seen.add(rp)
                    out.append(p)
        except Exception as error:  # noqa: BLE001 — skener nije kritičan
            _logger.debug("fts_index: skener nije uspeo za %s (%s)", root, error)
    return out


def _index_row(con: sqlite3.Connection, p: Path, mtime: float) -> bool:
    """Upiši/osveži jedan atom u indeks. `True` ako je uspelo."""
    try:
        raw = p.read_text(encoding="utf-8", errors="replace")
    except Exception as error:  # noqa: BLE001
        _logger.debug("fts_index: čitanje nije uspelo za %s (%s)", p, error)
        return False
    try:
        meta, body = _parse_frontmatter(raw)
        atom_id = meta.get("id") or p.stem
        title = meta.get("title") or p.stem
        path_key = str(p)
        con.execute(f"DELETE FROM {_TABLE} WHERE path = ?", (path_key,))
        con.execute(
            f"""INSERT INTO {_TABLE}
                (id, title, tags, type, status, confidence, updated, body, path, mtime)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                atom_id,
                title,
                meta.get("tags", ""),
                meta.get("type", ""),
                meta.get("status", ""),
                meta.get("confidence", ""),
                meta.get("updated", ""),
                body,
                path_key,
                mtime,
            ),
        )
        con.execute(
            f"""INSERT INTO {_META_TABLE}(path, mtime) VALUES (?, ?)
                ON CONFLICT(path) DO UPDATE SET mtime = excluded.mtime""",
            (path_key, mtime),
        )
        return True
    except Exception as error:  # noqa: BLE001 — indeksiranje jednog atoma nije kritično
        _logger.debug("fts_index: indeksiranje nije uspelo za %s (%s)", p, error)
        return False


def rebuild() -> int:
    """Puna re-indeksacija svih atoma. Vraća broj indeksiranih (0 na grešku)."""
    try:
        con = _connect()
    except Exception as error:  # noqa: BLE001
        _logger.debug("fts_index: rebuild — konekcija nije uspela (%s)", error)
        return 0
    try:
        count = 0
        with con:
            con.execute(f"DELETE FROM {_TABLE}")
            con.execute(f"DELETE FROM {_META_TABLE}")
            for p in _iter_atom_files():
                try:
                    mtime = p.stat().st_mtime
                except Exception:  # noqa: BLE001, S112
                    continue
                if _index_row(con, p, mtime):
                    count += 1
        return count
    except Exception as error:  # noqa: BLE001
        _logger.debug("fts_index: rebuild nije uspeo (%s)", error)
        return 0
    finally:
        con.close()


def sync() -> int:
    """Inkrementalna sinhronizacija po `mtime`. Vraća broj izmenjenih/novih/
    obrisanih atoma (0 na grešku ili kad nema promena)."""
    try:
        con = _connect()
    except Exception as error:  # noqa: BLE001
        _logger.debug("fts_index: sync — konekcija nije uspela (%s)", error)
        return 0
    try:
        known = dict(con.execute(f"SELECT path, mtime FROM {_META_TABLE}").fetchall())
        seen: set[str] = set()
        changed = 0
        with con:
            for p in _iter_atom_files():
                path_key = str(p)
                seen.add(path_key)
                try:
                    mtime = p.stat().st_mtime
                except Exception:  # noqa: BLE001, S112
                    continue
                if known.get(path_key) == mtime:
                    continue
                if _index_row(con, p, mtime):
                    changed += 1
            stale = set(known) - seen
            for path_key in stale:
                con.execute(f"DELETE FROM {_TABLE} WHERE path = ?", (path_key,))
                con.execute(f"DELETE FROM {_META_TABLE} WHERE path = ?", (path_key,))
                changed += 1
        return changed
    except Exception as error:  # noqa: BLE001
        _logger.debug("fts_index: sync nije uspeo (%s)", error)
        return 0
    finally:
        con.close()


def count() -> int:
    """Broj trenutno indeksiranih atoma (0 na grešku ili prazan indeks)."""
    try:
        con = _connect()
        try:
            row = con.execute(f"SELECT COUNT(*) FROM {_TABLE}").fetchone()
            return int(row[0]) if row else 0
        finally:
            con.close()
    except Exception as error:  # noqa: BLE001
        _logger.debug("fts_index: count nije uspeo (%s)", error)
        return 0


def _dj_variants(token: str) -> set[str]:
    """Dopuna za 'đ' koje `unicode61 remove_diacritics 2` NE preslikava (za
    razliku od č/ć/š/ž — empirijski provereno pri implementaciji ove ćelije).
    Doda alternativne zapise upita (đ<->d<->dj) da oba stila kucanja rade."""
    variants = {token}
    if "đ" in token or "Đ" in token:
        variants.add(token.replace("đ", "d").replace("Đ", "D"))
        variants.add(token.replace("đ", "dj").replace("Đ", "Dj"))
    if _DJ_RE.search(token):
        variants.add(_DJ_RE.sub("đ", token))
    return variants


_PREFIX_MIN_LEN = 4  # kraći tokeni (npr. "IP", "CVE") -> egzaktan, ne prefiks


def _stem_prefixes(v: str) -> set[str]:
    """Dodatne stem-prefiks varijante za srpsku fleksiju (komande->komandi,
    izmene->izmena, pretraga->pretragu): skrati token za 1-2 znaka pa prefiks-
    matchuj. SAMO DODAJE kandidate (OR); rerank/BM25 i dalje favorizuju tačniji,
    duži pogodak, pa ne kvari domene koji su već 100%. Kratki tokeni netaknuti."""
    out = {v}
    if len(v) >= 5:
        out.add(v[:-1])
    if len(v) >= 7:
        out.add(v[:-2])
    return out


def _fts_query(query: str) -> str:
    """Pretvori slobodan upit u bezbedan FTS5 MATCH izraz.

    Tokenizuje ručno (bez specijalnih FTS5 znakova u tokenima -> nema rizika
    od sintaksne greške/injekcije). Token dug ≥4 znaka ide kao prefiks
    (`"tok"*`, bolji recall na delimično kucanje); kraći token ide egzaktno
    (bez `*`) da ne pokupi šum iz svakog naslova koji slučajno počinje istim
    slovima (npr. "rec" ne sme pogoditi "Recon"/"recept"/...). OR spojeno."""
    tokens = [t for t in _TOKEN_RE.split(query) if t]
    if not tokens:
        return ""
    parts: list[str] = []
    seen: set[str] = set()
    for tok in tokens:
        for variant in _dj_variants(tok):
            for v in _stem_prefixes(variant.replace('"', "")):
                if not v or v in seen:
                    continue
                seen.add(v)
                suffix = "*" if len(v) >= _PREFIX_MIN_LEN else ""
                parts.append(f'"{v}"{suffix}')
    return " OR ".join(parts)


def search(query: str, k: int = 5) -> list[dict]:
    """BM25 leksička pretraga. Vraća listu rečnika:
    {id, title, type, status, confidence, updated, path, snippet, rank}.
    Prazna lista na svaku grešku (nema baze, oštećen indeks, prazan upit)."""
    q = (query or "").strip()
    if not q:
        return []
    try:
        con = _connect()
    except Exception as error:  # noqa: BLE001
        _logger.debug("fts_index: search — konekcija nije uspela (%s)", error)
        return []
    try:
        fts_q = _fts_query(q)
        if not fts_q:
            return []
        rows = con.execute(
            f"""
            SELECT id, title, type, status, confidence, updated, path, body,
                   bm25({_TABLE}, {_BM25_WEIGHTS}) AS rank
            FROM {_TABLE}
            WHERE {_TABLE} MATCH ?
            ORDER BY rank
            LIMIT ?
            """,
            (fts_q, max(1, int(k))),
        ).fetchall()
    except Exception as error:  # noqa: BLE001 — npr. loš MATCH sintaksa
        _logger.debug("fts_index: search nije uspeo (%s)", error)
        return []
    finally:
        con.close()

    out: list[dict] = []
    for atom_id, title, atype, status, confidence, updated, path, body, rank in rows:
        snippet = (body or title or "").strip()[:_SNIPPET_MAX]
        if not snippet:
            continue
        out.append(
            {
                "id": atom_id,
                "title": title,
                "type": atype,
                "status": status,
                "confidence": confidence,
                "updated": updated,
                "path": path,
                "snippet": snippet,
                "rank": rank,
            }
        )
    return out
