# Ćelija FILMIUM — temelj (plan implementacije)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Napraviti temelj ćelijskog sistema i sklopiti FILMIUM ćeliju koja se diže na sopstvenom disku, sa sopstvenom bazom i sopstvenim API-jem, bez ijednog uvoza ka drugom domenu.

**Architecture:** Nov paket `core/cell/` u CORE repou nosi kontrakt ćelije (manifest, putanje, baza, AI sloj, status). Skripte u `scripts/cell/` izvlače FILMIUM podatke iz deljene `core.db` i sklapaju folder ćelije kopiranjem kernela, domena i API sloja. CORE nastavlja da radi nepromenjeno — dok ćelija ne proradi, ništa se iz CORE-a ne briše.

**Tech Stack:** Python 3.14, FastAPI, SQLite (`sqlite3` iz standardne biblioteke), pytest. Bez novih spoljnih zavisnosti.

**Spec:** `docs/superpowers/specs/2026-09-12-celijski-sistem-filmium-design.md`

## Global Constraints

- Pytest se pokreće isključivo kroz projektni venv: `./.venv/Scripts/python.exe -m pytest`. Sistemski `python` se ne koristi.
- Nijedan fajl se ne briše iz CORE repoa u ovom planu. Ćelija nastaje kopiranjem.
- Ponašanje CORE-a bez `cell.json` mora ostati bit po bit isto. Svaki zadatak koji dira postojeći kod nosi i regresioni test za taj slučaj.
- Bez novih pip zavisnosti.
- Komentari i docstring-ovi se pišu na srpskom, po ugledu na postojeći kod (`core/database/connection.py`, `apps/api/auto_import_runtime.py`).
- Nazivi tabela ostaju nepromenjeni: 25 tabela sa prefiksom `filmium_`.
- Mrežni timeout prema ćeliji je 5 sekundi, svuda.
- Rad ide na grani `feat/celija-filmium`, granatoj od `feat/filmium-torrenti`.

---

### Task 1: Manifest ćelije

**Files:**
- Create: `core/cell/__init__.py`
- Create: `core/cell/manifest.py`
- Test: `tests/test_cell_manifest.py`

**Interfaces:**
- Consumes: ništa.
- Produces:
  - `CELL_MANIFEST_FILENAME: str = "cell.json"`
  - `class CellManifest` (frozen dataclass) sa poljima: `domain_id: str`, `name: str`, `domain_version: str`, `kernel_version: str`, `port: int`, `core_url: str | None`, `created_at: str`, `detached_from: str | None`, `root: Path`, `ai_endpoint: str`, `ai_curator_model: str | None`, `rag_enabled: bool`, `rag_namespace: str`
  - `CellManifest.data_dir -> Path` (svojstvo, `root / "data"`)
  - `CellManifest.database_path -> Path` (svojstvo, `data_dir / f"{domain_id}.db"`)
  - `class CellManifestError(Exception)`
  - `load_cell_manifest(root: Path) -> CellManifest`
  - `find_cell_manifests(directory: Path) -> tuple[Path, ...]` — traži `cell.json` u zadatom folderu i jedan nivo poddirektorijuma

- [ ] **Step 1: Napiši testove koji padaju**

```python
# tests/test_cell_manifest.py
import json
from pathlib import Path

import pytest

from core.cell.manifest import (
    CELL_MANIFEST_FILENAME,
    CellManifest,
    CellManifestError,
    find_cell_manifests,
    load_cell_manifest,
)


def write_manifest(root: Path, **overrides: object) -> Path:
    """Upisuje ispravan cell.json, uz opcione izmene polja."""

    payload: dict[str, object] = {
        "domain_id": "filmium",
        "name": "FILMIUM",
        "domain_version": "0.1.0",
        "kernel_version": "0.1.0",
        "port": 8781,
        "core_url": "http://localhost:8000",
        "created_at": "2026-09-12T10:00:00",
        "detached_from": "f5d9257",
        "ai": {"endpoint": "http://localhost:11434", "curator_model": "llama3"},
        "rag": {"enabled": False, "namespace": "cell:filmium"},
    }
    payload.update(overrides)
    root.mkdir(parents=True, exist_ok=True)
    path = root / CELL_MANIFEST_FILENAME
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_loads_manifest_fields(tmp_path: Path) -> None:
    write_manifest(tmp_path)

    manifest = load_cell_manifest(tmp_path)

    assert manifest.domain_id == "filmium"
    assert manifest.port == 8781
    assert manifest.kernel_version == "0.1.0"
    assert manifest.ai_endpoint == "http://localhost:11434"
    assert manifest.ai_curator_model == "llama3"
    assert manifest.rag_enabled is False
    assert manifest.rag_namespace == "cell:filmium"


def test_derives_data_and_database_paths(tmp_path: Path) -> None:
    write_manifest(tmp_path)

    manifest = load_cell_manifest(tmp_path)

    assert manifest.data_dir == tmp_path / "data"
    assert manifest.database_path == tmp_path / "data" / "filmium.db"


def test_missing_manifest_raises(tmp_path: Path) -> None:
    with pytest.raises(CellManifestError) as error:
        load_cell_manifest(tmp_path)

    assert CELL_MANIFEST_FILENAME in str(error.value)


def test_missing_required_field_raises(tmp_path: Path) -> None:
    write_manifest(tmp_path)
    path = tmp_path / CELL_MANIFEST_FILENAME
    data = json.loads(path.read_text(encoding="utf-8"))
    del data["port"]
    path.write_text(json.dumps(data), encoding="utf-8")

    with pytest.raises(CellManifestError) as error:
        load_cell_manifest(tmp_path)

    assert "port" in str(error.value)


def test_invalid_port_raises(tmp_path: Path) -> None:
    write_manifest(tmp_path, port="osamhiljada")

    with pytest.raises(CellManifestError):
        load_cell_manifest(tmp_path)


def test_broken_json_raises(tmp_path: Path) -> None:
    tmp_path.mkdir(parents=True, exist_ok=True)
    (tmp_path / CELL_MANIFEST_FILENAME).write_text("{ ovo nije json", encoding="utf-8")

    with pytest.raises(CellManifestError):
        load_cell_manifest(tmp_path)


def test_optional_sections_have_defaults(tmp_path: Path) -> None:
    write_manifest(tmp_path)
    path = tmp_path / CELL_MANIFEST_FILENAME
    data = json.loads(path.read_text(encoding="utf-8"))
    del data["ai"]
    del data["rag"]
    data["core_url"] = None
    data["detached_from"] = None
    path.write_text(json.dumps(data), encoding="utf-8")

    manifest = load_cell_manifest(tmp_path)

    assert manifest.ai_endpoint == "http://localhost:11434"
    assert manifest.ai_curator_model is None
    assert manifest.rag_enabled is False
    assert manifest.rag_namespace == "cell:filmium"
    assert manifest.core_url is None


def test_find_manifests_scans_one_level_deep(tmp_path: Path) -> None:
    write_manifest(tmp_path / "FILMIUM")
    write_manifest(tmp_path / "KALIMA")
    (tmp_path / "prazno").mkdir()

    found = find_cell_manifests(tmp_path)

    assert sorted(path.parent.name for path in found) == ["FILMIUM", "KALIMA"]


def test_find_manifests_includes_directory_itself(tmp_path: Path) -> None:
    write_manifest(tmp_path)

    found = find_cell_manifests(tmp_path)

    assert found == (tmp_path / CELL_MANIFEST_FILENAME,)


def test_find_manifests_on_missing_directory_returns_empty(tmp_path: Path) -> None:
    assert find_cell_manifests(tmp_path / "nema-ovoga") == ()
```

