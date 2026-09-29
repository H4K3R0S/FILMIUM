# core/domains/filmium/jobs/tmdb_people_import.py
# ==========          POSAO: tmdb_people_import          ==========
"""Regeneriše atome FILMIUM biblioteke iz baze i (kad je TMDB ključ podešen)
osvežava kredite + preuzima slike glumaca/reditelja.

Generalizacija jednokratnog `gen_atoms.py` skripta (v. UNAPREDJENJE
01-ARHITEKTURA/01-atomski-standard-v2.md) u posao koji zna sam da nađe svoje
stavke iz `filmium_media_items` (umesto hardkodovane liste id-jeva).

`media_entry`/`collection` atomi ostaju u SOPSTVENOJ ćeliji
(`core_paths.root/.ai/atomi/filmium/{filmovi,serije,kolekcije}`). Person
atomi (i slike) VIŠE NISU u toj ćeliji — žive u `Actors/` obrascu na mount
root-u diska (`/run/media/kalima/FILMIUM/Actors/<fs_name(ime)>/`, DELJENO
između Windows/Linux dual-boot, isti koren kao `search/fts_index.py:
_ACTORS_ROOT`). `.ai/atomi/filmium/osobe/` se VIŠE NE PRAVI (dupliralo bi
Actors atome u pretrazi — v. `_iter_atom_files` u fts_index.py koja već
skenira i `_ACTORS_ROOT`).

Dva koraka, oba best-effort (nikad ne ruše posao):
  1. `_regenerate_atoms` — čita `filmium_media_items` (+ sezone/epizode za
     serije) i piše media_entry/collection atome + person atome u Actors/.
     UPSERT-uje `filmium_people`/`filmium_media_people` iz podataka koji već
     postoje u bazi (`cast_names`/`director`). RADI BEZ TMDB ključa (jeftino
     — samo baza + disk).
  2. `_fetch_tmdb_people` — SAMO ako je TMDB ključ STVARNO podešen (v.
     `_tmdb_ready` ispod — `tmdb_client.is_tmdb_available()` trenutno vraća
     True i za placeholder vrednosti iz `config/tmdb.json`, jer je to
     ne-prazan string; ovaj posao zato dodaje sopstvenu proveru placeholder
     obrasca da placeholder NE pokrene mrežne pozive). Osvežava
     `cast_names`/`director` u bazi (pun spisak, ne skraćen), preuzima slike
     glumaca/reditelja (top `CAST_CAP` po naslovu) u
     `Actors/<fs_name>/<fs_name>.jpg` (inkrementalno, preskače već
     preuzete) i obogaćuje `filmium_people`/`filmium_media_people` sa
     `character` i `tmdb_person_id` (iz TMDB `credits.cast`/`credits.crew`
     `id`-ja — nedostupno u ranijoj jednokratnoj migraciji).

Atom standard: id = slugify(title), dedup osoba preko slug-a, CAST_CAP=10
glavnih uloga po naslovu u TELU atoma (baza i dalje čuva pun cast).
"""
from __future__ import annotations

import contextlib as _contextlib
import json
import re
import sqlite3 as _sqlite3
import time
from pathlib import Path

from core.cell.jobs import Job, JobContext
from core.domains.filmium import atom_factory as _AF
from core.domains.filmium import tmdb_client as tmdb
from core.domains.filmium.cast_atom import build_cast_entity_atom, extract_professions
from core.domains.filmium.jobs.tmdb_people_atoms import (
    _atom_body,
    _atom_compact_meta,
    _atom_frontmatter,
    _jarr,
    _write_atom_or_error,
    slugify,
)
from core.domains.filmium.paths import filmium_paths
from core.foundation.paths import core_paths


@_contextlib.contextmanager
def _catalog_connection():
    """Konekcija ka FILMIUM KATALOG bazi (`data/filmium.db`) — NE `core.db`
    (prazan kernel db). Katalog (filmium_media_items sa cast_names/tmdb_id) je
    u filmium.db; _catalog_connection() otvara pogresnu, praznu bazu."""
    con = _sqlite3.connect(str(core_paths.data / "filmium.db"))
    con.row_factory = _sqlite3.Row
    try:
        yield con
        con.commit()
    finally:
        con.close()

# ----------          KONSTANTE          ----------
CAST_CAP = 10                 # top N glumaca po naslovu (u TELU atoma)
ATOM_BATCH_DEFAULT = 50       # koliko stavki iz baze po pozivu _regenerate_atoms (bez media_ids)
TMDB_SCAN_LIMIT = 5000         # koliko stavki sa tmdb_id se razmatra po pozivu _fetch_tmdb_people
TMDB_FETCH_LIMIT = 25         # koliko STVARNIH TMDB poziva (mrežnih) po pozivu — drži posao brzim/pristojnim

_PLACEHOLDER_HINTS = ("here put", "[")

