---
id: filmium-05a0f339-2026-08-08-filmium-kategorije-i-migracija-biblioteke-md
type: plan
domain: filmium
namespace: global
visibility: global
tier: domain
title: FILMIUM kategorije + migracija biblioteke — Implementation Plan
summary: '> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development
  (recommended) or superpowers:executing-plans to implement this plan t'
keywords:
- filmium
- kategorije
- migracija
- biblioteke
- implementation
- docs
- superpowers
- plans
tags:
- superpowers
- plans
source_path: docs/superpowers/plans/2026-08-08-filmium-kategorije-i-migracija-biblioteke.md
---

# FILMIUM kategorije + migracija biblioteke — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Preurediti FILMIUM oko kategorija Strano/Domaće/Animirano (sidebar + FILM/SERIJE toggle), i uskladiti disk, bazu i tok uvoza sa strukturom `F:\Strano\{Filmovi,Serije}`, `F:\Domace\{Filmovi,Serije}`, `F:\Animirano\{Filmovi,Serije}`.

**Architecture:** Kategorija = postojeće polje `content_category` (regular→Strano, domestic→Domaće, animated→Animirano). Migracija ide fazno: disk (same-drive rename) → baza (prefiks putanja) → kod uvoza (nove ciljne putanje) → GUI (filter po kategoriji + tip toggle). Svaka destruktivna skripta ima dry-run kao default i rollback.

**Tech Stack:** Python 3.13 + pytest (`.venv/Scripts/python.exe -m pytest`), React + TS + Vitest (`npx vitest run` u `apps/gui`), SQLite.

## Global Constraints

- Kod/identifikatori: engleski. Komentari/docstring/UI stringovi: srpski. (CLAUDE.md)
- Zaglavlja sekcija: Python `# ========== SEKCIJA ==========`, React `{/* ========== SEKCIJA ========== */}`.
- Projekat NIJE git repo → nema `git commit`. Umesto commit-a, checkpoint = pokreni relevantni test set i potvrdi PASS.
- Ciljna struktura (odluka A2): `Strano`/`Domace` sa prefiksom; `Animirano` ostaje srpski. Regular grana se KOLAPSIRA na `Strano\{Filmovi,Serije}` (bez žanrovskog `Crtani`/`Crtane serije` pod-splita; animirano ide isključivo pod `Animirano` preko content_mode).
- Destruktivne skripte: `--dry-run` je default; `--apply` samo eksplicitno. Backup baze pre svake DB izmene: `data/database/core.db.bak-<timestamp>`.
- Test-runner na pravoj bazi/disku se NE pokreće u testovima — testovi rade nad `tmp_path`.

---

## Faza 1 — Migracija na disku

### Task 1: Skripta za premeštanje foldera biblioteke

**Files:**
- Create: `scripts/migrate_library_layout.py`
- Test: `tests/test_migrate_library_layout.py`