- [ ] **Step 2: Pokreni testove i potvrdi da padaju**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_cell_manifest.py -v`
Expected: FAIL sa `ModuleNotFoundError: No module named 'core.cell'`

- [ ] **Step 3: Napiši minimalnu implementaciju**

```python
# core/cell/__init__.py
```

(prazan fajl — paket)

```python
# core/cell/manifest.py
"""Manifest ćelije: čitanje i provera `cell.json`.

Ćelija je odcepljen domen koji živi u sopstvenom direktorijumu. Manifest je
jedini fajl koji CORE mora da razume da bi je pronašao i povezao.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

CELL_MANIFEST_FILENAME = "cell.json"

_REQUIRED_FIELDS = (
    "domain_id",
    "name",
    "domain_version",
    "kernel_version",
    "port",
    "created_at",
)

_DEFAULT_AI_ENDPOINT = "http://localhost:11434"


class CellManifestError(Exception):
    """Manifest ne postoji, nije čitljiv ili mu nedostaje obavezno polje."""


@dataclass(frozen=True)
class CellManifest:
    """Trajni identitet jedne ćelije."""

    domain_id: str
    name: str
    domain_version: str
    kernel_version: str
    port: int
    core_url: str | None
    created_at: str
    detached_from: str | None
    root: Path
    ai_endpoint: str
    ai_curator_model: str | None
    rag_enabled: bool
    rag_namespace: str

    @property
    def data_dir(self) -> Path:
        """Direktorijum sa bazom, artwork-om i logovima ćelije."""

        return self.root / "data"

    @property
    def database_path(self) -> Path:
        """SQLite baza ćelije, imenovana po domenu."""

        return self.data_dir / f"{self.domain_id}.db"


def load_cell_manifest(root: Path) -> CellManifest:
    """
    Učitava i proverava `cell.json` iz zadatog direktorijuma.

    Args:
        root: Koren ćelije (direktorijum u kom stoji `cell.json`).

    Returns:
        Pročitan manifest.

    Raises:
        CellManifestError: Ako fajl ne postoji, nije ispravan JSON ili mu
            nedostaje obavezno polje.
    """
    path = root / CELL_MANIFEST_FILENAME

    if not path.is_file():
        raise CellManifestError(f"Nema {CELL_MANIFEST_FILENAME} u {root}")

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise CellManifestError(f"Nečitljiv {path}: {error}") from error

    if not isinstance(data, dict):
        raise CellManifestError(f"{path} nije JSON objekat")

    missing = [field for field in _REQUIRED_FIELDS if field not in data]
    if missing:
        raise CellManifestError(
            f"{path} nema obavezna polja: {', '.join(missing)}"
        )

    try:
        port = int(data["port"])
    except (TypeError, ValueError) as error:
        raise CellManifestError(f"{path}: port nije broj") from error

    ai = data.get("ai") or {}
    rag = data.get("rag") or {}
    domain_id = str(data["domain_id"])

    return CellManifest(
        domain_id=domain_id,
        name=str(data["name"]),
        domain_version=str(data["domain_version"]),
        kernel_version=str(data["kernel_version"]),
        port=port,
        core_url=data.get("core_url"),
        created_at=str(data["created_at"]),
        detached_from=data.get("detached_from"),
        root=root,
        ai_endpoint=str(ai.get("endpoint") or _DEFAULT_AI_ENDPOINT),
        ai_curator_model=ai.get("curator_model"),
        rag_enabled=bool(rag.get("enabled", False)),
        rag_namespace=str(rag.get("namespace") or f"cell:{domain_id}"),
    )


def find_cell_manifests(directory: Path) -> tuple[Path, ...]:
    """
    Traži manifeste u zadatom direktorijumu i jedan nivo ispod.

    Dublje se namerno ne ide: ćelija je uvek folder sa imenom domena, a dublje
    skeniranje bi po velikim diskovima trajalo neprihvatljivo dugo.

    Args:
        directory: Direktorijum koji korisnik bira u CORE Settings-u.

    Returns:
        Putanje pronađenih `cell.json` fajlova, sortirane.
    """
    if not directory.is_dir():
        return ()

    found: list[Path] = []

    own = directory / CELL_MANIFEST_FILENAME
    if own.is_file():
        found.append(own)

    try:
        children = sorted(directory.iterdir())
    except OSError:
        return tuple(found)

    for child in children:
        if not child.is_dir():
            continue
        candidate = child / CELL_MANIFEST_FILENAME
        if candidate.is_file():
            found.append(candidate)

    return tuple(found)
```

- [ ] **Step 4: Pokreni testove i potvrdi da prolaze**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_cell_manifest.py -v`
Expected: PASS, 10 testova

- [ ] **Step 5: Commit**

```bash
git add core/cell/__init__.py core/cell/manifest.py tests/test_cell_manifest.py
git commit -m "feat(cell): manifest celije (cell.json) sa proverom i pretragom"
```

---

### Task 2: Primena manifesta na CORE putanje

**Files:**
- Create: `core/cell/paths.py`
- Test: `tests/test_cell_paths.py`

**Interfaces:**
- Consumes: `CellManifest` iz Task 1.
- Produces: `apply_cell_paths(manifest: CellManifest, paths: CorePaths | None = None) -> None`

Postojeći `core_database_connection` već bira `core_paths.core_database` kad mu putanja nije prosleđena (`core/database/connection.py:28`), a svi FILMIUM repozitorijumi prosleđuju `self._database_path` koji je podrazumevano `None`. Zato ćeliji nije potrebna nijedna izmena u `connection.py` — dovoljno je da pri podizanju preusmeri `core_paths`.

- [ ] **Step 1: Napiši testove koji padaju**

```python
# tests/test_cell_paths.py
import json
from pathlib import Path

from core.cell.manifest import CELL_MANIFEST_FILENAME, load_cell_manifest
from core.cell.paths import apply_cell_paths
from core.foundation.paths import CorePaths


def make_manifest(root: Path):
    """Pravi minimalan manifest na disku i vraća ga učitanog."""

    root.mkdir(parents=True, exist_ok=True)
    (root / CELL_MANIFEST_FILENAME).write_text(
        json.dumps(
            {
                "domain_id": "filmium",
                "name": "FILMIUM",
                "domain_version": "0.1.0",
                "kernel_version": "0.1.0",
                "port": 8781,
                "created_at": "2026-09-12T10:00:00",
            }
        ),
        encoding="utf-8",
    )
    return load_cell_manifest(root)


def test_redirects_database_and_data_dirs(tmp_path: Path) -> None:
    manifest = make_manifest(tmp_path / "FILMIUM")
    paths = CorePaths(root_path=tmp_path / "nebitno")

    apply_cell_paths(manifest, paths)

    assert paths.core_database == manifest.database_path
    assert paths.database_dir == manifest.data_dir
    assert paths.logs == manifest.data_dir / "logs"


def test_creates_data_directories(tmp_path: Path) -> None:
    manifest = make_manifest(tmp_path / "FILMIUM")
    paths = CorePaths(root_path=tmp_path / "nebitno")

    apply_cell_paths(manifest, paths)

    assert manifest.data_dir.is_dir()
    assert (manifest.data_dir / "logs").is_dir()


def test_does_not_touch_global_paths_when_given_instance(tmp_path: Path) -> None:
    from core.foundation.paths import core_paths

    before = core_paths.core_database
    manifest = make_manifest(tmp_path / "FILMIUM")

    apply_cell_paths(manifest, CorePaths(root_path=tmp_path / "nebitno"))

    assert core_paths.core_database == before
```

- [ ] **Step 2: Pokreni testove i potvrdi da padaju**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_cell_paths.py -v`
Expected: FAIL sa `ModuleNotFoundError: No module named 'core.cell.paths'`

- [ ] **Step 3: Napiši minimalnu implementaciju**

```python
# core/cell/paths.py
"""Preusmeravanje CORE putanja na direktorijum ćelije.

Ćelija koristi isti kernel kao CORE, ali joj baza, logovi i podaci stoje u
sopstvenom folderu. Umesto da svaki repozitorijum dobije novu putanju, ovde se
jednom preusmeri registar putanja koji svi već koriste.
"""

from __future__ import annotations

from core.cell.manifest import CellManifest
from core.foundation.paths import CorePaths, core_paths


def apply_cell_paths(
    manifest: CellManifest,
    paths: CorePaths | None = None,
) -> None:
    """
    Preusmerava putanje na direktorijum ćelije i kreira ih.

    Args:
        manifest: Učitan manifest ćelije.
        paths: Registar putanja koji se menja. Bez njega se menja globalni
            `core_paths`, što se radi samo pri podizanju ćelije.
    """
    target = paths if paths is not None else core_paths

    target.data = manifest.data_dir
    target.database_dir = manifest.data_dir
    target.core_database = manifest.database_path
    target.logs = manifest.data_dir / "logs"
    target.screenshots = manifest.data_dir / "screenshots"
    target.editor_projects = target.screenshots / "projects"

    target.ensure_required_dirs()
```

- [ ] **Step 4: Pokreni testove i potvrdi da prolaze**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_cell_paths.py -v`
Expected: PASS, 3 testa

- [ ] **Step 5: Potvrdi da CORE nije pomeren**

Run: `./.venv/Scripts/python.exe -m pytest tests/ -q`
Expected: PASS — isti broj prolaza kao pre ovog zadatka. `apply_cell_paths` se nigde još ne poziva, pa CORE ponašanje mora biti netaknuto.

- [ ] **Step 6: Commit**

```bash
git add core/cell/paths.py tests/test_cell_paths.py
git commit -m "feat(cell): preusmeravanje CORE putanja na folder celije"
```

---

### Task 3: Inicijalizacija baze ćelije

**Files:**
- Create: `core/cell/database.py`
- Test: `tests/test_cell_database.py`

**Interfaces:**
- Consumes: `CellManifest` (Task 1), `FILMIUM_MIGRATIONS` iz `core/domains/filmium/migrations.py`, `apply_database_migrations` iz `core/database/migrations.py`.
- Produces:
  - `DOMAIN_MIGRATIONS: dict[str, tuple[DatabaseMigration, ...]]` — mapa `domain_id` u migracije
  - `initialize_cell_database(manifest: CellManifest) -> None`

Razlika u odnosu na `initialize_core_database`: ćelija primenjuje **samo** migracije svog domena, nikad `CORE_AI_MIGRATIONS` (tabele `core_connectors`, `core_model_allowlist`, `core_model_visibility` ostaju CORE-ove).

- [ ] **Step 1: Napiši testove koji padaju**

```python
# tests/test_cell_database.py
import json
import sqlite3
from pathlib import Path

import pytest

from core.cell.database import initialize_cell_database
from core.cell.manifest import CELL_MANIFEST_FILENAME, load_cell_manifest


def make_manifest(root: Path, domain_id: str = "filmium"):
    root.mkdir(parents=True, exist_ok=True)
    (root / CELL_MANIFEST_FILENAME).write_text(
        json.dumps(
            {
                "domain_id": domain_id,
                "name": domain_id.upper(),
                "domain_version": "0.1.0",
                "kernel_version": "0.1.0",
                "port": 8781,
                "created_at": "2026-09-12T10:00:00",
            }
        ),
        encoding="utf-8",
    )
    return load_cell_manifest(root)


def table_names(path: Path) -> set[str]:
    connection = sqlite3.connect(path)
    try:
        rows = connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
        ).fetchall()
    finally:
        connection.close()
    return {row[0] for row in rows}


def test_creates_filmium_tables(tmp_path: Path) -> None:
    manifest = make_manifest(tmp_path / "FILMIUM")

    initialize_cell_database(manifest)

    names = table_names(manifest.database_path)
    assert "filmium_media_items" in names
    assert "filmium_torrents" in names


def test_does_not_create_core_ai_tables(tmp_path: Path) -> None:
    manifest = make_manifest(tmp_path / "FILMIUM")

    initialize_cell_database(manifest)

    names = table_names(manifest.database_path)
    assert "core_connectors" not in names
    assert "core_model_allowlist" not in names
    assert "core_model_visibility" not in names


def test_is_idempotent(tmp_path: Path) -> None:
    manifest = make_manifest(tmp_path / "FILMIUM")

    initialize_cell_database(manifest)
    first = table_names(manifest.database_path)
    initialize_cell_database(manifest)
    second = table_names(manifest.database_path)

    assert first == second


def test_unknown_domain_raises(tmp_path: Path) -> None:
    manifest = make_manifest(tmp_path / "NEPOSTOJECI", domain_id="nepostojeci")

    with pytest.raises(KeyError):
        initialize_cell_database(manifest)
```

- [ ] **Step 2: Pokreni testove i potvrdi da padaju**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_cell_database.py -v`
Expected: FAIL sa `ModuleNotFoundError: No module named 'core.cell.database'`

- [ ] **Step 3: Napiši minimalnu implementaciju**

```python
# core/cell/database.py
"""Inicijalizacija baze ćelije.