# FILMIUM Actors folder — person atomi + slike žive OVDE, na mount root-u
# diska (DELJENO između Windows/Linux dual-boot). Hardkodovano identično
# `core/domains/filmium/search/fts_index.py:_ACTORS_ROOT` (NAMERNO — jedini
# izvor istine za ovaj koren je taj mount, ne `core_paths`, jer Actors/ nije
# unutar bilo koje pojedinačne kopije aplikacije).
_ACTORS_ROOT = Path("/run/media/kalima/FILMIUM/Actors")
_MOUNT_ROOT = Path("/run/media/kalima/FILMIUM")


def fs_name(name: object) -> str:
    """Sanitizuje ime osobe u bezbedan naziv foldera/fajla na disku — identično
    migracionom skriptu (`migrate_actors.py:fs_name`): skida karaktere koje
    Windows/NTFS ne dozvoljava, trimuje razmake/tačke, ograničava na 120
    znakova. Za razliku od `slugify`, čuva razmake/velika slova (folder se
    zove „Tom Hanks", ne „tom-hanks")."""
    cleaned = re.sub(r'[<>:"/\\|?*]', "", str(name)).strip().rstrip(". ")
    return cleaned[:120] or "unknown"


def _rel_to_mount(path: Path) -> str:
    """Putanja relativna na `_MOUNT_ROOT` (za `image_local`/`folder_path`/
    `image_path` — isti oblik kao migracioni skript, npr. `Actors/Tom Hanks/
    Tom Hanks.jpg`). Van mount-a (ne bi trebalo da se desi) — vraća apsolutnu."""
    try:
        return str(path.relative_to(_MOUNT_ROOT))
    except ValueError:
        return str(path)


def _now_iso() -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S")


def _looks_like_placeholder(value: str | None) -> bool:
    if not value:
        return True
    low = value.strip().lower()
    return any(hint in low for hint in _PLACEHOLDER_HINTS)


def _tmdb_ready() -> bool:
    """Da li je TMDB STVARNO spreman za mrežne pozive.

    NAPOMENA (bug u `tmdb_client.is_tmdb_available()`): ta funkcija vraća
    `True` čim je `access_token`/`api_key` bilo koji ne-prazan string —
    uključujući placeholder tekst iz `config/tmdb.json`
    (`"[ Here put API key for TMDB ]"`). Ovaj posao NE SME da pokrene
    mrežne pozive protiv placeholder vrednosti, pa ovde dodajemo eksplicitnu
    proveru da vrednost ne izgleda kao placeholder. `tmdb_client.py` NIJE
    menjan (van obima ovog zadatka) — ovo je dodatna, lokalna zaštita."""
    creds = tmdb.load_credentials()
    real_access = bool(creds.access_token) and not _looks_like_placeholder(creds.access_token)
    real_key = bool(creds.api_key) and not _looks_like_placeholder(creds.api_key)
    return real_access or real_key


def _credits_cast(data: dict | None, limit: int) -> list[dict]:
    """Cast iz `credits.cast` SA `profile_path`/`character`/`id` (za razliku od
    `tmdb_client._parse_cast`, koja vraća samo imena). Redosled je TMDB
    billing-order (već sortirano), dedup po imenu, ograničeno na `limit`."""
    if not isinstance(data, dict):
        return []
    credits = data.get("credits")
    if not isinstance(credits, dict):
        return []
    cast = credits.get("cast")
    if not isinstance(cast, list):
        return []
    out: list[dict] = []
    seen: set[str] = set()
    for member in cast:
        if not isinstance(member, dict):
            continue
        name = member.get("name")
        if not isinstance(name, str) or not name or name in seen:
            continue
        seen.add(name)
        out.append({
            "name": name,
            "character": member.get("character") if isinstance(member.get("character"), str) else None,
            "profile_path": member.get("profile_path") if isinstance(member.get("profile_path"), str) else None,
            "id": member.get("id") if isinstance(member.get("id"), int) else None,
        })
        if len(out) >= limit:
            break
    return out


def _credits_director(data: dict | None) -> dict | None:
    """Reditelj iz `credits.crew` (SAMO filmovi) SA TMDB `id`-jem osobe — za
    razliku od `tmdb_client._parse_director` (samo ime; taj takođe pokriva
    `created_by` kod serija, koje nemaju ekvivalentan `id` u istom obliku pa
    ovde ostaju van dometa — `tmdb_person_id` im ostaje prazno)."""
    if not isinstance(data, dict):
        return None
    credits = data.get("credits")
    if not isinstance(credits, dict):
        return None
    crew = credits.get("crew")
    if not isinstance(crew, list):
        return None
    for member in crew:
        if isinstance(member, dict) and member.get("job") == "Director":
            name = member.get("name")
            if isinstance(name, str) and name:
                return {"name": name, "id": member.get("id") if isinstance(member.get("id"), int) else None}
    return None


# ----------          ATOM BUILDER: IZDVOJENE FAZE          ----------
# Faze _media_atom-a (kompaktni metapodaci / frontmatter / telo) izdvojene u
# modul-funkcije radi jasnoće i niže složenosti. Ponašanje nepromenjeno.