**Interfaces:**
- Produces:
  - `build_move_plan(root: Path) -> list[tuple[Path, Path]]` — vraća listu `(izvor, odredište)` rename operacija za dati koren (npr. `F:\`).
  - `apply_move_plan(plan: list[tuple[Path, Path]]) -> list[tuple[Path, Path]]` — izvršava rename-ove; vraća listu urađenih (za rollback). Preskače ako odredište postoji (diže `FileExistsError`).
  - `build_rollback(done: list[tuple[Path, Path]]) -> list[tuple[Path, Path]]` — inverzni parovi, obrnut redosled.
  - CLI: `python scripts/migrate_library_layout.py <root> [--apply]` (bez `--apply` = dry-run ispis plana).

- [ ] **Step 1: Napiši failing test za plan pomeranja**

```python
# tests/test_migrate_library_layout.py
from pathlib import Path

from scripts.migrate_library_layout import build_move_plan


def _make_layout(root: Path) -> None:
    (root / "Filmovi" / "Neki Film (2020)").mkdir(parents=True)
    (root / "Serije" / "Filmske serije" / "Neka Serija").mkdir(parents=True)
    (root / "Domaci" / "Filmovi" / "Domaci Film").mkdir(parents=True)
    (root / "Animirano" / "Serije" / "Neki Anime").mkdir(parents=True)


def test_build_move_plan_maps_all_categories(tmp_path: Path) -> None:
    _make_layout(tmp_path)

    plan = build_move_plan(tmp_path)
    pairs = {(src.name, dst.relative_to(tmp_path).as_posix()) for src, dst in plan}

    # Strani filmovi: ceo folder Filmovi ide pod Strano.
    assert (tmp_path / "Filmovi", tmp_path / "Strano" / "Filmovi") in plan
    # Strane serije: Filmske serije postaje Strano/Serije.
    assert (
        tmp_path / "Serije" / "Filmske serije",
        tmp_path / "Strano" / "Serije",
    ) in plan
    # Domaci -> Domace (ceo folder).
    assert (tmp_path / "Domaci", tmp_path / "Domace") in plan
    # Animirano se NE pomera.
    assert all("Animirano" not in src.parts for src, _ in plan)
```

- [ ] **Step 2: Pokreni test — mora da padne**

Run: `.venv/Scripts/python.exe -m pytest tests/test_migrate_library_layout.py -v`
Expected: FAIL (`ModuleNotFoundError: scripts.migrate_library_layout`).

- [ ] **Step 3: Implementiraj skriptu**

```python
# scripts/migrate_library_layout.py
"""Migracija strukture FILMIUM biblioteke na Strano/Domace/Animirano.

Same-drive rename (instant, reverzibilno). Dry-run je podrazumevan; premeštanje
tek uz --apply. Animirano se NE dira.
"""

from __future__ import annotations

import sys
from pathlib import Path


# ========== PLAN ==========

def build_move_plan(root: Path) -> list[tuple[Path, Path]]:
    """Parovi (izvor, odredište) za dati koren biblioteke."""

    root = Path(root)
    plan: list[tuple[Path, Path]] = []

    filmovi = root / "Filmovi"
    if filmovi.is_dir():
        plan.append((filmovi, root / "Strano" / "Filmovi"))

    filmske = root / "Serije" / "Filmske serije"
    if filmske.is_dir():
        plan.append((filmske, root / "Strano" / "Serije"))

    domaci = root / "Domaci"
    if domaci.is_dir():
        plan.append((domaci, root / "Domace"))

    return plan


def apply_move_plan(
    plan: list[tuple[Path, Path]],
) -> list[tuple[Path, Path]]:
    """Izvršava rename-ove; vraća urađene parove. Ne prepisuje postojeće."""

    done: list[tuple[Path, Path]] = []
    for source, destination in plan:
        if destination.exists():
            raise FileExistsError(
                f"Odredište već postoji, prekid: {destination}"
            )
        destination.parent.mkdir(parents=True, exist_ok=True)
        source.rename(destination)
        done.append((source, destination))
    return done


def build_rollback(
    done: list[tuple[Path, Path]],
) -> list[tuple[Path, Path]]:
    """Inverzni parovi u obrnutom redosledu (za vraćanje)."""

    return [(destination, source) for source, destination in reversed(done)]


# ========== CLI ==========

def _main(argv: list[str]) -> int:
    if not argv:
        print("Upotreba: migrate_library_layout.py <root> [--apply]")
        return 2

    root = Path(argv[0])
    apply = "--apply" in argv[1:]
    plan = build_move_plan(root)

    if not plan:
        print("Nema šta da se premesti (nema Filmovi/Serije/Domaci).")
        return 0

    print("PLAN premeštanja:")
    for source, destination in plan:
        print(f"  {source}  ->  {destination}")

    if not apply:
        print("\nDRY-RUN (bez izmena). Dodaj --apply za izvršenje.")
        return 0

    done = apply_move_plan(plan)
    print(f"\nURAĐENO: {len(done)} premeštanja.")
    print("ROLLBACK (ako zatreba):")
    for source, destination in build_rollback(done):
        print(f"  {source}  ->  {destination}")
    return 0


if __name__ == "__main__":
    raise SystemExit(_main(sys.argv[1:]))
```

- [ ] **Step 4: Pokreni test — mora da prođe**

Run: `.venv/Scripts/python.exe -m pytest tests/test_migrate_library_layout.py -v`
Expected: PASS.

- [ ] **Step 5: Dodaj test za apply + rollback (round-trip)**

```python
from scripts.migrate_library_layout import (
    apply_move_plan,
    build_move_plan,
    build_rollback,
)


def test_apply_then_rollback_restores_layout(tmp_path: Path) -> None:
    _make_layout(tmp_path)
    before = sorted(p.relative_to(tmp_path).as_posix() for p in tmp_path.rglob("*"))

    done = apply_move_plan(build_move_plan(tmp_path))
    assert (tmp_path / "Strano" / "Filmovi" / "Neki Film (2020)").is_dir()
    assert (tmp_path / "Strano" / "Serije" / "Neka Serija").is_dir()
    assert (tmp_path / "Domace" / "Filmovi" / "Domaci Film").is_dir()
    assert not (tmp_path / "Filmovi").exists()

    apply_move_plan(build_rollback(done))
    after = sorted(p.relative_to(tmp_path).as_posix() for p in tmp_path.rglob("*"))
    # Strano/Domace ostaju kao prazne ljuske posle rollback-a — obriši ih pa uporedi.
    for shell in ("Strano", "Domace"):
        target = tmp_path / shell
        if target.exists():
            for d in sorted(target.rglob("*"), reverse=True):
                d.rmdir()
            target.rmdir()
    after = sorted(p.relative_to(tmp_path).as_posix() for p in tmp_path.rglob("*"))
    assert after == before


def test_apply_refuses_existing_destination(tmp_path: Path) -> None:
    import pytest

    _make_layout(tmp_path)
    (tmp_path / "Strano" / "Filmovi").mkdir(parents=True)
    with pytest.raises(FileExistsError):
        apply_move_plan(build_move_plan(tmp_path))
```

- [ ] **Step 6: Pokreni ceo test fajl — mora PASS**

Run: `.venv/Scripts/python.exe -m pytest tests/test_migrate_library_layout.py -v`
Expected: PASS (3 testa).

- [ ] **Step 7: Checkpoint** — prijavi da je Faza 1 skripta spremna; NE pokrećeš je na `F:\` dok korisnik ne odobri dry-run izlaz.

---

## Faza 2 — Migracija baze

### Task 2: Skripta za prefiks putanja u bazi

**Files:**
- Create: `scripts/migrate_library_db_paths.py`
- Test: `tests/test_migrate_library_db_paths.py`

**Interfaces:**
- Produces:
  - `remap_relative_directory(rel: str) -> str` — preslikava stari relativni prefiks u novi (`Filmovi/…`→`Strano/Filmovi/…`, `Serije/Filmske serije/…`→`Strano/Serije/…`, `Serije/Filmske serije`→`Strano/Serije`, `Filmovi`→`Strano/Filmovi`, `Domaci/…`→`Domace/…`, `Domaci`→`Domace`; `Animirano/…` i već-novi oblici nepromenjeni — idempotentno).
  - `remap_snapshot(path: str) -> str` — isto nad apsolutnim `root_path_snapshot` (segmenti razdvojeni `\` ili `/`).
  - `migrate_database(db_path: Path, apply: bool) -> list[tuple[int, str, str, str, str]]` — vraća listu `(source_id, stari_rel, novi_rel, stari_snap, novi_snap)`; upisuje samo ako `apply=True`.
  - CLI: `python scripts/migrate_library_db_paths.py [db_path] [--apply]` (default db `data/database/core.db`, default dry-run; pravi `.bak-<ts>` pre `--apply`).

- [ ] **Step 1: Napiši failing test za remap (čist string)**

```python
# tests/test_migrate_library_db_paths.py
from scripts.migrate_library_db_paths import (
    remap_relative_directory,
    remap_snapshot,
)


def test_remap_relative_directory_all_prefixes() -> None:
    assert remap_relative_directory("Filmovi/Neki Film") == "Strano/Filmovi/Neki Film"
    assert remap_relative_directory("Serije/Filmske serije/X") == "Strano/Serije/X"
    assert remap_relative_directory("Serije/Filmske serije") == "Strano/Serije"
    assert remap_relative_directory("Domaci/Filmovi/Y") == "Domace/Filmovi/Y"
    assert remap_relative_directory("Domaci") == "Domace"
    # Animirano i već-novi oblik ostaju netaknuti (idempotentno).
    assert remap_relative_directory("Animirano/Serije/Z") == "Animirano/Serije/Z"
    assert remap_relative_directory("Strano/Filmovi/Neki Film") == "Strano/Filmovi/Neki Film"


def test_remap_snapshot_backslash_paths() -> None:
    assert remap_snapshot(r"F:\Serije\Filmske serije") == r"F:\Strano\Serije"
    assert remap_snapshot(r"F:\Domaci") == r"F:\Domace"
    assert remap_snapshot(r"F:\Filmovi") == r"F:\Strano\Filmovi"
    assert remap_snapshot(r"F:\Animirano\Serije") == r"F:\Animirano\Serije"
```

- [ ] **Step 2: Pokreni test — mora da padne**

Run: `.venv/Scripts/python.exe -m pytest tests/test_migrate_library_db_paths.py -v`
Expected: FAIL (import error).

- [ ] **Step 3: Implementiraj remap logiku + migraciju**

```python
# scripts/migrate_library_db_paths.py
"""Migracija putanja u filmium_media_sources na Strano/Domace šemu.

Dry-run podrazumevan; --apply pravi backup baze pa upisuje. Idempotentno.
"""

from __future__ import annotations

import shutil
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

_DEFAULT_DB = Path("data/database/core.db")

# Redosled je bitan: duži/specifičniji prefiks prvi.
_PREFIX_RULES: tuple[tuple[str, str], ...] = (
    ("Serije/Filmske serije", "Strano/Serije"),
    ("Filmovi", "Strano/Filmovi"),
    ("Domaci", "Domace"),
)


def _remap_posix(value: str) -> str:
    """Preslikava POSIX-stil putanju po prefiks-pravilima (idempotentno)."""

    for old, new in _PREFIX_RULES:
        if value == old:
            return new
        if value.startswith(old + "/"):
            return new + value[len(old):]
    return value


def remap_relative_directory(rel: str) -> str:
    return _remap_posix(rel.replace("\\", "/"))


def remap_snapshot(path: str) -> str:
    """Isto nad apsolutnom putanjom (zadržava backslash i drive prefiks)."""

    normalized = path.replace("\\", "/")
    # Odvoji drive (npr. „F:") od ostatka.
    if len(normalized) >= 2 and normalized[1] == ":":
        drive, rest = normalized[:2], normalized[2:].lstrip("/")
    else:
        drive, rest = "", normalized
    remapped = _remap_posix(rest)
    combined = f"{drive}/{remapped}" if drive else remapped
    # Vrati u Windows oblik ako je ulaz imao backslash.
    return combined.replace("/", "\\") if "\\" in path else combined


# ========== MIGRACIJA ==========

def migrate_database(
    db_path: Path,
    apply: bool,
) -> list[tuple[int, str, str, str, str]]:
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    changes: list[tuple[int, str, str, str, str]] = []
    try:
        rows = connection.execute(
            "SELECT id, relative_directory, root_path_snapshot "
            "FROM filmium_media_sources"
        ).fetchall()
        for row in rows:
            old_rel = row["relative_directory"] or ""
            old_snap = row["root_path_snapshot"] or ""
            new_rel = remap_relative_directory(old_rel)
            new_snap = remap_snapshot(old_snap)
            if new_rel == old_rel and new_snap == old_snap:
                continue
            changes.append((row["id"], old_rel, new_rel, old_snap, new_snap))
            if apply:
                connection.execute(
                    "UPDATE filmium_media_sources "
                    "SET relative_directory = ?, root_path_snapshot = ? "
                    "WHERE id = ?",
                    (new_rel, new_snap, row["id"]),
                )
        if apply:
            connection.commit()
    finally:
        connection.close()
    return changes


# ========== CLI ==========

def _main(argv: list[str]) -> int:
    args = [a for a in argv if not a.startswith("--")]
    apply = "--apply" in argv
    db_path = Path(args[0]) if args else _DEFAULT_DB

    if apply:
        backup = db_path.with_name(
            db_path.name + ".bak-" + datetime.now().strftime("%Y%m%d-%H%M%S")
        )
        shutil.copy2(db_path, backup)
        print(f"Backup: {backup}")

    changes = migrate_database(db_path, apply=apply)
    for source_id, old_rel, new_rel, _os, _ns in changes:
        print(f"  #{source_id}: {old_rel!r} -> {new_rel!r}")
    print(f"\n{'UPISANO' if apply else 'DRY-RUN'}: {len(changes)} izvora.")
    if not apply:
        print("Dodaj --apply za izvršenje (pravi backup baze).")
    return 0


if __name__ == "__main__":
    raise SystemExit(_main(sys.argv[1:]))
```

- [ ] **Step 4: Pokreni remap testove — PASS**

Run: `.venv/Scripts/python.exe -m pytest tests/test_migrate_library_db_paths.py -v`
Expected: PASS (2 testa).

- [ ] **Step 5: Dodaj integracioni test migracije nad privremenom bazom**

```python
import sqlite3
from pathlib import Path

from core.database.runtime import initialize_core_database
from scripts.migrate_library_db_paths import migrate_database


def test_migrate_database_updates_and_is_idempotent(tmp_path: Path) -> None:
    db = tmp_path / "core.db"
    initialize_core_database(db)
    conn = sqlite3.connect(db)
    conn.execute(
        "INSERT INTO filmium_media_items (title, media_type, editor_settings) "
        "VALUES ('X', 'series', '{}')"
    )
    media_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    conn.execute(
        "INSERT INTO filmium_media_sources "
        "(media_id, library_root_id, root_path_snapshot, relative_directory, manifest_path) "
        "VALUES (?, NULL, ?, ?, 'filmium_info.json')",
        (media_id, r"F:\Serije\Filmske serije", "Agents"),
    )
    conn.commit()
    conn.close()

    first = migrate_database(db, apply=True)
    assert len(first) == 1

    conn = sqlite3.connect(db)
    row = conn.execute(
        "SELECT relative_directory, root_path_snapshot FROM filmium_media_sources"
    ).fetchone()
    conn.close()
    # relative_directory 'Agents' nema stari prefiks → ostaje; snapshot se remapuje.
    assert row[1] == r"F:\Strano\Serije"

    # Ponovni run ne menja ništa (idempotentno).
    second = migrate_database(db, apply=True)
    assert second == []
```

- [ ] **Step 6: Pokreni ceo fajl — PASS**

Run: `.venv/Scripts/python.exe -m pytest tests/test_migrate_library_db_paths.py -v`
Expected: PASS (3 testa).

- [ ] **Step 7: Checkpoint** — Faza 2 skripta spremna; ne pokreće se na pravoj bazi dok korisnik ne vidi dry-run.

---

## Faza 3 — Tok uvoza (nove ciljne putanje)

### Task 3: Centralizuj rutiranje kategorija na Strano/Domace/Animirano

**Files:**
- Modify: `core/domains/filmium/library_category.py`
- Test: `tests/test_library_category.py` (Create ako ne postoji)

**Interfaces:**
- Produces:
  - `CATEGORY_ROOT: dict[str, str]` = `{"regular": "Strano", "domestic": "Domace", "animated": "Animirano"}`.
  - `movie_base_parts(content_mode: str) -> tuple[str, str]` → `(CATEGORY_ROOT[mode], "Filmovi")`.
  - `series_base_parts(content_mode: str) -> tuple[str, str]` → `(CATEGORY_ROOT[mode], "Serije")`.
  - `infer_content_mode_from_parts(parts: set[str]) -> str` → `animated` ako sadrži `animirano`; `domestic` ako `domace`/`domaci`/`domaći`; inače `regular`.

- [ ] **Step 1: Napiši failing test**

```python
# tests/test_library_category.py
from core.domains.filmium.library_category import (
    infer_content_mode_from_parts,
    movie_base_parts,
    series_base_parts,
)


def test_base_parts_per_mode() -> None:
    assert movie_base_parts("regular") == ("Strano", "Filmovi")
    assert movie_base_parts("domestic") == ("Domace", "Filmovi")
    assert movie_base_parts("animated") == ("Animirano", "Filmovi")
    assert series_base_parts("regular") == ("Strano", "Serije")
    assert series_base_parts("domestic") == ("Domace", "Serije")
    assert series_base_parts("animated") == ("Animirano", "Serije")


def test_infer_content_mode_recognizes_new_and_old() -> None:
    assert infer_content_mode_from_parts({"strano", "filmovi"}) == "regular"
    assert infer_content_mode_from_parts({"domace", "serije"}) == "domestic"
    assert infer_content_mode_from_parts({"domaci"}) == "domestic"  # stari fallback
    assert infer_content_mode_from_parts({"animirano"}) == "animated"
    assert infer_content_mode_from_parts({"filmovi"}) == "regular"
```

- [ ] **Step 2: Pokreni — FAIL**

Run: `.venv/Scripts/python.exe -m pytest tests/test_library_category.py -v`
Expected: FAIL (funkcije ne postoje).

- [ ] **Step 3: Dodaj funkcije u `library_category.py`**

```python
# Dodati ispod postojećih (zadržati stare funkcije radi kompatibilnosti).

# ========== KATEGORIJSKI KORENI ==========

CATEGORY_ROOT: dict[str, str] = {
    "regular": "Strano",
    "domestic": "Domace",
    "animated": "Animirano",
}


def movie_base_parts(content_mode: str) -> tuple[str, str]:
    # Film → <kategorija>/Filmovi (regular=Strano, domestic=Domace, animated=Animirano).
    return (CATEGORY_ROOT.get(content_mode, "Strano"), MOVIES_DIR)


def series_base_parts(content_mode: str) -> tuple[str, str]:
    # Serija → <kategorija>/Serije (bez žanrovskog pod-splita).
    return (CATEGORY_ROOT.get(content_mode, "Strano"), SERIES_DIR)


def infer_content_mode_from_parts(parts: set[str]) -> str:
    # Kategorija iz skupa segmenata putanje (casefold). Novi + stari nazivi.
    if "animirano" in parts:
        return "animated"
    if "domace" in parts or "domaci" in parts or "domaći" in parts:
        return "domestic"
    return "regular"
```

- [ ] **Step 4: Pokreni — PASS**

Run: `.venv/Scripts/python.exe -m pytest tests/test_library_category.py -v`
Expected: PASS.

### Task 4: Preusmeri serije import na nove baze + novo `_infer_content_mode`

**Files:**
- Modify: `core/domains/filmium/series_import_service.py` (target baze na linijama ~504-512; detekcioni kandidati ~619-621, 690-692, 962-966; `_infer_content_mode` ~1268-1290)
- Test: `tests/test_filmium_series_import_service.py`

**Interfaces:**
- Consumes: `series_base_parts`, `movie_base_parts`, `infer_content_mode_from_parts` iz Task 3.

- [ ] **Step 1: Napiši failing test za ciljnu putanju serije**

```python
# u tests/test_filmium_series_import_service.py
def test_regular_series_imports_into_strano(tmp_path: Path) -> None:
    from core.domains.filmium.models import MediaType

    service, media_repo, seasons, episodes = _setup(tmp_path)
    source = _make_series(tmp_path / "source")
    library = tmp_path / "library"
    library.mkdir()

    result = service.import_series(source, library, confirmed=True)

    assert (library / "Strano" / "Serije" / "Fringe" / "Sezona 1" / "E01.mkv").is_file()
    assert not (library / "Serije" / "Filmske serije").exists()
```

- [ ] **Step 2: Pokreni — FAIL** (trenutno ide u `Serije/Filmske serije`)

Run: `.venv/Scripts/python.exe -m pytest tests/test_filmium_series_import_service.py::test_regular_series_imports_into_strano -v`
Expected: FAIL.

- [ ] **Step 3: Zameni target-baze u `series_import_service.py`**

Zameni blok (regular grana koristila `series_category_parts`):

```python
        # Serija ide u <koren>/<kategorija>/Serije (Strano/Domace/Animirano).
        library_base = Path(library_root).joinpath(
            *series_base_parts(content_mode)
        )
```

Dodaj import na vrhu fajla:

```python
from core.domains.filmium.library_category import (
    series_base_parts,
    movie_base_parts,
    infer_content_mode_from_parts,
)
```

Zameni telo `_infer_content_mode` da koristi zajedničku funkciju:

```python
def _infer_content_mode(directory: Path, root_path: Path) -> str:
    """Zaključuje kategoriju iz putanje (Strano/Domace/Animirano + stari nazivi)."""

    try:
        parts = {
            part.casefold()
            for part in directory.resolve(strict=False)
            .relative_to(root_path)
            .parts
        }
    except ValueError:
        parts = {part.casefold() for part in directory.parts}
    return infer_content_mode_from_parts(parts)
```

Ažuriraj detekcione kandidate (skeniranje postojećih kategorija) — svako mesto tipa `root_path / "Serije"`, `root_path / "Domaci" / "Serije"`, `root_path / "Filmovi"`, `root_path / "Domaci" / "Filmovi"` zameni novim putanjama:

```python
                root_path / "Strano" / "Serije",
                root_path / "Animirano" / "Serije",
                root_path / "Domace" / "Serije",
```

```python
                root_path / "Strano" / "Filmovi",
                root_path / "Animirano" / "Filmovi",
                root_path / "Domace" / "Filmovi",
```

- [ ] **Step 4: Pokreni novi test + ceo fajl — PASS**

Run: `.venv/Scripts/python.exe -m pytest tests/test_filmium_series_import_service.py -v`
Expected: PASS (svi, uklj. novi). Ako neki stariji test tvrdi `Serije/Filmske serije`, ažuriraj ga na `Strano/Serije`.

### Task 5: Preusmeri film (kolekcija) import u commit servisu

**Files:**
- Modify: `core/domains/filmium/library_import_commit_service.py:224-227` (i regular grana koja koristi `category_parts`)
- Test: `tests/test_filmium_library_import_commit_service.py`

**Interfaces:**
- Consumes: `movie_base_parts` iz Task 3.

- [ ] **Step 1: Napiši failing test da regular film ide u `Strano/Filmovi`**

```python
# Prati postojeći obrazac u tests/test_filmium_library_import_commit_service.py:
# napravi film u <root>/Strano-neutralnom izvoru, commit sa content_mode='regular',
# pa assert da je fajl završio u <target>/Strano/Filmovi/...
# (Iskoristi postojeće helper-e iz tog test fajla za setup root/preview/commit.)
```

- [ ] **Step 2: Pokreni — FAIL**

Run: `.venv/Scripts/python.exe -m pytest tests/test_filmium_library_import_commit_service.py -v -k regular`
Expected: FAIL (ide u `Filmovi`, ne `Strano/Filmovi`).

- [ ] **Step 3: Zameni grananje kategorije u commit servisu**

```python
            # Ciljni folder po kategoriji (regular=Strano, domestic=Domace,
            # animated=Animirano); film uvek u .../Filmovi.
            category_parts = movie_base_parts(content_mode)
```

Dodaj import:

```python
from core.domains.filmium.library_category import movie_base_parts
```

Ukloni staro `if content_mode == "animated": ("Animirano","Filmovi") elif "domestic": ("Domaci","Filmovi") else movie_category_parts(...)`.

- [ ] **Step 4: Pokreni ceo fajl — PASS**

Run: `.venv/Scripts/python.exe -m pytest tests/test_filmium_library_import_commit_service.py -v`
Expected: PASS.

- [ ] **Step 5: Checkpoint** — pokreni pun Python filmium set.

Run: `.venv/Scripts/python.exe -m pytest tests/ -q -k "filmium or series or source or import or category"`
Expected: PASS.

---

## Faza 4 — GUI

### Task 6: Prošири filter hook kategorijom

**Files:**
- Modify: `apps/gui/src/features/filmium/hooks/useFilmiumFilters.ts`
- Modify: `apps/gui/src/types/filmium.ts` (dodaj tip `CategoryFilter`)
- Test: `apps/gui/src/features/filmium/hooks/useFilmiumFilters.test.ts` (Create)

**Interfaces:**
- Produces: hook vraća i `categoryFilter: CategoryFilter`, `setCategoryFilter`. `filteredItems` dodatno filtrira po `content_category` (mapa: `strano→regular`, `domace→domestic`, `animirano→animated`, `all→bez filtera`).
- `CategoryFilter = "all" | "strano" | "domace" | "animirano"`.

- [ ] **Step 1: Dodaj tip u `types/filmium.ts`**

```typescript
export type CategoryFilter = "all" | "strano" | "domace" | "animirano";
```

- [ ] **Step 2: Napiši failing test hooka**

```typescript
// useFilmiumFilters.test.ts
import { act, renderHook } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { useFilmiumFilters } from "./useFilmiumFilters";
import type { MediaItem } from "../../../types/filmium";

function item(over: Partial<MediaItem>): MediaItem {
  return {
    id: 1, title: "X", original_title: null, media_type: "movie",
    release_year: 2020, watch_status: "planned", rating: null, notes: null,
    genres: [], is_favorite: false, poster_path: null, backdrop_path: null,
    created_at: "", updated_at: "", runtime_minutes: null,
    content_category: "regular", cast_names: [], english_title: null,
    ...over,
  } as MediaItem;
}

describe("useFilmiumFilters categoryFilter", () => {
  it("filtrira po content_category", () => {
    const items = [
      item({ id: 1, content_category: "regular" }),
      item({ id: 2, content_category: "animated" }),
      item({ id: 3, content_category: "domestic" }),
    ];
    const { result } = renderHook(() => useFilmiumFilters(items));
    act(() => result.current.setCategoryFilter("strano"));
    expect(result.current.filteredItems.map((x) => x.id)).toEqual([1]);
    act(() => result.current.setCategoryFilter("animirano"));
    expect(result.current.filteredItems.map((x) => x.id)).toEqual([2]);
  });
});
```

- [ ] **Step 3: Pokreni — FAIL**

Run (u `apps/gui`): `npx vitest run src/features/filmium/hooks/useFilmiumFilters.test.ts`
Expected: FAIL (`setCategoryFilter` ne postoji).

- [ ] **Step 4: Implementiraj u `useFilmiumFilters.ts`**

Dodaj state i filter (mapa kategorija → `content_category`), i vrati ih:

```typescript
  const [categoryFilter, setCategoryFilter] =
    useState<CategoryFilter>("all");

  const _categoryToContent: Record<
    Exclude<CategoryFilter, "all">,
    string
  > = { strano: "regular", domace: "domestic", animirano: "animated" };
```

U `filteredItems` filteru dodaj:

```typescript
      const matchesCategory =
        categoryFilter === "all" ||
        item.content_category === _categoryToContent[categoryFilter];
```

Uključi `matchesCategory` u `return (... && matchesCategory)`, dodaj `categoryFilter` u `useMemo` zavisnosti i u `clearFilters` (`setCategoryFilter("all")`), i u vraćeni objekat (`categoryFilter`, `setCategoryFilter`).

- [ ] **Step 5: Pokreni — PASS**

Run: `npx vitest run src/features/filmium/hooks/useFilmiumFilters.test.ts`
Expected: PASS.

### Task 7: Sidebar — Strano/Domaće/Animirano + rute

**Files:**
- Modify: `apps/gui/src/components/layout/Sidebar.tsx:53-70`
- Modify: `apps/gui/src/App.tsx` (rute)
- Modify: `apps/gui/src/pages/FilmiumLibraryPage.tsx` (`FilmiumLibraryView` + mapiranje na kategoriju)
- Test: `apps/gui/src/components/layout/Sidebar.test.tsx`

**Interfaces:**
- Rute: `/filmium/strano`, `/filmium/domace`, `/filmium/animirano` → `<FilmiumLibraryPage view="strano|domace|animirano" />`.
- `FilmiumLibraryPage` prima nove `view` vrednosti; postavlja `categoryFilter` preko `useEffect` (analogno postojećem `lockedMediaType`).

- [ ] **Step 1: Zameni sidebar stavke (Filmovi/Serije/Animirano → Strano/Domaće/Animirano)**

```typescript
  {
    id: "filmium-strano",
    label: "Strano",
    icon: Clapperboard,
    path: "/filmium/strano",
  },
  {
    id: "filmium-domace",
    label: "Domaće",
    icon: Tv,
    path: "/filmium/domace",
  },
  {
    id: "filmium-animated",
    label: "Animirano",
    icon: Sparkles,
    path: "/filmium/animirano",
  },
```

- [ ] **Step 2: Dodaj rute u `App.tsx`** (zameni postojeće movies/series/animated rute)

```tsx
<Route path="strano" element={<FilmiumLibraryPage view="strano" />} />
<Route path="domace" element={<FilmiumLibraryPage view="domace" />} />
<Route path="animirano" element={<FilmiumLibraryPage view="animirano" />} />
```

- [ ] **Step 3: U `FilmiumLibraryPage.tsx` proširi `FilmiumLibraryView` i mapiranje**

```typescript
export type FilmiumLibraryView =
  | "strano" | "domace" | "animirano"
  | "favorites" | "top-rated" | "upcoming" | "all";
```

Dodaj mapiranje view→categoryFilter i postavi ga u `useEffect`:

```typescript
  const lockedCategory =
    view === "strano" ? "strano"
      : view === "domace" ? "domace"
        : view === "animirano" ? "animirano"
          : "all";

  useEffect(() => {
    setCategoryFilter(lockedCategory);
  }, [lockedCategory, setCategoryFilter]);
```

Naslovi: dodaj `strano: "Strano"`, `domace: "Domaće"`, `animirano: "Animirano"` u `viewTitles`. `shouldUsePosterGrid` uključi i nove kategorije (sve koriste poster grid).

- [ ] **Step 4: Ažuriraj Sidebar test** da očekuje nove labele (`Strano`, `Domaće`), pokreni GUI testove za sidebar i library.

Run: `npx vitest run src/components/layout/Sidebar.test.tsx src/pages/FilmiumLibraryPage.test.tsx`
Expected: PASS (ažuriraj asertacije labela/ruta gde su padale).

### Task 8: Top bar — FILM/SERIJE toggle dugmad

**Files:**
- Modify: `apps/gui/src/features/filmium/components/layout/FilmiumTopBar.tsx`
- Modify: `apps/gui/src/features/filmium/context/FilmiumWorkspace.tsx` (prosledi `mediaTypeFilter`/`setMediaTypeFilter` u TopBar)
- Test: `apps/gui/src/features/filmium/components/layout/FilmiumTopBar.test.tsx` (Create ili proširi)

**Interfaces:**
- TopBar dobija props: `mediaTypeFilter: MediaTypeFilter`, `onToggleMovie: () => void`, `onToggleSeries: () => void`.
- Ponašanje: dugme `FILM` aktivno kad `mediaTypeFilter === "movie"`; `SERIJE` aktivno kad `=== "series"`. Klik na aktivno → `all` (isključi). Klik na neaktivno → postavi taj tip. Oba nikad istovremeno „on" (isključiva; ekvivalent „sve" je kad je `all`).

- [ ] **Step 1: Dodaj toggle handlere u Workspace**

```typescript
  function handleToggleMovie(): void {
    filters.setMediaTypeFilter(
      filters.mediaTypeFilter === "movie" ? "all" : "movie",
    );
  }
  function handleToggleSeries(): void {
    filters.setMediaTypeFilter(
      filters.mediaTypeFilter === "series" ? "all" : "series",
    );
  }
```

Prosledi u `<FilmiumTopBar ... mediaTypeFilter={filters.mediaTypeFilter} onToggleMovie={handleToggleMovie} onToggleSeries={handleToggleSeries} />`.

- [ ] **Step 2: Napiši failing test TopBar-a**

```typescript
// FilmiumTopBar.test.tsx
import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import FilmiumTopBar from "./FilmiumTopBar";

const base = {
  searchQuery: "", onHomeClick: vi.fn(), onSearchChange: vi.fn(),
  onFilterClick: vi.fn(), onUploadClick: vi.fn(), onSettingsClick: vi.fn(),
};

describe("FilmiumTopBar toggles", () => {
  it("FILM dugme aktivno kad je mediaTypeFilter=movie", () => {
    render(<FilmiumTopBar {...base} mediaTypeFilter="movie"
      onToggleMovie={vi.fn()} onToggleSeries={vi.fn()} />);
    expect(screen.getByRole("button", { name: /FILM/i })).toHaveClass("active");
  });
  it("klik na SERIJE zove onToggleSeries", () => {
    const onToggleSeries = vi.fn();
    render(<FilmiumTopBar {...base} mediaTypeFilter="all"
      onToggleMovie={vi.fn()} onToggleSeries={onToggleSeries} />);
    fireEvent.click(screen.getByRole("button", { name: /SERIJE/i }));
    expect(onToggleSeries).toHaveBeenCalledOnce();
  });
});
```

- [ ] **Step 3: Pokreni — FAIL**

Run: `npx vitest run src/features/filmium/components/layout/FilmiumTopBar.test.tsx`
Expected: FAIL (props/dugmad ne postoje).

- [ ] **Step 4: Dodaj dugmad u `FilmiumTopBar.tsx`** (levo, odmah posle Home dugmeta, pre search labele)

```tsx
      <div className="filmium-type-toggles">
        <button
          className={`filmium-type-toggle ${
            mediaTypeFilter === "movie" ? "active" : ""
          }`}
          onClick={onToggleMovie}
          type="button"
        >
          FILM
        </button>
        <button
          className={`filmium-type-toggle ${
            mediaTypeFilter === "series" ? "active" : ""
          }`}
          onClick={onToggleSeries}
          type="button"
        >
          SERIJE
        </button>
      </div>
```

Dodaj u props tip: `mediaTypeFilter: MediaTypeFilter; onToggleMovie: () => void; onToggleSeries: () => void;` i import `MediaTypeFilter` iz `../../../types/filmium`.

- [ ] **Step 5: Pokreni — PASS**

Run: `npx vitest run src/features/filmium/components/layout/FilmiumTopBar.test.tsx`
Expected: PASS.

### Task 9: Ukloni stari `FilmiumCatalog` prikaz svuda

**Files:**
- Modify: `apps/gui/src/pages/FilmiumLibraryPage.tsx` (grana `!shouldUsePosterGrid`)
- Delete: `apps/gui/src/components/filmium/FilmiumCatalog.tsx` i `FilmiumCatalog.test.tsx`
- Modify: `apps/gui/src/pages/FilmiumLibraryPage.test.tsx` (ukloni FilmiumCatalog mock)

**Interfaces:**
- `top-rated`/`upcoming` renderuju `FilmiumMediaPosterGrid` (kao ostale kategorije).

- [ ] **Step 1: `shouldUsePosterGrid` = true za sve preostale view-ove** (ukloni `FilmiumCatalog` granu; sve ide u `FilmiumMediaPosterGrid`).

```typescript
  const shouldUsePosterGrid = true;
```

Ukloni `!shouldUsePosterGrid` blok i import `FilmiumCatalog`.

- [ ] **Step 2: Obriši `FilmiumCatalog.tsx` i njegov test.** Ukloni njegov `vi.mock` iz `FilmiumLibraryPage.test.tsx`; prilagodi/ukloni test „otvara edit režim" (edit više nije inline nigde — zameni proverom da poster kartica poziva `onOpenDetails`).

- [ ] **Step 3: Pokreni ceo GUI set — PASS**

Run (u `apps/gui`): `npx vitest run`
Expected: PASS (svih fajlova; ažuriraj asertacije koje su zavisile od starog catalog-a).

- [ ] **Step 4: TypeScript provera**

Run (u `apps/gui`): `npx tsc --noEmit`
Expected: bez grešaka.

- [ ] **Step 5: Checkpoint** — Faza 4 gotova; ceo GUI set + tsc čisti.

---

## Redosled izvršenja na produkciji (posle merge-a koda)

Ovo NIJE deo automatskih testova — radi se ručno uz potvrdu, redom:

1. `python scripts/migrate_library_layout.py "F:\"` (dry-run) → korisnik pregleda plan.
2. `python scripts/migrate_library_layout.py "F:\" --apply` → premeštanje (sačuvaj ispisani rollback).
3. `python scripts/migrate_library_db_paths.py` (dry-run) → pregled.
4. `python scripts/migrate_library_db_paths.py --apply` → backup + upis.
5. Verifikacija: reprodukcija filma i serije iz svake kategorije; sličice se učitavaju.

## Napomene / otvoreno

- Kolaps regular grane (nema `Crtani`/`Crtane serije`) je posledica 6-folder cilja; ako korisnik želi da zadrži žanrovski pod-split unutar `Strano`, Task 3-5 se koriguju (ali cilj-struktura bi tada imala više od 6 foldera).
- `origin_scope` (sve „unknown") se ne koristi u ovom radu.
- Ako se pojavi `F:\Domaci\Serije` pre migracije, `Domaci`→`Domace` rename je pokriva automatski (ceo folder).