Ćelija primenjuje samo migracije svog domena. CORE migracije (konektori,
vidljivost modela) ostaju u CORE bazi i nikad ne ulaze u ćeliju.
"""

from __future__ import annotations

from core.cell.manifest import CellManifest
from core.database.connection import core_database_connection
from core.database.migrations import DatabaseMigration, apply_database_migrations
from core.domains.filmium.migrations import FILMIUM_MIGRATIONS

# Registar migracija po domenu. Novi domen dodaje jedan red.
DOMAIN_MIGRATIONS: dict[str, tuple[DatabaseMigration, ...]] = {
    "filmium": FILMIUM_MIGRATIONS,
}


def initialize_cell_database(manifest: CellManifest) -> None:
    """
    Gradi ili dopunjuje bazu ćelije migracijama njenog domena.

    Args:
        manifest: Učitan manifest ćelije.

    Raises:
        KeyError: Ako domen nema registrovane migracije.
    """
    migrations = DOMAIN_MIGRATIONS[manifest.domain_id]

    manifest.data_dir.mkdir(parents=True, exist_ok=True)

    with core_database_connection(manifest.database_path) as connection:
        apply_database_migrations(connection, migrations)
```

- [ ] **Step 4: Pokreni testove i potvrdi da prolaze**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_cell_database.py -v`
Expected: PASS, 4 testa

- [ ] **Step 5: Commit**

```bash
git add core/cell/database.py tests/test_cell_database.py
git commit -m "feat(cell): inicijalizacija baze celije samo migracijama domena"
```

---

### Task 4: Prenos podataka iz `core.db` u bazu ćelije

**Files:**
- Create: `core/cell/extraction.py`
- Create: `scripts/cell/extract_domain_db.py`
- Test: `tests/test_cell_extraction.py`

**Interfaces:**
- Consumes: `initialize_cell_database` (Task 3), `CellManifest` (Task 1).
- Produces:
  - `domain_table_names(connection: sqlite3.Connection, domain_id: str) -> tuple[str, ...]`
  - `extract_domain_data(source_db: Path, manifest: CellManifest) -> dict[str, int]` — vraća broj prenetih redova po tabeli
  - `verify_extraction(source_db: Path, manifest: CellManifest) -> tuple[str, ...]` — vraća imena tabela kod kojih se broj redova razlikuje

- [ ] **Step 1: Napiši testove koji padaju**

```python
# tests/test_cell_extraction.py
import json
import sqlite3
from pathlib import Path

from core.cell.extraction import (
    domain_table_names,
    extract_domain_data,
    verify_extraction,
)
from core.cell.manifest import CELL_MANIFEST_FILENAME, load_cell_manifest
from core.database.runtime import initialize_core_database


def make_manifest(root: Path):
    root.mkdir(parents=True, exist_ok=True)
    (root / CELL_MANIFEST_FILENAME).write_text(
        json.dumps(
            {
                "domain_id": "filmium",
                "name": "FILMIUM",
                "domain_version": "0.1.0",
                "kernel_version": "0.1.0",
                "port": 8781,
                "created_at": "2026-09-12T10:00:00",
            }
        ),
        encoding="utf-8",
    )
    return load_cell_manifest(root)


def seed_source(tmp_path: Path) -> Path:
    """Pravi CORE bazu sa jednim filmom u biblioteci."""

    source = tmp_path / "core.db"
    initialize_core_database(source)

    connection = sqlite3.connect(source)
    try:
        connection.execute(
            "INSERT INTO filmium_media_items (title, media_type) VALUES (?, ?)",
            ("Probni film", "movie"),
        )
        connection.commit()
    finally:
        connection.close()

    return source


def test_lists_only_domain_tables(tmp_path: Path) -> None:
    source = seed_source(tmp_path)

    connection = sqlite3.connect(source)
    try:
        names = domain_table_names(connection, "filmium")
    finally:
        connection.close()

    assert "filmium_media_items" in names
    assert all(name.startswith("filmium_") for name in names)
    assert "core_connectors" not in names


def test_copies_rows(tmp_path: Path) -> None:
    source = seed_source(tmp_path)
    manifest = make_manifest(tmp_path / "FILMIUM")

    counts = extract_domain_data(source, manifest)

    assert counts["filmium_media_items"] == 1

    connection = sqlite3.connect(manifest.database_path)
    try:
        titles = [
            row[0]
            for row in connection.execute("SELECT title FROM filmium_media_items")
        ]
    finally:
        connection.close()

    assert titles == ["Probni film"]


def test_copies_migration_rows_for_scope(tmp_path: Path) -> None:
    source = seed_source(tmp_path)
    manifest = make_manifest(tmp_path / "FILMIUM")

    extract_domain_data(source, manifest)

    connection = sqlite3.connect(manifest.database_path)
    try:
        scopes = {
            row[0]
            for row in connection.execute(
                "SELECT DISTINCT scope FROM core_schema_migrations"
            )
        }
    finally:
        connection.close()

    assert scopes == {"filmium"}


def test_verification_reports_no_mismatch(tmp_path: Path) -> None:
    source = seed_source(tmp_path)
    manifest = make_manifest(tmp_path / "FILMIUM")

    extract_domain_data(source, manifest)

    assert verify_extraction(source, manifest) == ()


def test_verification_reports_mismatch(tmp_path: Path) -> None:
    source = seed_source(tmp_path)
    manifest = make_manifest(tmp_path / "FILMIUM")
    extract_domain_data(source, manifest)

    connection = sqlite3.connect(manifest.database_path)
    try:
        connection.execute("DELETE FROM filmium_media_items")
        connection.commit()
    finally:
        connection.close()

    assert verify_extraction(source, manifest) == ("filmium_media_items",)


def test_rerun_does_not_duplicate_rows(tmp_path: Path) -> None:
    source = seed_source(tmp_path)
    manifest = make_manifest(tmp_path / "FILMIUM")

    extract_domain_data(source, manifest)
    extract_domain_data(source, manifest)

    assert verify_extraction(source, manifest) == ()


def test_source_is_not_modified(tmp_path: Path) -> None:
    source = seed_source(tmp_path)
    manifest = make_manifest(tmp_path / "FILMIUM")
    before = source.read_bytes()

    extract_domain_data(source, manifest)

    assert source.read_bytes() == before
```

- [ ] **Step 2: Pokreni testove i potvrdi da padaju**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_cell_extraction.py -v`
Expected: FAIL sa `ModuleNotFoundError: No module named 'core.cell.extraction'`

- [ ] **Step 3: Napiši minimalnu implementaciju**

```python
# core/cell/extraction.py
"""Prenos podataka domena iz deljene CORE baze u bazu ćelije.

Šema ćelije se ne kopira — nju grade migracije domena. Ovde se prenose samo
redovi, plus zapisi o već primenjenim migracijama, da ćelija ne bi pokušala da
ih ponovi.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from core.cell.database import initialize_cell_database
from core.cell.manifest import CellManifest


def domain_table_names(
    connection: sqlite3.Connection,
    domain_id: str,
) -> tuple[str, ...]:
    """
    Vraća imena tabela koje pripadaju domenu, po prefiksu imena.

    Args:
        connection: Otvorena konekcija ka izvornoj bazi.
        domain_id: Identifikator domena, npr. `filmium`.

    Returns:
        Sortirana imena tabela.
    """
    rows = connection.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' "
        "AND name LIKE ? ORDER BY name",
        (f"{domain_id}_%",),
    ).fetchall()

    return tuple(row[0] for row in rows)


def _row_count(connection: sqlite3.Connection, table: str) -> int:
    return int(connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])


def extract_domain_data(source_db: Path, manifest: CellManifest) -> dict[str, int]:
    """
    Prenosi redove domena iz CORE baze u bazu ćelije.

    Ponovljeno pokretanje daje isti rezultat: ciljne tabele se prvo prazne.
    Izvorna baza se otvara samo za čitanje i ostaje netaknuta.

    Args:
        source_db: Putanja CORE baze.
        manifest: Manifest ćelije.

    Returns:
        Broj prenetih redova po tabeli.
    """
    initialize_cell_database(manifest)

    target = sqlite3.connect(manifest.database_path)
    counts: dict[str, int] = {}

    try:
        target.execute("PRAGMA foreign_keys = OFF")
        target.execute(
            "ATTACH DATABASE ? AS source", (str(source_db),)
        )

        tables = domain_table_names(target, manifest.domain_id)

        for table in tables:
            target.execute(f"DELETE FROM {table}")
            target.execute(f"INSERT INTO {table} SELECT * FROM source.{table}")
            counts[table] = _row_count(target, table)

        target.execute(
            "DELETE FROM core_schema_migrations WHERE scope = ?",
            (manifest.domain_id,),
        )
        target.execute(
            "INSERT INTO core_schema_migrations "
            "SELECT * FROM source.core_schema_migrations WHERE scope = ?",
            (manifest.domain_id,),
        )

        target.commit()
    finally:
        try:
            target.execute("DETACH DATABASE source")
        except sqlite3.Error:
            pass
        target.close()

    return counts


def verify_extraction(source_db: Path, manifest: CellManifest) -> tuple[str, ...]:
    """
    Poredi broj redova po tabeli u izvoru i u ćeliji.

    Args:
        source_db: Putanja CORE baze.
        manifest: Manifest ćelije.

    Returns:
        Imena tabela kod kojih se brojevi razlikuju. Prazna torka znači da je
        prenos ispravan.
    """
    source = sqlite3.connect(source_db)
    target = sqlite3.connect(manifest.database_path)

    mismatched: list[str] = []

    try:
        for table in domain_table_names(source, manifest.domain_id):
            if _row_count(source, table) != _row_count(target, table):
                mismatched.append(table)
    finally:
        source.close()
        target.close()

    return tuple(mismatched)