class TmdbPeopleImportJob(Job):
    id = "tmdb_people_import"
    opis = (
        "Regeneriše atome biblioteke iz baze (media_entry/person/collection); "
        "kad je TMDB ključ podešen, osvežava kredite i preuzima slike glumaca."
    )
    raspored = "on-demand (run-once/start) + best-effort pri boot-u ćelije"

    # ----------          run(ctx)          ----------

    def run(self, ctx: JobContext) -> dict:
        atoms = self._regenerate_atoms(ctx)
        # Catch-up: `_regenerate_atoms` bez media_ids obrađuje samo prvih
        # ATOM_BATCH_DEFAULT naslova, pa `filmium_media_people` (koju čita
        # film-stranica) ostaje prazna za većinu filmova iako `cast_names`
        # postoji. Dopuni linkove za SVE naslove sa cast_names bez linkova —
        # lokalno (bez TMDB); posle prvog prolaza nema nedostajućih pa je
        # praktično besplatno.
        backfilled = self._backfill_missing_media_people(ctx)
        ready = _tmdb_ready()
        people_fetched = 0
        if ready:
            people_fetched = self._fetch_tmdb_people(ctx)
        else:
            ctx.progress(
                atoms, atoms,
                "TMDB ključ nije podešen — preskačem preuzimanje kredita/slika; atomi iz baze",
            )
        return {
            "atoms": atoms,
            "backfilled": backfilled,
            "people_fetched": people_fetched,
            "tmdb": ready,
        }

    def _media_ids_missing_people(self) -> list[int]:
        """Naslovi koji IMAJU `cast_names`, a NEMAJU nijedan `filmium_media_people`."""
        try:
            with _catalog_connection() as con:
                self._ensure_people_tables(con)
                rows = con.execute(
                    "SELECT id FROM filmium_media_items "
                    "WHERE cast_names IS NOT NULL AND TRIM(cast_names) NOT IN ('', '[]') "
                    "AND id NOT IN (SELECT DISTINCT media_id FROM filmium_media_people) "
                    "ORDER BY id"
                ).fetchall()
            return [int(r["id"]) for r in rows]
        except Exception:  # noqa: BLE001 — best-effort
            return []

    def _backfill_missing_media_people(self, ctx: JobContext) -> int:
        """Izgradi `filmium_media_people` za SVE naslove sa cast_names bez linkova.

        Koristi kanonski `_regenerate_atoms` (u komadima), koji iz `cast_names`/
        `director` UPSERT-uje `filmium_people`/`filmium_media_people`. Vraća broj
        obrađenih naslova. Idempotentno; sledeći put nema nedostajućih → 0.
        """
        ids = self._media_ids_missing_people()
        if not ids:
            return 0
        ctx.progress(0, len(ids), f"dopuna glumaca za {len(ids)} naslova (bez linkova)…")
        chunk = 100
        for start in range(0, len(ids), chunk):
            if ctx.should_stop():
                break
            self._regenerate_atoms(ctx, media_ids=ids[start:start + chunk])
            ctx.progress(min(start + chunk, len(ids)), len(ids), "dopuna glumaca…")
        return len(ids)

    # ----------          DB šema (idempotentno, nikad ne briše)          ----------

    @staticmethod
    def _ensure_people_tables(con) -> None:
        """Kreira `filmium_people`/`filmium_media_people` ako ne postoje.
        Idempotentno (`CREATE TABLE IF NOT EXISTS`) — NIKAD ne briše postojeće
        redove (za razliku od jednokratnog migracionog skripta); ovaj posao je
        inkrementalan i mora bezbedno da radi nad već popunjenim tabelama."""
        con.executescript(
            """
            CREATE TABLE IF NOT EXISTS filmium_people(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                slug TEXT UNIQUE NOT NULL,
                tmdb_person_id INTEGER,
                folder_path TEXT,
                image_path TEXT,
                created_at TEXT,
                updated_at TEXT
            );
            CREATE TABLE IF NOT EXISTS filmium_media_people(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                media_id INTEGER NOT NULL,
                person_id INTEGER NOT NULL,
                role TEXT NOT NULL,
                character TEXT,
                sort_order INTEGER,
                UNIQUE(media_id, person_id, role)
            );
            """
        )
        # SR: nove kolone (obogaćivanje + cast_entity) — idempotentno, da posao
        #     radi i nad starim DB-om bez njih. / EN: extra columns, idempotent.
        _cols = {r[1] for r in con.execute("PRAGMA table_info(filmium_people)")}
        for _c, _t in (
            ("bio", "TEXT"), ("birthday", "TEXT"), ("deathday", "TEXT"),
            ("place_of_birth", "TEXT"), ("known_for", "TEXT"),
            ("is_director", "INTEGER DEFAULT 0"), ("filmography_json", "TEXT"),
            ("gallery_count", "INTEGER DEFAULT 0"), ("enriched_at", "TEXT"),
            ("professions", "TEXT"), ("imdb_id", "TEXT"), ("native_name", "TEXT"),
        ):
            if _c not in _cols:
                con.execute(f"ALTER TABLE filmium_people ADD COLUMN {_c} {_t}")

    @staticmethod
    def _upsert_person(
        con,
        name: str,
        slug: str,
        *,
        tmdb_person_id: int | None = None,
        folder_path: str | None = None,
        image_path: str | None = None,
    ) -> int:
        """UPSERT u `filmium_people` po `slug` (jedinstven). `COALESCE` čuva
        postojeće ne-prazne vrednosti kad novi poziv nema tu informaciju (npr.
        `_regenerate_atoms`, koji nema `tmdb_person_id`, ne sme da obriše onaj
        koji je `_fetch_tmdb_people` ranije upisao). Vraća `id` reda."""
        now = _now_iso()
        con.execute(
            """
            INSERT INTO filmium_people(name, slug, tmdb_person_id, folder_path, image_path, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(slug) DO UPDATE SET
                name = excluded.name,
                tmdb_person_id = COALESCE(excluded.tmdb_person_id, filmium_people.tmdb_person_id),
                folder_path = COALESCE(excluded.folder_path, filmium_people.folder_path),
                image_path = COALESCE(excluded.image_path, filmium_people.image_path),
                updated_at = excluded.updated_at
            """,
            (name, slug, tmdb_person_id, folder_path, image_path, now, now),
        )
        row = con.execute("SELECT id FROM filmium_people WHERE slug = ?", (slug,)).fetchone()
        return row["id"]

    @staticmethod
    def _upsert_media_person(
        con,
        media_id: int,
        person_id: int,
        role: str,
        *,
        character: str | None = None,
        sort_order: int | None = None,
    ) -> None:
        """UPSERT u `filmium_media_people` po (media_id, person_id, role).
        `COALESCE` čuva `character`/`sort_order` već upisan iz bogatijeg
        TMDB-fetch prolaza ako ovaj poziv (npr. `_regenerate_atoms`, bez
        `character`) nema tu informaciju."""
        con.execute(
            """
            INSERT INTO filmium_media_people(media_id, person_id, role, character, sort_order)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(media_id, person_id, role) DO UPDATE SET
                character = COALESCE(excluded.character, filmium_media_people.character),
                sort_order = COALESCE(excluded.sort_order, filmium_media_people.sort_order)
            """,
            (media_id, person_id, role, character, sort_order),
        )

    # ----------          korak 1: atomi iz baze (radi BEZ ključa)          ----------

    def _regenerate_atoms(self, ctx: JobContext, media_ids: list[int] | None = None) -> int:
        """Piše media_entry/collection atome iz `filmium_media_items` u
        `.ai/atomi/filmium/{filmovi,serije,kolekcije}`, i person atome u
        `Actors/<fs_name>/<slug>.md` (VIŠE NE u `.ai/atomi/filmium/osobe/` —
        taj folder se više ne pravi). Uz to UPSERT-uje `filmium_people`/
        `filmium_media_people` iz podataka koji već postoje u bazi
        (`cast_names`/`director`) — radi BEZ TMDB ključa.

        Bez `media_ids`: uzima do `ATOM_BATCH_DEFAULT` stavki sa popunjenim
        `cast_names` (najniži `id` prvo — jeftin, deterministički batch).
        Sa `media_ids`: samo te stavke (koristi ga `_fetch_tmdb_people` posle
        osvežavanja kredita, kao i spoljni pozivalac koji cilja konkretan
        naslov). Vraća broj NAPISANIH atom fajlova (media + person + collection)."""

        atoms_root = core_paths.root / ".ai" / "atomi" / "filmium"

        try:
            with _catalog_connection() as con:
                self._ensure_people_tables(con)

                if media_ids:
                    placeholders = ",".join("?" for _ in media_ids)
                    rows = con.execute(
                        f"SELECT * FROM filmium_media_items WHERE id IN ({placeholders})",
                        tuple(media_ids),
                    ).fetchall()
                else:
                    rows = con.execute(
                        "SELECT * FROM filmium_media_items "
                        "WHERE cast_names IS NOT NULL AND cast_names != '' "
                        "ORDER BY id LIMIT ?",
                        (ATOM_BATCH_DEFAULT,),
                    ).fetchall()

                items = [dict(r) for r in rows]

                people: dict[str, dict] = {}   # slug -> {name, reditelj:set, glumac:set, links:[(media_id,role,order)]}
                collections: dict[str, dict] = {}  # slug -> {name, films:set}
                out: dict[tuple[str, str], str] = {}  # (sub, slug) -> sadrzaj (media/collection)

                def reg_person(name: str | None, film_slug: str, role: str, media_id: int, order: int) -> str | None:
                    if not name:
                        return None
                    slug = slugify(name)
                    entry = people.setdefault(
                        slug, {"name": name, "reditelj": set(), "glumac": set(), "links": []}
                    )
                    entry[role].add(film_slug)
                    entry["links"].append((media_id, role, order))
                    return slug

                for m in items:
                    if ctx.should_stop():
                        break
                    try:
                        self._link_people_and_collections(m, reg_person, collections)
                        sub, mslug, content = _AF.build_media_atom(con, m)
                    except Exception as error:  # noqa: BLE001 — jedna stavka ne sme da obori posao
                        ctx.progress(len(out), len(items), f"preskačem '{m.get('title', '?')}': {error}")
                        continue
                    out[(sub, mslug)] = content

                # TMDB franšize -> zaseban region „franshize" (odvojeno od ličnih kolekcija)
                for cslug, coll in collections.items():
                    out[("franshize", cslug)] = _AF.build_franchise_atom(cslug, coll)
                # Lične kolekcije (filmium_collections) -> region „kolekcije"
                for cslug, content in _AF.build_personal_collection_atoms(con).items():
                    out[("kolekcije", cslug)] = content
                # Problem-detalj atomi (region „problemi")
                for pslug, pcontent in _AF.problem_atoms().items():
                    out[("problemi", pslug)] = pcontent

                written = 0
                for (sub, slug), content in out.items():
                    error = _write_atom_or_error(atoms_root, sub, slug, content)
                    if error:
                        ctx.progress(written, len(out), error)
                    else:
                        written += 1

                for pslug, person in people.items():
                    if ctx.should_stop():
                        break
                    error = self._write_person_or_error(con, pslug, person)
                    if error:
                        ctx.progress(
                            written, len(out) + len(people), error,
                        )
                    else:
                        written += 1

                ctx.progress(
                    written, written,
                    f"regenerisano {written} atoma iz baze ({len(items)} stavki, {len(people)} osoba)",
                )
                return written
        except Exception as error:  # noqa: BLE001 — regeneracija je best-effort
            ctx.progress(0, None, f"regeneracija atoma nije uspela: {error}")
            return 0

    def _write_person_or_error(self, con, pslug: str, person: dict) -> str | None:
        """Upisi jednu osobu; greska -> poruka (jedna osoba ne rusi posao)."""

        try:
            self._write_person(con, pslug, person)
            return None
        except Exception as error:  # noqa: BLE001 — jedna osoba ne sme da obori posao
            return f"ne mogu da upišem osobu '{person['name']}': {error}"

    def _write_person(self, con, pslug: str, person: dict) -> None:
        """Piše JEDAN person atom u `Actors/<fs_name>/<slug>.md` (slika se NE
        preuzima ovde — samo referencira ako već postoji, npr. iz migracije
        ili ranijeg `_fetch_tmdb_people`) + UPSERT `filmium_people`/
        `filmium_media_people` za sve filmove/serije gde se osoba pojavljuje."""
        name = person["name"]
        fs = fs_name(name)
        folder = _ACTORS_ROOT / fs
        folder.mkdir(parents=True, exist_ok=True)

        image_file = folder / f"{fs}.jpg"
        image_rel = _rel_to_mount(image_file) if image_file.is_file() else None

        # SR: bogat cast_entity atom — povuci obogaćeni red (bio/datumi/…) ako
        #     postoji; profesije se izvlače iz opisa. Isti builder kao standalone
        #     skripta build_cast_atoms.py (jedan izvor istine).
        # EN: rich cast_entity atom — pull the enriched row if present; professions
        #     come from the description. Same builder as build_cast_atoms.py.
        prow = con.execute("SELECT * FROM filmium_people WHERE slug=?", (pslug,)).fetchone()
        prow = dict(prow) if prow else {}
        pbio = prow.get("bio")
        is_dir = bool(person["reditelj"]) or bool(prow.get("is_director"))
        professions = extract_professions(
            pbio, is_actor=bool(person["glumac"]) or not is_dir, is_director=is_dir
        )
        try:
            filmography = json.loads(prow.get("filmography_json") or "[]")
        except Exception:  # noqa: BLE001
            filmography = []
        directed = sorted(person["reditelj"])
        acted = sorted(person["glumac"])
        content = build_cast_entity_atom(
            slug=pslug, name=name, bio=pbio,
            birthday=prow.get("birthday"), deathday=prow.get("deathday"),
            place_of_birth=prow.get("place_of_birth"), known_for=prow.get("known_for"),
            tmdb_id=prow.get("tmdb_person_id"), imdb_id=prow.get("imdb_id"),
            native_name=prow.get("native_name"), professions=professions,
            is_director=is_dir, image_rel=image_rel or prow.get("image_path"),
            gallery_count=prow.get("gallery_count") or 0,
            directed_slugs=directed, acted_slugs=acted,
            filmography=filmography, lib_film_count=len(set(directed) | set(acted)),
        )
        _AF.write_atom(folder / f"{pslug}.md", content)

        person_id = self._upsert_person(
            con, name, pslug,
            folder_path=_rel_to_mount(folder),
            image_path=image_rel,
        )
        try:
            con.execute(
                "UPDATE filmium_people SET professions=? WHERE id=?",
                (json.dumps(professions, ensure_ascii=False), person_id),
            )
        except Exception:  # noqa: BLE001, S110
            pass
        seen: set[tuple[int, str]] = set()
        for media_id, role, order in person["links"]:
            key = (media_id, role)
            if key in seen:
                continue
            seen.add(key)
            self._upsert_media_person(con, media_id, person_id, role, sort_order=order)

    def _link_people_and_collections(self, m: dict, reg_person, collections: dict) -> None:
        """Populiši person/kolekcija veze (reg_person + collections) za jedan naslov;
        SADRŽAJ atoma pravi atom_factory. Zadržava import person atoma/relacija."""
        title = m["title"]
        year = m.get("release_year") or ""
        mslug = slugify(f"{title} {year}" if year else title)
        director = (m.get("director") or "").strip()
        cast = _jarr(m.get("cast_names"))[:CAST_CAP]
        if director:
            reg_person(director, mslug, "reditelj", m["id"], -1)
        for i, c in enumerate(cast):
            reg_person(c, mslug, "glumac", m["id"], i)
        coll = (m.get("collection") or "").strip()
        if coll:
            cslug = slugify(coll)
            collections.setdefault(cslug, {"name": coll, "films": set()})["films"].add(mslug)

    def _media_atom(self, con, m: dict, reg_person, collections: dict) -> tuple[str, str, str]:
        is_series = m.get("media_type") == "series"
        title = m["title"]
        year = m.get("release_year") or ""
        mslug = slugify(f"{title} {year}" if year else title)

        director = (m.get("director") or "").strip()
        cast = _jarr(m.get("cast_names"))[:CAST_CAP]
        kws = list(dict.fromkeys(_jarr(m.get("keywords"))))[:12]
        coll = (m.get("collection") or "").strip()

        meta = _atom_compact_meta(con, m, is_series=is_series, title=title,
                                  cast=cast)

        dslug = reg_person(director, mslug, "reditelj", m["id"], -1) if director else None
        cslugs = [reg_person(c, mslug, "glumac", m["id"], i) for i, c in enumerate(cast)]

        if coll:
            cslug = slugify(coll)
            collections.setdefault(cslug, {"name": coll, "films": set()})["films"].add(mslug)

        fm = _atom_frontmatter(m, mslug=mslug, title=title, year=year,
                               is_series=is_series, meta=meta)
        body = _atom_body(con, m, fm, is_series=is_series, meta=meta,
                          dslug=dslug, cslugs=cslugs, coll=coll, kws=kws)

        sub = "serije" if is_series else "filmovi"
        return sub, mslug, "\n".join(body) + "\n"

    def _person_atom(self, pslug: str, person: dict, image_rel: str | None) -> str:
        fm = [
            f"id: {pslug}", f"title: {person['name']}", "type: person", "domain: filmium",
            "status: verified", "source: tmdb", "tags: [osoba, tmdb]",
        ]
        if image_rel:
            fm.append(f"image_local: {image_rel}")

        roles = []
        if person["reditelj"]:
            roles.append("reditelj")
        if person["glumac"]:
            roles.append("glumac")
        slika_napomena = "" if image_rel else " (slika: TODO, treba TMDB ključ)"

        body = [
            "---", "\n".join(fm), "---", "",
            "## 🎯 KONTEKST",
            f"{person['name']} — {', '.join(roles)} u FILMIUM biblioteci.{slika_napomena}",
            "", "## 🔀 VEZE",
        ]
        if person["reditelj"]:
            body.append("- Režirao: " + ", ".join(f"[[{f}]]" for f in sorted(person["reditelj"])))
        if person["glumac"]:
            body.append("- Glumio u: " + ", ".join(f"[[{f}]]" for f in sorted(person["glumac"])))
        return "\n".join(body) + "\n"

    def _collection_atom(self, cslug: str, coll: dict) -> str:
        fm = (
            f"id: {cslug}\ntitle: {coll['name']}\ntype: collection\ndomain: filmium\n"
            "status: verified\nsource: tmdb\ntags: [kolekcija, tmdb]"
        )
        body = [
            "---", fm, "---", "",
            "## 🎯 KONTEKST", f"Kolekcija „{coll['name']}“ iz FILMIUM biblioteke.", "",
            "## 🔀 VEZE",
            "- Filmovi: " + ", ".join(f"[[{f}]]" for f in sorted(coll["films"])),
        ]
        return "\n".join(body) + "\n"

    def _personal_collection_atoms(self, con) -> dict:
        """Atomi LIČNIH kolekcija (filmium_collections) sa [[linkovima]] ka film/serija
        atomima — samoisceljujuće pri svakom pokretanju posla."""
        out: dict = {}
        try:
            cols = con.execute(
                "SELECT id, name, description FROM filmium_collections ORDER BY id"
            ).fetchall()
        except Exception:  # noqa: BLE001 — tabela možda ne postoji
            return out
        for row in cols:
            cid, name = row["id"], row["name"]
            desc = (row["description"] or "").strip()
            rows = con.execute(
                "SELECT m.title, m.release_year, m.media_type "
                "FROM filmium_collection_items ci "
                "JOIN filmium_media_items m ON m.id = ci.media_id "
                "WHERE ci.collection_id = ? "
                "ORDER BY m.media_type, m.release_year, m.title",
                (cid,),
            ).fetchall()
            films = [(r["title"], r["release_year"]) for r in rows if r["media_type"] != "series"]
            series = [(r["title"], r["release_year"]) for r in rows if r["media_type"] == "series"]
            slug = slugify(name)
            L = [
                "---", f"id: {slug}", "type: collection", "domain: filmium",
                f'title: "{name}"', f'kolekcija: "{name}"',
                (f'opis: "{desc}"' if desc else 'opis: ""'),
                f"broj_stavki: {len(rows)}", f"filmova: {len(films)}", f"serija: {len(series)}",
                "tags: [kolekcija, filmium, licna-kolekcija]", "---", "",
                "## 🎯 KONTEKST",
                (f"Lična kolekcija **{name}** — {len(rows)} naslova "
                f"({len(films)} filmova, {len(series)} serija)."),
            ]
            if desc:
                L.append(f"> {desc}")
            L.append("")
            if films:
                L.append(f"## 🎬 FILMOVI ({len(films)})")
                for tt, yy in films:
                    L.append(f"- [[{slugify(f'{tt} {yy}')}]] — {tt} ({yy or '?'})")
                L.append("")
            if series:
                L.append(f"## 📺 SERIJE ({len(series)})")
                for tt, yy in series:
                    L.append(f"- [[{slugify(f'{tt} {yy}')}]] — {tt} ({yy or '?'})")
                L.append("")
            out[slug] = "\n".join(L).rstrip() + "\n"
        return out

    # ----------          korak 2: TMDB kredit/slike (SAMO sa stvarnim ključem)          ----------

    def _fetch_tmdb_people(self, ctx: JobContext) -> int:
        """Osvežava `cast_names`/`director` u bazi i preuzima slike glumaca/
        reditelja (top `CAST_CAP` po naslovu) u `Actors/<fs_name>/<fs_name>.jpg`
        (VIŠE NE `data/filmium/people/<slug>.jpg`). Uz to obogaćuje
        `filmium_people`/`filmium_media_people` sa `character` (iz
        `credits.cast`) i `tmdb_person_id` (iz `credits.cast`/`credits.crew`
        `id`-ja — ovaj posao ga, za razliku od jednokratne migracije, IMA
        direktno iz TMDB odgovora).

        Inkrementalno na DVA nivoa:
          - PO OSOBI: slika se ne preuzima ponovo ako fajl već postoji u
            `Actors/<fs_name>/<fs_name>.jpg`.
          - PO STAVCI: kredit-poziv (`.../credits`) se ne ponavlja za stavku
            koja je već jednom USPEŠNO konsultovana (marker fajl — i dalje u
            `data/filmium/people/.fetched/<media_id>.done`; taj folder je
            NAMERNO ostao gde je bio, to je samo interni marker ove ćelije,
            ne deo Actors/ obrasca, pa ne mora da se seli). NAMERNO nije
            "svi top-CAST_CAP glumci imaju sliku" — neki glumci (češće kod
            starijih/manjih naslova) nikad nemaju `profile_path` na TMDB-u,
            pa bi ta provera zauvek iznova gađala isti mali skup stavki i
            nikad ne bi stigla do ostatka biblioteke. Marker se piše SAMO
            posle uspešnog odgovora (mrežna greška -> nema markera -> sledeći
            pokret probni ponovo, ispravno).
        Best-effort: greška na jednoj stavci/slici ne ruši posao; mrežni
        pozivi su već tolerantni na svom nivou (`tmdb_client._request`/
        `download_image` vraćaju `None` umesto izuzetka)."""

        if not _tmdb_ready():
            ctx.progress(0, 0, "TMDB ključ nije podešen — preskačem preuzimanje/slike; atomi iz baze")
            return 0

        fetch_state_dir = filmium_paths.root / "people" / ".fetched"
        try:
            fetch_state_dir.mkdir(parents=True, exist_ok=True)
            _ACTORS_ROOT.mkdir(parents=True, exist_ok=True)
        except OSError as error:
            ctx.progress(0, None, f"ne mogu da napravim {fetch_state_dir} / {_ACTORS_ROOT}: {error}")
            return 0

        fetched_images = 0
        attempted = 0

        try:
            with _catalog_connection() as con:
                self._ensure_people_tables(con)
                rows = con.execute(
                    "SELECT id, title, media_type, tmdb_id, cast_names "
                    "FROM filmium_media_items WHERE tmdb_id IS NOT NULL "
                    "ORDER BY id LIMIT ?",
                    (TMDB_SCAN_LIMIT,),
                ).fetchall()

                for row in rows:
                    if ctx.should_stop() or attempted >= TMDB_FETCH_LIMIT:
                        break

                    item = dict(row)
                    marker_path = fetch_state_dir / f"{item['id']}.done"
                    if marker_path.is_file():
                        continue  # već konsultovano — inkrementalno preskačemo

                    attempted += 1
                    try:
                        fetched_images = self._process_person_item(
                            con, item, marker_path, ctx, fetched_images
                        )
                    except Exception as error:  # noqa: BLE001 — jedna stavka ne sme da obori posao
                        ctx.progress(fetched_images, None, f"preskačem '{item.get('title', '?')}': {error}")
                        continue
        except Exception as error:  # noqa: BLE001 — cela faza je best-effort
            ctx.progress(fetched_images, None, f"preuzimanje TMDB kredita/slika nije uspelo: {error}")
            return fetched_images

        ctx.progress(
            fetched_images, fetched_images,
            f"gotovo: {fetched_images} novih slika ({attempted} stavki obrađeno)",
        )
        return fetched_images


    def _process_person_item(self, con, item, marker_path, ctx,
                             fetched_before: int) -> int:
        """Obradi jednu stavku: TMDB krediti -> UPDATE baze + poveži
        reditelja/glumce (slike). Vraća novi ukupan broj slika."""

        fetched_images = fetched_before
        kind = "tv" if item.get("media_type") == "series" else "movie"
        data = tmdb._request(
            f"{kind}/{item['tmdb_id']}",
            {"append_to_response": "credits"},
            language="en-US",
        )
        if not data:
            return fetched_before

        try:
            marker_path.write_text("", encoding="utf-8")
        except OSError:
            pass

        all_cast_names = tmdb._parse_cast(data)
        director = tmdb._parse_director(data)

        sets: list[str] = []
        params: list[object] = []
        if all_cast_names:
            sets.append("cast_names = ?")
            params.append(json.dumps(list(all_cast_names), ensure_ascii=False))
        if director:
            sets.append("director = ?")
            params.append(director)
        if sets:
            sets.append("updated_at = CURRENT_TIMESTAMP")
            params.append(item["id"])
            con.execute(
                f"UPDATE filmium_media_items SET {', '.join(sets)} WHERE id = ?",
                params,
            )

        if director:
            info = _credits_director(data)
            director_tmdb_id = (
                info.get("id") if info and info.get("name") == director else None
            )
            try:
                fetched_images += self._fetch_and_link_person(
                    con, director, "reditelj", item["id"], -1,
                    tmdb_person_id=director_tmdb_id,
                    profile_path=None,
                )
            except Exception:  # noqa: BLE001, S110
                pass

        cast_entries = _credits_cast(data, CAST_CAP)
        for order, person in enumerate(cast_entries):
            fetched_images += self._link_cast_member(con, person, item["id"], order)

        ctx.progress(
            fetched_images, None,
            f"TMDB: '{item['title']}' obrađen ({len(cast_entries)} glumaca)",
        )
        return fetched_images

    def _link_cast_member(self, con, person: dict, item_id: int, order: int) -> int:
        """Poveži jednog glumca (slika); jedan glumac ne sme da obori stavku."""

        try:
            return self._fetch_and_link_person(
                con, person["name"], "glumac", item_id, order,
                tmdb_person_id=person.get("id"),
                profile_path=person.get("profile_path"),
                character=person.get("character"),
            )
        except Exception:  # noqa: BLE001 — jedan glumac ne sme da obori stavku
            return 0

    def _fetch_and_link_person(
        self,
        con,
        name: str,
        role: str,
        media_id: int,
        order: int,
        *,
        tmdb_person_id: int | None,
        profile_path: str | None,
        character: str | None = None,
    ) -> int:
        """Preuzima sliku (SAMO ako još ne postoji) u
        `Actors/<fs_name>/<fs_name>.jpg` i UPSERT-uje `filmium_people`/
        `filmium_media_people` za JEDNU osobu (glumac ili reditelj). Vraća
        `1` ako je slika NOVO preuzeta (za brojač `fetched_images`), inače
        `0` — DB upsert se dešava u oba slučaja."""
        slug = slugify(name)
        fs = fs_name(name)
        folder = _ACTORS_ROOT / fs
        folder.mkdir(parents=True, exist_ok=True)

        image_file = folder / f"{fs}.jpg"
        downloaded = 0
        if not image_file.is_file():
            url = tmdb._image_url(profile_path, "w185")
            content = tmdb.download_image(url) if url else None
            if content:
                try:
                    image_file.write_bytes(content)
                    downloaded = 1
                except OSError:
                    pass

        image_rel = _rel_to_mount(image_file) if image_file.is_file() else None
        person_id = self._upsert_person(
            con, name, slug,
            tmdb_person_id=tmdb_person_id,
            folder_path=_rel_to_mount(folder),
            image_path=image_rel,
        )
        self._upsert_media_person(con, media_id, person_id, role, character=character, sort_order=order)
        return downloaded