```

```python
# scripts/cell/extract_domain_db.py
"""Prenosi podatke jednog domena iz CORE baze u bazu ćelije.

Upotreba:
    ./.venv/Scripts/python.exe scripts/cell/extract_domain_db.py F:\\FILMIUM
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from core.cell.extraction import extract_domain_data, verify_extraction  # noqa: E402
from core.cell.manifest import load_cell_manifest  # noqa: E402
from core.foundation.paths import core_paths  # noqa: E402


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("Upotreba: extract_domain_db.py <koren-celije>")
        return 2

    manifest = load_cell_manifest(Path(argv[1]))
    counts = extract_domain_data(core_paths.core_database, manifest)

    for table, count in sorted(counts.items()):
        print(f"  {table}: {count}")

    mismatched = verify_extraction(core_paths.core_database, manifest)
    if mismatched:
        print("NESLAGANJE u tabelama: " + ", ".join(mismatched))
        return 1

    print(f"Preneto {sum(counts.values())} redova u {manifest.database_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
```

- [ ] **Step 4: Pokreni testove i potvrdi da prolaze**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_cell_extraction.py -v`
Expected: PASS, 7 testova

- [ ] **Step 5: Commit**

```bash
git add core/cell/extraction.py scripts/cell/extract_domain_db.py tests/test_cell_extraction.py
git commit -m "feat(cell): prenos podataka domena iz core.db u bazu celije"
```

---

### Task 5: `import_guard` — skener uvoza bez KALIMA-e

**Files:**
- Create: `core/domains/filmium/import_guard/__init__.py`
- Create: `core/domains/filmium/import_guard/models.py`
- Create: `core/domains/filmium/import_guard/hash_checker.py`
- Create: `core/domains/filmium/import_guard/scanner.py`
- Test: `tests/test_filmium_import_guard.py`

**Interfaces:**
- Consumes: ništa van standardne biblioteke.
- Produces:
  - `class GuardStatus(str, Enum)` sa vrednostima `CLEAN`, `SUSPICIOUS`, `MALWARE`, `UNKNOWN` — iste vrednosti kao `core/domains/filmium/auto_import/auto_import_models.py:18`
  - `class ImportGuard` sa `scan(file_path: str) -> GuardReport` i `status_for(file_path: str) -> GuardStatus`
  - `class GuardReport` (frozen dataclass): `status: GuardStatus`, `threats: tuple[str, ...]`, `digest: str`

Kopija `core/domains/kalima/security/` (221 linija), bez karantina — ćelija samo odbija fajl, ne premešta ga. Karantin ostaje KALIMA funkcija.

- [ ] **Step 1: Napiši testove koji padaju**

```python
# tests/test_filmium_import_guard.py
import hashlib
from pathlib import Path

from core.domains.filmium.auto_import.auto_import_models import SecurityStatus
from core.domains.filmium.import_guard import GuardStatus, ImportGuard


def write_file(path: Path, content: bytes = b"sadrzaj") -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return str(path)


def test_clean_video_passes(tmp_path: Path) -> None:
    target = write_file(tmp_path / "film.mkv")

    assert ImportGuard().status_for(target) is GuardStatus.CLEAN


def test_executable_extension_is_suspicious(tmp_path: Path) -> None:
    target = write_file(tmp_path / "film.exe")

    report = ImportGuard().scan(target)

    assert report.status is GuardStatus.SUSPICIOUS
    assert any("exe" in threat for threat in report.threats)


def test_double_extension_is_suspicious(tmp_path: Path) -> None:
    target = write_file(tmp_path / "film.mp4.exe")

    assert ImportGuard().status_for(target) is GuardStatus.SUSPICIOUS


def test_known_malware_hash_is_malware(tmp_path: Path) -> None:
    content = b"zlonamerni sadrzaj"
    target = write_file(tmp_path / "film.mkv", content)
    digest = hashlib.sha256(content).hexdigest()

    guard = ImportGuard(known_hashes={digest})

    assert guard.status_for(target) is GuardStatus.MALWARE


def test_missing_file_is_suspicious(tmp_path: Path) -> None:
    assert ImportGuard().status_for(str(tmp_path / "nema.mkv")) is GuardStatus.SUSPICIOUS


def test_status_values_match_filmium_enum() -> None:
    assert {status.value for status in GuardStatus} >= {
        status.value for status in SecurityStatus
    }


def test_status_is_directly_usable_as_filmium_status(tmp_path: Path) -> None:
    target = write_file(tmp_path / "film.mkv")

    status = SecurityStatus(ImportGuard().status_for(target).value)

    assert status is SecurityStatus.CLEAN
```

- [ ] **Step 2: Pokreni testove i potvrdi da padaju**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_filmium_import_guard.py -v`
Expected: FAIL sa `ModuleNotFoundError: No module named 'core.domains.filmium.import_guard'`

- [ ] **Step 3: Napiši minimalnu implementaciju**

```python
# core/domains/filmium/import_guard/models.py
"""Model nalaza pri proveri fajla koji ulazi u biblioteku."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class GuardStatus(str, Enum):
    """Ishod provere. Vrednosti su iste kao FILMIUM `SecurityStatus`."""

    UNKNOWN = "unknown"
    CLEAN = "clean"
    SUSPICIOUS = "suspicious"
    MALWARE = "malware"


@dataclass(frozen=True)
class GuardReport:
    """Nalaz jedne provere."""

    status: GuardStatus
    threats: tuple[str, ...]
    digest: str
```

```python
# core/domains/filmium/import_guard/hash_checker.py
"""Računanje SHA-256 sažetka fajla, u blokovima."""

from __future__ import annotations

import hashlib

_BLOCK_SIZE = 1024 * 1024


def sha256_file(file_path: str) -> str:
    """
    Računa SHA-256 sažetak fajla.

    Args:
        file_path: Putanja fajla.

    Returns:
        Heksadecimalni sažetak.

    Raises:
        OSError: Ako se fajl ne može pročitati.
    """
    digest = hashlib.sha256()

    with open(file_path, "rb") as handle:
        while True:
            block = handle.read(_BLOCK_SIZE)
            if not block:
                break
            digest.update(block)

    return digest.hexdigest()
```

```python
# core/domains/filmium/import_guard/scanner.py
"""Provera fajla pre uvoza u biblioteku.

Kopija KALIMA skenera, bez mreže i bez karantina: ćelija fajl samo označi, ne
premešta ga. Postoji zato što torrenti i nadzirani folderi umeju da donesu
izvršni fajl pod imenom filma.
"""

from __future__ import annotations

import os
from collections.abc import Iterable

from core.domains.filmium.import_guard.hash_checker import sha256_file
from core.domains.filmium.import_guard.models import GuardReport, GuardStatus

# Ekstenzije koje su izvršne ili rizične u kontekstu preuzetog „videa".
DANGEROUS_EXT = frozenset({
    "exe", "scr", "bat", "cmd", "com", "js", "vbs", "jar", "msi", "ps1", "sh", "apk",
})

# Ekstenzije koje se legitimno pojavljuju kao prvi deo dvostruke ekstenzije.
_MEDIA_EXT = frozenset({
    "mp4", "mkv", "avi", "mov", "wmv", "srt", "sub", "ass", "vtt",
})


class ImportGuard:
    """Skenira fajl i vraća nalaz."""

    def __init__(self, known_hashes: Iterable[str] | None = None) -> None:
        """
        Args:
            known_hashes: Sažeci poznatog malware-a. Prazno po podrazumevanom.
        """
        self._known = frozenset(known_hashes or ())

    def scan(self, file_path: str) -> GuardReport:
        """
        Proverava fajl i vraća nalaz.

        Args:
            file_path: Putanja fajla.

        Returns:
            Nalaz sa statusom, spiskom pretnji i sažetkom.
        """
        extension = os.path.splitext(file_path)[1].lstrip(".").lower()
        threats: list[str] = []
        status = GuardStatus.CLEAN
        digest = ""

        try:
            digest = sha256_file(file_path)
            if digest in self._known:
                threats.append("poznat malware hash")
                status = GuardStatus.MALWARE
        except OSError:
            threats.append("nemoguće pročitati fajl")
            status = GuardStatus.SUSPICIOUS

        if status is not GuardStatus.MALWARE:
            if self._has_double_extension(file_path):
                threats.append("dvostruka ekstenzija (maskiranje)")
                status = GuardStatus.SUSPICIOUS
            if extension in DANGEROUS_EXT:
                threats.append(f"izvršna ekstenzija .{extension}")
                status = GuardStatus.SUSPICIOUS

        return GuardReport(status=status, threats=tuple(threats), digest=digest)

    def status_for(self, file_path: str) -> GuardStatus:
        """Vraća samo status, za ubrizgavanje u `AutoImportService`."""

        return self.scan(file_path).status

    @staticmethod
    def _has_double_extension(file_path: str) -> bool:
        """Tačno: `film.mp4.exe`. Netačno: `film.2024.mkv`."""

        name = os.path.basename(file_path).lower()
        parts = name.split(".")

        if len(parts) < 3:
            return False

        return parts[-2] in _MEDIA_EXT and parts[-1] in DANGEROUS_EXT
```

```python
# core/domains/filmium/import_guard/__init__.py
"""Provera fajlova pre uvoza, bez zavisnosti od drugih domena."""

from core.domains.filmium.import_guard.models import GuardReport, GuardStatus
from core.domains.filmium.import_guard.scanner import DANGEROUS_EXT, ImportGuard

__all__ = [
    "DANGEROUS_EXT",
    "GuardReport",
    "GuardStatus",
    "ImportGuard",
]
```

- [ ] **Step 4: Pokreni testove i potvrdi da prolaze**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_filmium_import_guard.py -v`
Expected: PASS, 7 testova

- [ ] **Step 5: Potvrdi da CORE auto-uvoz nije diran**

Run: `./.venv/Scripts/python.exe -m pytest tests/ -q -k "auto_import or security"`
Expected: PASS. `apps/api/auto_import_runtime.py` i dalje koristi KALIMA skener; `import_guard` se u CORE-u ne poziva.

- [ ] **Step 6: Commit**

```bash
git add core/domains/filmium/import_guard tests/test_filmium_import_guard.py
git commit -m "feat(filmium): import_guard, skener uvoza bez zavisnosti od KALIMA-e"
```

---

### Task 6: AI sloj ćelije (Ollama i persone)

**Files:**
- Create: `core/cell/ai.py`
- Test: `tests/test_cell_ai.py`

**Interfaces:**
- Consumes: `CellManifest` (Task 1), `OllamaClient` iz `core/ai/ollama_client.py`, `CuratorService` iz `core/domains/filmium/curator`.
- Produces:
  - `class CellModelBinding` (frozen dataclass): `model: str`, `endpoint: str`
  - `class CellModelRegistry` sa metodom `binding(domain: str, role: str) -> CellModelBinding`
  - `build_cell_curator(manifest: CellManifest, retriever: MediaRetriever) -> CuratorService`

`CuratorService` u CORE-u dobija pun `ModelRegistry`; u ćeliji dobija ovaj tanak registar sa jednim vezivanjem, pročitanim iz `cell.json`. Domenski kod se ne menja.

- [ ] **Step 1: Napiši testove koji padaju**

```python
# tests/test_cell_ai.py
import json
from pathlib import Path

import pytest

from core.cell.ai import CellModelBinding, CellModelRegistry, build_cell_curator
from core.cell.manifest import CELL_MANIFEST_FILENAME, load_cell_manifest


def make_manifest(root: Path, curator_model: str | None = "llama3"):
    root.mkdir(parents=True, exist_ok=True)
    (root / CELL_MANIFEST_FILENAME).write_text(
        json.dumps(
            {
                "domain_id": "filmium",
                "name": "FILMIUM",
                "domain_version": "0.1.0",
                "kernel_version": "0.1.0",
                "port": 8781,
                "created_at": "2026-09-12T10:00:00",
                "ai": {
                    "endpoint": "http://localhost:11434",
                    "curator_model": curator_model,
                },
            }
        ),
        encoding="utf-8",
    )
    return load_cell_manifest(root)


def test_registry_returns_binding_from_manifest(tmp_path: Path) -> None:
    manifest = make_manifest(tmp_path / "FILMIUM")

    binding = CellModelRegistry(manifest).binding("Filmium", "curator_model")

    assert binding == CellModelBinding(
        model="llama3", endpoint="http://localhost:11434"
    )


def test_registry_without_model_raises(tmp_path: Path) -> None:
    manifest = make_manifest(tmp_path / "FILMIUM", curator_model=None)

    with pytest.raises(LookupError):
        CellModelRegistry(manifest).binding("Filmium", "curator_model")


class StubRetriever:
    """MediaRetriever ima metodu `retrieve(question, top_n=...)`."""

    def retrieve(self, question: str, *, top_n: int = 10) -> list:
        return []


def test_builds_curator_service(tmp_path: Path) -> None:
    manifest = make_manifest(tmp_path / "FILMIUM")

    service = build_cell_curator(manifest, StubRetriever())

    assert service is not None
```

- [ ] **Step 2: Pokreni testove i potvrdi da padaju**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_cell_ai.py -v`
Expected: FAIL sa `ModuleNotFoundError: No module named 'core.cell.ai'`

- [ ] **Step 3: Napiši minimalnu implementaciju**

```python
# core/cell/ai.py
"""AI sloj ćelije: lokalna Ollama i jedno vezivanje modela iz `cell.json`.

CORE ima pun registar modela sa provajderima, ključevima i vidljivošću. Ćelija
ne nosi ništa od toga — nosi samo adresu lokalne Ollame i ime modela.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from core.ai.ollama_client import OllamaClient
from core.cell.manifest import CellManifest
from core.domains.filmium.curator import CuratorService, MediaRetriever

_CURATOR_TIMEOUT_SECONDS = 60.0


@dataclass(frozen=True)
class CellModelBinding:
    """Model i adresa servisa za jednu ulogu."""

    model: str
    endpoint: str


class CellModelRegistry:
    """Najmanji registar modela: sve uloge vode na isti lokalni model."""

    def __init__(self, manifest: CellManifest) -> None:
        self._manifest = manifest

    def binding(self, domain: str, role: str) -> CellModelBinding:
        """
        Vraća vezivanje modela za traženu ulogu.

        Args:
            domain: Ime domena; u ćeliji postoji samo jedan, pa se ne koristi.
            role: Ime uloge, npr. `curator_model`.

        Returns:
            Model i adresa.

        Raises:
            LookupError: Ako model nije upisan u `cell.json`.
        """
        model = self._manifest.ai_curator_model

        if not model:
            raise LookupError(
                f"cell.json nema ai.curator_model za ulogu {role} ({domain})"
            )

        return CellModelBinding(model=model, endpoint=self._manifest.ai_endpoint)


def build_cell_curator(
    manifest: CellManifest,
    retriever: MediaRetriever,
) -> CuratorService:
    """
    Sklapa Kuratora za ćeliju.

    Args:
        manifest: Manifest ćelije.
        retriever: Pretraživač biblioteke; `CuratorService` ga zove kao
            `retrieve(question, top_n=...)`.

    Returns:
        Kurator vezan za lokalnu Ollamu.
    """
    registry = CellModelRegistry(manifest)
    client = OllamaClient(
        endpoint=manifest.ai_endpoint,
        timeout=_CURATOR_TIMEOUT_SECONDS,
    )

    def generate(
        model: str,
        prompt: str,
        *,
        system: str | None = None,
        fmt: str | None = None,
    ) -> str:
        return client.generate(model, prompt, system=system, fmt=fmt)

    return CuratorService(registry, generate, retriever)
```

- [ ] **Step 4: Pokreni testove i potvrdi da prolaze**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_cell_ai.py -v`
Expected: PASS, 3 testa

- [ ] **Step 5: Commit**

```bash
git add core/cell/ai.py tests/test_cell_ai.py
git commit -m "feat(cell): AI sloj celije nad lokalnom Ollamom"
```

---

### Task 7: `/cell/status` i status ćelije

**Files:**
- Create: `core/cell/status.py`
- Create: `apps/api/routers/cell.py`
- Create: `apps/api/schemas/cell.py`
- Test: `tests/test_cell_status.py`

**Interfaces:**
- Consumes: `CellManifest` (Task 1).
- Produces:
  - `build_cell_status(manifest: CellManifest, *, pending_upgrades: int = 0) -> dict[str, object]`
  - `router` u `apps/api/routers/cell.py`, prefiks `/cell`, ruta `GET /cell/status`
  - `CellStatusResponse` u `apps/api/schemas/cell.py`

Ime `/cell/status` je namerno različito od postojećeg `/status` u `apps/api/routers/system.py:41`.

- [ ] **Step 1: Napiši testove koji padaju**

```python
# tests/test_cell_status.py
import json
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from core.cell.manifest import CELL_MANIFEST_FILENAME, load_cell_manifest
from core.cell.status import build_cell_status


def make_manifest(root: Path):
    root.mkdir(parents=True, exist_ok=True)
    (root / CELL_MANIFEST_FILENAME).write_text(
        json.dumps(
            {
                "domain_id": "filmium",
                "name": "FILMIUM",
                "domain_version": "0.1.0",
                "kernel_version": "0.1.0",
                "port": 8781,
                "created_at": "2026-09-12T10:00:00",
                "rag": {"enabled": False, "namespace": "cell:filmium"},
            }
        ),
        encoding="utf-8",
    )
    return load_cell_manifest(root)


def test_status_payload_has_expected_keys(tmp_path: Path) -> None:
    manifest = make_manifest(tmp_path / "FILMIUM")

    status = build_cell_status(manifest, pending_upgrades=2)

    assert status["domain_id"] == "filmium"
    assert status["name"] == "FILMIUM"
    assert status["kernel_version"] == "0.1.0"
    assert status["port"] == 8781
    assert status["pending_upgrades"] == 2
    assert status["rag_enabled"] is False
    assert status["operating_system"]


def test_router_serves_status(tmp_path: Path) -> None:
    manifest = make_manifest(tmp_path / "FILMIUM")

    from apps.api.routers import cell as cell_router

    cell_router.bind_manifest(manifest)

    app = FastAPI()
    app.include_router(cell_router.router)

    response = TestClient(app).get("/cell/status")

    assert response.status_code == 200
    assert response.json()["domain_id"] == "filmium"


def test_router_without_manifest_returns_503() -> None:
    from apps.api.routers import cell as cell_router

    cell_router.bind_manifest(None)

    app = FastAPI()
    app.include_router(cell_router.router)

    response = TestClient(app).get("/cell/status")

    assert response.status_code == 503
```

- [ ] **Step 2: Pokreni testove i potvrdi da padaju**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_cell_status.py -v`
Expected: FAIL sa `ModuleNotFoundError: No module named 'core.cell.status'`

- [ ] **Step 3: Napiši minimalnu implementaciju**

```python
# core/cell/status.py
"""Status ćelije: ono što CORE pita preko mreže."""

from __future__ import annotations

import platform

from core.cell.manifest import CellManifest


def build_cell_status(
    manifest: CellManifest,
    *,
    pending_upgrades: int = 0,
) -> dict[str, object]:
    """
    Sklapa opis stanja ćelije.

    Args:
        manifest: Manifest ćelije.
        pending_upgrades: Broj primljenih, a neprimenjenih beleški.

    Returns:
        Rečnik spreman za JSON odgovor.
    """
    return {
        "domain_id": manifest.domain_id,
        "name": manifest.name,
        "domain_version": manifest.domain_version,
        "kernel_version": manifest.kernel_version,
        "port": manifest.port,
        "operating_system": platform.system().lower(),
        "node_name": platform.node(),
        "database_path": str(manifest.database_path),
        "rag_enabled": manifest.rag_enabled,
        "rag_namespace": manifest.rag_namespace,
        "pending_upgrades": pending_upgrades,
    }
```

```python
# apps/api/schemas/cell.py
"""Sheme odgovora ćelijskog API-ja."""

from pydantic import BaseModel


class CellStatusResponse(BaseModel):
    """Stanje ćelije koje CORE prikazuje na kartici domena."""

    domain_id: str
    name: str
    domain_version: str
    kernel_version: str
    port: int
    operating_system: str
    node_name: str
    database_path: str
    rag_enabled: bool
    rag_namespace: str
    pending_upgrades: int
```

```python
# apps/api/routers/cell.py
"""Ćelijski API: ono što ćelija izlaže CORE-u.

Ruta je namerno `/cell/status`, a ne `/status`, da se ne sudari sa sistemskim
statusom iz `apps/api/routers/system.py`.
"""

from fastapi import APIRouter, HTTPException, status

from apps.api.schemas.cell import CellStatusResponse
from core.cell.manifest import CellManifest
from core.cell.status import build_cell_status

router = APIRouter(prefix="/cell", tags=["cell"])

_manifest: CellManifest | None = None


def bind_manifest(manifest: CellManifest | None) -> None:
    """Vezuje manifest za router; poziva se pri podizanju ćelije."""

    global _manifest
    _manifest = manifest


@router.get("/status", response_model=CellStatusResponse)
def read_cell_status() -> CellStatusResponse:
    """Vraća stanje ćelije."""

    if _manifest is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Ćelija nema učitan manifest.",
        )

    return CellStatusResponse(**build_cell_status(_manifest))
```

- [ ] **Step 4: Pokreni testove i potvrdi da prolaze**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_cell_status.py -v`
Expected: PASS, 3 testa

- [ ] **Step 5: Commit**

```bash
git add core/cell/status.py apps/api/routers/cell.py apps/api/schemas/cell.py tests/test_cell_status.py
git commit -m "feat(cell): /cell/status kao tacka provere zdravlja celije"
```

---

### Task 8: Sklapanje foldera ćelije

**Files:**
- Create: `core/cell/build.py`
- Create: `scripts/cell/build_cell.py`
- Create: `scripts/cell/templates/cell_app.py.tpl`
- Create: `scripts/cell/templates/start.bat.tpl`
- Create: `scripts/cell/templates/cell.json.tpl`
- Create: `scripts/cell/templates/CLAUDE.md.tpl`
- Test: `tests/test_cell_build.py`

**Interfaces:**
- Consumes: `CellManifest` (Task 1), `ImportGuard` (Task 5), `apps/api/routers/cell.py` (Task 7).
- Produces:
  - `KERNEL_VERSION: str = "0.1.0"`
  - `KERNEL_PYTHON_MODULES: tuple[str, ...]` — putanje u repou koje ulaze u kernel
  - `KERNEL_GUI_MODULES: tuple[str, ...]` — deljeni GUI moduli koje FILMIUM koristi
  - `build_cell(domain_id: str, target: Path, *, repo_root: Path, port: int, detached_from: str) -> CellManifest`
  - `find_foreign_domain_imports(cell_root: Path, domain_id: str) -> tuple[str, ...]`
  - `rewrite_import_guard(text: str, domain_id: str) -> str`

**Odluka o rasporedu (pre-flight ruling):** ćelija zadržava Python korene paketa
`core` i `apps` iz repoa. Spec §4 crta `kernel/`, `domain/` i `api/` kao imena
foldera, ali bi to razbilo svih 119 domenskih fajlova koji uvoze
`core.domains.filmium...`, kao i `apps.api.schemas...` u routerima — svaka
alternativa traži prepisivanje uvoza u 135+ fajlova. Ćelija zato izgleda ovako:

```
F:\FILMIUM\
  cell.json, cell_app.py, start.bat, requirements.txt
  .ai\                 uputstva, atomi, nadogradnje
  core\                kernel: foundation, database, system/file_monitor, cell, rag, ai podskup
  core\domains\filmium\   domen
  apps\api\            routeri, sheme, runtime moduli
  gui\                 front
  data\                baza, artwork, logovi
```

Podela na kernel i domen ostaje stvarna, samo je zapisana u `.ai/PROJECT.yaml`
i u `kernel_version`, umesto u imenima foldera.

- [ ] **Step 1: Napiši testove koji padaju**

```python
# tests/test_cell_build.py
import json
from pathlib import Path

import pytest

from core.cell.build import (
    build_cell,
    find_foreign_domain_imports,
    rewrite_import_guard,
)
from core.cell.manifest import CELL_MANIFEST_FILENAME
from core.foundation.paths import core_paths


def build(tmp_path: Path):
    """Sklapa FILMIUM ćeliju u privremeni folder i vraća njen koren."""

    target = tmp_path / "FILMIUM"
    manifest = build_cell(
        "filmium",
        target,
        repo_root=core_paths.root,
        port=8781,
        detached_from="abc1234",
    )
    return target, manifest


def test_creates_expected_structure(tmp_path: Path) -> None:
    target, _ = build(tmp_path)

    assert (target / CELL_MANIFEST_FILENAME).is_file()
    assert (target / "core" / "foundation" / "paths.py").is_file()
    assert (target / "core" / "database" / "connection.py").is_file()
    assert (target / "core" / "cell" / "manifest.py").is_file()
    assert (target / "core" / "domains" / "filmium" / "repository.py").is_file()
    assert (target / "core" / "domains" / "filmium" / "import_guard" / "scanner.py").is_file()
    assert (target / "apps" / "api" / "routers" / "filmium.py").is_file()
    assert (target / "apps" / "api" / "routers" / "cell.py").is_file()
    assert (target / "gui" / "features" / "filmium").is_dir()
    assert (target / "cell_app.py").is_file()
    assert (target / "start.bat").is_file()
    assert (target / "requirements.txt").is_file()
    assert (target / ".ai" / "CLAUDE.md").is_file()
    assert (target / ".ai" / "atomi").is_dir()
    assert (target / ".ai" / "nadogradnje").is_dir()


def test_keeps_package_markers(tmp_path: Path) -> None:
    target, _ = build(tmp_path)

    assert (target / "core" / "__init__.py").is_file()
    assert (target / "core" / "domains" / "__init__.py").is_file()
    assert (target / "apps" / "__init__.py").is_file()
    assert (target / "apps" / "api" / "__init__.py").is_file()


def test_manifest_records_port_and_origin(tmp_path: Path) -> None:
    target, manifest = build(tmp_path)

    data = json.loads((target / CELL_MANIFEST_FILENAME).read_text(encoding="utf-8"))

    assert manifest.port == 8781
    assert data["port"] == 8781
    assert data["detached_from"] == "abc1234"
    assert data["domain_id"] == "filmium"


def test_does_not_copy_other_domains(tmp_path: Path) -> None:
    target, _ = build(tmp_path)

    assert not (target / "core" / "domains" / "kalima").exists()
    assert not (target / "core" / "domains" / "codium").exists()
    assert not (target / "apps" / "api" / "routers" / "codium.py").exists()
    assert not (target / "core" / "integrations").exists()
    assert not (target / "core" / "security").exists()


def test_no_foreign_domain_imports(tmp_path: Path) -> None:
    target, _ = build(tmp_path)

    assert find_foreign_domain_imports(target, "filmium") == ()


def test_auto_import_runtime_uses_import_guard(tmp_path: Path) -> None:
    target, _ = build(tmp_path)

    text = (target / "apps" / "api" / "auto_import_runtime.py").read_text(
        encoding="utf-8"
    )

    assert "kalima" not in text
    assert "ImportGuard" in text


def test_rewrite_import_guard_replaces_scanner() -> None:
    original = (
        "from core.domains.kalima.security import FileScanner\n"
        "_scanner = FileScanner()\n"
        "value = _scanner.status_for(file_path).value\n"
    )

    rewritten = rewrite_import_guard(original, "filmium")

    assert "kalima" not in rewritten
    assert "from core.domains.filmium.import_guard import ImportGuard" in rewritten
    assert "_guard = ImportGuard()" in rewritten
    assert "_guard.status_for(file_path).value" in rewritten


def test_refuses_existing_non_empty_target(tmp_path: Path) -> None:
    target = tmp_path / "FILMIUM"
    target.mkdir()
    (target / "vec-nesto.txt").write_text("x", encoding="utf-8")

    with pytest.raises(FileExistsError):
        build_cell(
            "filmium",
            target,
            repo_root=core_paths.root,
            port=8781,
            detached_from="abc1234",
        )
```

- [ ] **Step 2: Pokreni testove i potvrdi da padaju**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_cell_build.py -v`
Expected: FAIL sa `ModuleNotFoundError: No module named 'core.cell.build'`

- [ ] **Step 3: Napiši minimalnu implementaciju**

```python
# core/cell/build.py
"""Sklapanje foldera ćelije iz živog repoa.

Ništa se ne briše iz repoa — ovo je kopiranje. Brisanje FILMIUM koda iz CORE-a
je zaseban, kasniji korak, tek kad ćelija dokaže rad.

Ćelija zadržava Python korene `core` i `apps`, pa se nijedan uvoz u kopiranom
kodu ne prepisuje — osim jednog: auto-uvoz prelazi sa KALIMA skenera na
`import_guard` domena.
"""

from __future__ import annotations

import re
import shutil
from datetime import datetime
from pathlib import Path

from core.cell.manifest import CELL_MANIFEST_FILENAME, CellManifest, load_cell_manifest

KERNEL_VERSION = "0.1.0"

# Kernel ćelije: putanje relativne na koren repoa.
KERNEL_PYTHON_MODULES: tuple[str, ...] = (
    "core/__init__.py",
    "core/foundation",
    "core/database",
    "core/cell",
    "core/rag",
    "core/system/__init__.py",
    "core/system/file_monitor",
    "core/ai/__init__.py",
    "core/ai/ollama_client.py",
    "core/ai/persona_store.py",
    "core/ai/personas.py",
    "core/models",
    "core/domains/__init__.py",
    "apps/__init__.py",
    "apps/api/__init__.py",
    "apps/api/dependencies.py",
    "apps/api/streaming.py",
    "apps/api/routers/__init__.py",
    "apps/api/routers/cell.py",
    "apps/api/schemas/__init__.py",
    "apps/api/schemas/cell.py",
)

# Runtime moduli koje FILMIUM routeri traže.
DOMAIN_RUNTIME_MODULES: tuple[str, ...] = (
    "apps/api/auto_import_runtime.py",
    "apps/api/torrent_runtime.py",
    "apps/api/curator_runtime.py",
    "apps/api/disk_runtime.py",
)

# GUI moduli koje FILMIUM koristi van svoje fascikle (mereno 2026-09-12).
KERNEL_GUI_MODULES: tuple[str, ...] = (
    "apps/gui/src/services/httpClient.ts",
    "apps/gui/src/lib/sound.ts",
    "apps/gui/src/lib/useCoreSetting.ts",
    "apps/gui/src/components/chat/CoreChat.tsx",
    "apps/gui/src/components/chat/CoreAssistantChat.tsx",
)

_IGNORE = shutil.ignore_patterns("__pycache__", "*.pyc", ".pytest_cache")

_FOREIGN_IMPORT = re.compile(
    r"^\s*from\s+core\.domains\.(?P<domain>\w+)", re.MULTILINE
)


def _copy(source: Path, target: Path) -> None:
    """Kopira fajl ili folder, praveći roditeljske direktorijume."""

    target.parent.mkdir(parents=True, exist_ok=True)

    if source.is_dir():
        shutil.copytree(source, target, ignore=_IGNORE, dirs_exist_ok=True)
    else:
        shutil.copy2(source, target)


def _render_template(repo_root: Path, name: str, values: dict[str, str]) -> str:
    """Učitava šablon iz `scripts/cell/templates` i popunjava ga."""

    text = (repo_root / "scripts" / "cell" / "templates" / name).read_text(
        encoding="utf-8"
    )

    for key, value in values.items():
        text = text.replace("{{" + key + "}}", value)

    return text


def rewrite_import_guard(text: str, domain_id: str) -> str:
    """
    Prevodi auto-uvoz sa KALIMA skenera na `import_guard` domena.

    Args:
        text: Sadržaj `auto_import_runtime.py` iz repoa.
        domain_id: Domen ćelije.

    Returns:
        Izmenjen sadržaj, bez ijednog pomena KALIMA-e.
    """
    text = text.replace(
        "from core.domains.kalima.security import FileScanner",
        f"from core.domains.{domain_id}.import_guard import ImportGuard",
    )
    text = text.replace("_scanner = FileScanner()", "_guard = ImportGuard()")
    text = text.replace("_scanner.status_for", "_guard.status_for")

    return text.replace(
        "KALIMA sigurnosnim skenerom kao adapterom",
        "sopstvenim import_guard-om kao adapterom",
    )


def build_cell(
    domain_id: str,
    target: Path,
    *,
    repo_root: Path,
    port: int,
    detached_from: str,
) -> CellManifest:
    """
    Sklapa folder ćelije za zadati domen.

    Args:
        domain_id: Identifikator domena, npr. `filmium`.
        target: Ciljni folder ćelije. Mora biti prazan ili nepostojeći.
        repo_root: Koren CORE repoa iz kog se kopira.
        port: Port koji CORE dodeljuje ćeliji.
        detached_from: Kratak hash commita iz kog je ćelija izvučena.

    Returns:
        Manifest sklopljene ćelije.

    Raises:
        FileExistsError: Ako ciljni folder postoji i nije prazan.
    """
    if target.exists() and any(target.iterdir()):
        raise FileExistsError(f"Ciljni folder nije prazan: {target}")

    target.mkdir(parents=True, exist_ok=True)

    # Kernel — isti raspored kao u repou, pa uvozi rade nepromenjeni.
    for module in KERNEL_PYTHON_MODULES:
        source = repo_root / module
        if source.exists():
            _copy(source, target / module)

    # Domen.
    _copy(
        repo_root / "core" / "domains" / domain_id,
        target / "core" / "domains" / domain_id,
    )

    # Routeri i sheme domena.
    routers = repo_root / "apps" / "api" / "routers"
    for router in sorted(routers.glob(f"{domain_id}*.py")):
        _copy(router, target / "apps" / "api" / "routers" / router.name)

    schemas = repo_root / "apps" / "api" / "schemas"
    for schema in sorted(schemas.glob(f"{domain_id}*.py")):
        _copy(schema, target / "apps" / "api" / "schemas" / schema.name)

    # Runtime moduli; auto-uvoz se prepisuje na import_guard.
    for module in DOMAIN_RUNTIME_MODULES:
        source = repo_root / module
        if not source.exists():
            continue
        destination = target / module
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(
            rewrite_import_guard(source.read_text(encoding="utf-8"), domain_id),
            encoding="utf-8",
        )

    # GUI.
    _copy(
        repo_root / "apps" / "gui" / "src" / "features" / domain_id,
        target / "gui" / "features" / domain_id,
    )
    for module in KERNEL_GUI_MODULES:
        source = repo_root / module
        if source.exists():
            _copy(source, target / "gui" / Path(module).relative_to("apps/gui/src"))

    # `.ai` direktorijum ćelije.
    ai_root = target / ".ai"
    (ai_root / "atomi").mkdir(parents=True, exist_ok=True)
    (ai_root / "nadogradnje").mkdir(parents=True, exist_ok=True)
    (ai_root / "dev-log" / "entries").mkdir(parents=True, exist_ok=True)
    (ai_root / "CLAUDE.md").write_text(
        _render_template(
            repo_root,
            "CLAUDE.md.tpl",
            {"DOMAIN_ID": domain_id, "DOMAIN_NAME": domain_id.upper()},
        ),
        encoding="utf-8",
    )

    # Pokretanje i zavisnosti.
    (target / "cell_app.py").write_text(
        _render_template(repo_root, "cell_app.py.tpl", {"DOMAIN_ID": domain_id}),
        encoding="utf-8",
    )
    (target / "start.bat").write_text(
        _render_template(repo_root, "start.bat.tpl", {"PORT": str(port)}),
        encoding="utf-8",
    )
    _copy(repo_root / "requirements.txt", target / "requirements.txt")

    # Manifest.
    (target / CELL_MANIFEST_FILENAME).write_text(
        _render_template(
            repo_root,
            "cell.json.tpl",
            {
                "DOMAIN_ID": domain_id,
                "DOMAIN_NAME": domain_id.upper(),
                "KERNEL_VERSION": KERNEL_VERSION,
                "PORT": str(port),
                "CREATED_AT": datetime.now().isoformat(timespec="seconds"),
                "DETACHED_FROM": detached_from,
            },
        ),
        encoding="utf-8",
    )

    return load_cell_manifest(target)


def find_foreign_domain_imports(
    cell_root: Path,
    domain_id: str,
) -> tuple[str, ...]:
    """
    Traži uvoze ka drugim domenima u sklopljenoj ćeliji.

    Args:
        cell_root: Koren ćelije.
        domain_id: Domen kom ćelija pripada.

    Returns:
        Redovi oblika `putanja:linija: tekst` za svaki nađen strani uvoz.
    """
    findings: list[str] = []

    for path in sorted(cell_root.rglob("*.py")):
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue

        for match in _FOREIGN_IMPORT.finditer(text):
            if match.group("domain") == domain_id:
                continue
            line = text.count("\n", 0, match.start()) + 1
            findings.append(
                f"{path.relative_to(cell_root)}:{line}: {match.group(0).strip()}"
            )

    return tuple(findings)
```

```
# scripts/cell/templates/cell_app.py.tpl
"""Ulazna tačka ćelije {{DOMAIN_ID}}.

Diže FastAPI sa routerima domena nad sopstvenom bazom, bez CORE-a.
"""

import sys
from contextlib import asynccontextmanager
from pathlib import Path

CELL_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(CELL_ROOT))

from fastapi import FastAPI  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402

from apps.api.routers import cell as cell_router  # noqa: E402
from core.cell.database import initialize_cell_database  # noqa: E402
from core.cell.manifest import load_cell_manifest  # noqa: E402
from core.cell.paths import apply_cell_paths  # noqa: E402

MANIFEST = load_cell_manifest(CELL_ROOT)


@asynccontextmanager
async def cell_lifespan(_: FastAPI):
    """Priprema putanje i bazu pre nego što ćelija počne da služi."""

    apply_cell_paths(MANIFEST)
    initialize_cell_database(MANIFEST)
    cell_router.bind_manifest(MANIFEST)
    yield


app = FastAPI(
    title=MANIFEST.name,
    version=MANIFEST.domain_version,
    lifespan=cell_lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(cell_router.router)
```

```
# scripts/cell/templates/start.bat.tpl
@echo off
REM Pokretanje celije na dodeljenom portu.
cd /d "%~dp0"
python -m uvicorn cell_app:app --host 127.0.0.1 --port {{PORT}}
```

```
# scripts/cell/templates/cell.json.tpl
{
  "domain_id": "{{DOMAIN_ID}}",
  "name": "{{DOMAIN_NAME}}",
  "domain_version": "0.1.0",
  "kernel_version": "{{KERNEL_VERSION}}",
  "port": {{PORT}},
  "core_url": "http://localhost:8000",
  "created_at": "{{CREATED_AT}}",
  "detached_from": "{{DETACHED_FROM}}",
  "ai": {"endpoint": "http://localhost:11434", "curator_model": null},
  "rag": {"enabled": false, "namespace": "cell:{{DOMAIN_ID}}"}
}
```

```
# scripts/cell/templates/CLAUDE.md.tpl
# {{DOMAIN_NAME}} — uputstva za AI

Ovo je odcepljena ćelija domena {{DOMAIN_ID}}. Radi samostalno, bez CORE-a.

## Struktura

- `core/foundation`, `core/database`, `core/cell`, `core/system`, `core/rag`,
  `core/ai` — kernel. Ne menja se ovde; menja se nadogradnjom kernela.
- `core/domains/{{DOMAIN_ID}}` — kod domena. Ovde ide najveći deo rada.
- `apps/api/` — routeri i sheme.
- `gui/` — korisnički deo.
- `.ai/atomi/` — atomske beleške, jedna činjenica po fajlu.
- `.ai/nadogradnje/` — beleške primljene iz CORE-a; ništa se ne primenjuje samo od sebe.

## Pravila

- Testovi se pokreću iz korena ćelije.
- Kod domena ne sme da uvozi nijedan drugi domen.
- Pre izmene pročitaj `.ai/PROJECT.yaml` i poslednje unose u `.ai/dev-log/entries/`.
```

```python
# scripts/cell/build_cell.py
"""Sklapa folder ćelije za zadati domen.

Upotreba:
    ./.venv/Scripts/python.exe scripts/cell/build_cell.py filmium F:\\FILMIUM 8781
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from core.cell.build import build_cell, find_foreign_domain_imports  # noqa: E402
from core.foundation.paths import core_paths  # noqa: E402


def main(argv: list[str]) -> int:
    if len(argv) != 4:
        print("Upotreba: build_cell.py <domain_id> <ciljni-folder> <port>")
        return 2

    domain_id, target, port = argv[1], Path(argv[2]), int(argv[3])

    head = subprocess.run(
        ["git", "rev-parse", "--short", "HEAD"],
        cwd=core_paths.root,
        capture_output=True,
        text=True,
        check=False,
    ).stdout.strip()

    manifest = build_cell(
        domain_id,
        target,
        repo_root=core_paths.root,
        port=port,
        detached_from=head or "nepoznato",
    )

    foreign = find_foreign_domain_imports(target, domain_id)
    if foreign:
        print("Ćelija ima uvoze ka drugim domenima:")
        for line in foreign:
            print(f"  {line}")
        return 1

    print(f"Ćelija sklopljena: {manifest.root} (port {manifest.port})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
```

- [ ] **Step 4: Pokreni testove i potvrdi da prolaze**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_cell_build.py -v`
Expected: PASS, 8 testova

Ako `test_no_foreign_domain_imports` padne, nalaz je stvaran: ispiši prijavljene
fajlove i reši svaki uvoz. Najčešći uzrok je novi runtime modul koji nije u
`DOMAIN_RUNTIME_MODULES`, ili domenski fajl koji stvarno zove drugi domen.

- [ ] **Step 5: Commit**

```bash
git add core/cell/build.py scripts/cell tests/test_cell_build.py
git commit -m "feat(cell): sklapanje foldera celije iz repoa, sa proverom stranih uvoza"
```

---

### Task 9: Čišćenje tajni pri commit-u

**Files:**
- Create: `scripts/git/scrub_secrets.py`
- Create: `.gitattributes`
- Create: `docs/CELIJA_TAJNE.md`
- Test: `tests/test_scrub_secrets.py`

**Interfaces:**
- Consumes: ništa.
- Produces:
  - `SECRET_FIELDS: tuple[str, ...]` — imena polja koja se čiste
  - `placeholder_for(field: str, source_name: str = "") -> str` — vraća tekst oblika `[ Here put API key for TMDB ]`
  - `scrub_json_text(text: str, *, source_name: str) -> str`

Ovo je git `clean` filter: radna kopija zadržava prave vrednosti, a ono što uđe u commit nosi rezervisan tekst. Filter deluje samo na buduće commit-e — commit `0e78fa3` i dalje sadrži ključ dok se istorija ne prepiše.

- [ ] **Step 1: Napiši testove koji padaju**

```python
# tests/test_scrub_secrets.py
import json

from scripts.git.scrub_secrets import placeholder_for, scrub_json_text


def test_replaces_api_key_and_token() -> None:
    text = json.dumps({"access_token": "tajna", "api_key": "[Here put api_key]"})

    scrubbed = json.loads(scrub_json_text(text, source_name="tmdb.json"))

    assert scrubbed["api_key"] == "[ Here put API key for TMDB ]"
    assert scrubbed["access_token"] == "[ Here put access token for TMDB ]"


def test_keeps_non_secret_fields() -> None:
    text = json.dumps({"api_key": "tajna", "language": "sr-RS"})

    scrubbed = json.loads(scrub_json_text(text, source_name="tmdb.json"))

    assert scrubbed["language"] == "sr-RS"


def test_nested_fields_are_scrubbed() -> None:
    text = json.dumps({"db": {"password": "tajna", "host": "localhost"}})

    scrubbed = json.loads(scrub_json_text(text, source_name="rag.json"))

    assert scrubbed["db"]["password"] == "[ Here put password for RAG ]"
    assert scrubbed["db"]["host"] == "localhost"


def test_already_scrubbed_text_is_unchanged() -> None:
    text = json.dumps({"api_key": "[Here put api_key]"})

    assert json.loads(scrub_json_text(text, source_name="tmdb.json"))["api_key"] == (
        "[ Here put API key for TMDB ]"
    )


def test_null_value_stays_null() -> None:
    text = json.dumps({"password": None})

    assert json.loads(scrub_json_text(text, source_name="rag.json"))["password"] is None


def test_invalid_json_passes_through() -> None:
    text = "{ ovo nije json"

    assert scrub_json_text(text, source_name="tmdb.json") == text


def test_placeholder_names_the_source() -> None:
    assert placeholder_for("api_key", "tmdb.json") == "[ Here put API key for TMDB ]"
```

- [ ] **Step 2: Pokreni testove i potvrdi da padaju**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_scrub_secrets.py -v`
Expected: FAIL sa `ModuleNotFoundError: No module named 'scripts.git.scrub_secrets'`

Ako `scripts` nije paket, dodaj prazne `scripts/__init__.py` i `scripts/git/__init__.py` u istom koraku.

- [ ] **Step 3: Napiši minimalnu implementaciju**

```python
# scripts/git/scrub_secrets.py
"""Git `clean` filter: uklanja tajne iz onoga što ulazi u commit.

Radna kopija ostaje netaknuta — filter deluje samo na sadržaj koji git upisuje
u objekat. Čita sa stdin, piše na stdout.

Važno: filter čisti buduće commit-e. Tajne koje su već u istoriji uklanjaju se
zasebno, prepisivanjem istorije, pre objavljivanja repoa.
"""

from __future__ import annotations

import json
import sys

SECRET_FIELDS: tuple[str, ...] = (
    "api_key",
    "access_token",
    "token",
    "password",
    "secret",
    "client_secret",
)

_LABELS = {
    "api_key": "[Here put api_key]",
    "access_token": "access token",
    "token": "token",
    "password": "[Here put password]",
    "secret": "[Here put secret]",
    "client_secret": "[Here put client_secret]",
}


def placeholder_for(field: str, source_name: str = "") -> str:
    """
    Pravi rezervisan tekst za dato polje.

    Args:
        field: Ime polja, npr. `api_key`.
        source_name: Ime fajla, npr. `tmdb.json`; koristi se za naziv izvora.

    Returns:
        Tekst oblika `[ Here put API key for TMDB ]`.
    """
    label = _LABELS.get(field, field)
    source = source_name.split(".")[0].upper() or "THIS SERVICE"

    return f"[ Here put {label} for {source} ]"


def _scrub(value: object, source_name: str) -> object:
    if isinstance(value, dict):
        return {
            key: (
                placeholder_for(key, source_name)
                if key in SECRET_FIELDS and isinstance(inner, str) and inner
                else _scrub(inner, source_name)
            )
            for key, inner in value.items()
        }

    if isinstance(value, list):
        return [_scrub(item, source_name) for item in value]

    return value


def scrub_json_text(text: str, *, source_name: str) -> str:
    """
    Zamenjuje vrednosti tajni rezervisanim tekstom.

    Args:
        text: Sadržaj JSON fajla.
        source_name: Ime fajla, radi čitljivog naziva izvora.

    Returns:
        Očišćen JSON tekst. Neispravan JSON se vraća nepromenjen — filter nikad
        ne sme da pokvari commit.
    """
    try:
        data = json.loads(text)
    except ValueError:
        return text

    return json.dumps(_scrub(data, source_name), indent=2, ensure_ascii=False) + "\n"


def main(argv: list[str]) -> int:
    source_name = argv[1] if len(argv) > 1 else ""
    sys.stdout.write(scrub_json_text(sys.stdin.read(), source_name=source_name))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
```

```
# .gitattributes
config/*.json filter=core-secrets
```

```markdown
# docs/CELIJA_TAJNE.md

# Tajne u repou

Filter `core-secrets` uklanja vrednosti ključeva iz onoga što ide u commit.
Radna kopija zadržava prave vrednosti.

## Uključivanje filtera na novoj mašini

Filter se ne prenosi kroz klon — svaka radna kopija ga podešava jednom:

```bash
git config filter.core-secrets.clean "./.venv/Scripts/python.exe scripts/git/scrub_secrets.py %f"
git config filter.core-secrets.smudge cat
```

## Šta filter ne rešava

Commit `0e78fa3` sadrži TMDB `access_token` i `api_key`. Filter ne dira
istoriju. Pre objavljivanja bilo kog repoa (CORE ili ćelije):

1. Povuci i ponovo izdaj TMDB ključ.
2. Prepiši istoriju alatom `git filter-repo`, uklanjajući `config/tmdb.json`.
3. Tek tada `git push`.
```

- [ ] **Step 4: Pokreni testove i potvrdi da prolaze**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_scrub_secrets.py -v`
Expected: PASS, 7 testova

- [ ] **Step 5: Uključi filter i proveri ga na živom fajlu**

```bash
git config filter.core-secrets.clean "./.venv/Scripts/python.exe scripts/git/scrub_secrets.py %f"
git config filter.core-secrets.smudge cat
git check-attr filter config/tmdb.json
```

Expected: `config/tmdb.json: filter: core-secrets`

Zatim proveri šta bi ušlo u commit:

```bash
git add config/tmdb.json
git show :config/tmdb.json
```

Expected: ispis sadrži `[ Here put API key for TMDB ]`, a `config/tmdb.json` na disku i dalje ima pravi ključ.

- [ ] **Step 6: Commit**

```bash
git add .gitattributes scripts/git tests/test_scrub_secrets.py docs/CELIJA_TAJNE.md config/tmdb.json
git commit -m "chore(security): git clean filter za tajne u config/*.json"
```

---

### Task 10: Sklapanje žive FILMIUM ćelije

**Files:**
- Create: `.ai/dev-log/entries/2026-09-12-celija-filmium.md`

**Interfaces:**
- Consumes: sve prethodne zadatke.
- Produces: živu ćeliju na disku koja odgovara na `GET /cell/status`.

Ovo je jedini zadatak koji dodiruje disk van repoa. Radi se korak po korak, i
svaki korak ima proveru. Ćelija se sklapa u privremeni folder — premeštanje na
`F:\` radi korisnik tek kad ćelija odradi pun ciklus.

- [ ] **Step 1: Sklopi ćeliju u privremeni folder**

```bash
./.venv/Scripts/python.exe scripts/cell/build_cell.py filmium "C:/Users/Game Centar/AppData/Local/Temp/celija-proba/FILMIUM" 8781
```

Expected: `Ćelija sklopljena: ... (port 8781)`, izlazni kod 0, nijedan prijavljen
strani uvoz. Ako skripta prijavi strane uvoze, to je stvaran nalaz — reši ga u
`core/cell/build.py` (Task 8), ne ručno u sklopljenoj ćeliji, da bi i sledeća
ćelija nastala ispravna.

- [ ] **Step 2: Potvrdi da se ćelija uvozi bez CORE-a na putanji**

```bash
cd "C:/Users/Game Centar/AppData/Local/Temp/celija-proba/FILMIUM" && "C:/Users/Game Centar/Documents/AI HOME/CORE - Cloude/.venv/Scripts/python.exe" -c "import cell_app; print(cell_app.MANIFEST.domain_id, cell_app.MANIFEST.port)"
```

Expected: `filmium 8781`. Greška `ModuleNotFoundError` znači da `build_cell`
nije poneo neki kernel modul — dopuni `KERNEL_PYTHON_MODULES` u Task 8, dodaj
test za taj modul i ponovi od koraka 1.

- [ ] **Step 3: Prenesi podatke u bazu ćelije**

```bash
./.venv/Scripts/python.exe scripts/cell/extract_domain_db.py "C:/Users/Game Centar/AppData/Local/Temp/celija-proba/FILMIUM"
```

Expected: ispis broja redova po tabeli i poruka `Preneto N redova`, bez reda
`NESLAGANJE`.

- [ ] **Step 4: Podigni ćeliju i proveri status**

```bash
cd "C:/Users/Game Centar/AppData/Local/Temp/celija-proba/FILMIUM" && "C:/Users/Game Centar/Documents/AI HOME/CORE - Cloude/.venv/Scripts/python.exe" -m uvicorn cell_app:app --host 127.0.0.1 --port 8781
```

U drugom terminalu:

```bash
curl http://127.0.0.1:8781/cell/status
```

Expected: JSON sa `"domain_id": "filmium"`, `"kernel_version": "0.1.0"`,
`"port": 8781`, i `"database_path"` koji pokazuje na bazu ćelije, ne na
`data/database/core.db`.

- [ ] **Step 5: Potvrdi da CORE i dalje radi nepromenjeno**

Run: `./.venv/Scripts/python.exe -m pytest tests/ -q`
Expected: PASS, bez novih padova u odnosu na stanje pre ovog plana.

- [ ] **Step 6: Zapiši dev-log i commit**

Upiši `.ai/dev-log/entries/2026-09-12-celija-filmium.md` sa: šta je sklopljeno,
koji port, koliko redova je preneto, koji su moduli morali da se dodaju u
kernel, i šta ostaje za sledeći plan.

```bash
git add .ai/dev-log/entries/2026-09-12-celija-filmium.md
git commit -m "docs(dev-log): ziva FILMIUM celija sa sopstvenom bazom i /cell/status"
```

---

## Šta ovaj plan namerno ne radi

Sledeći plan (`docs/superpowers/plans/`, dokument koji dolazi posle ovog) pokriva:

- GUI ćelije: Vite konfiguracija, build i serviranje iz ćelijskog FastAPI-ja.
- CORE Settings ekran „Ćelijski sistem": tabela `cells`, skeniranje direktorijuma, kartica domena sa „Poveži / Dodaj domen".
- Beleške o nadogradnji: tabela `cell_upgrade_notes`, `POST /cell/upgrades`, pozadinski radnik na 900 sekundi, prikaz i biranje u ćeliji.
- RAG ćelije nad `.ai/atomi/`: format atoma, unos, prostor imena `cell:filmium`.
- Sopstveni git repozitorijum ćelije i prepisivanje istorije pre objavljivanja.
- Tabela komandi koje Kurator sme da izvrši nad bibliotekom (pretraga i prikaz filmova).
- Brisanje FILMIUM koda i tabela iz CORE repoa — tek kad ćelija odradi pun ciklus rada.
