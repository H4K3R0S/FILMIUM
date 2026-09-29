# FILMIUM Torrenti — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** FILMIUM dobija torrent modul koji dodaje torrent pauziran, pokaže listu fajlova, pusti preuzimanje tek kad korisnik štiklira i odobri, prikaže progres uživo i po završetku ponudi uvoz.

**Architecture:** Poslovna logika je u `core/domains/filmium/torrents/` i ne zna ništa o torrent klijentu. Jedini modul koji dodiruje qBittorrent je `torrent_engine.py`, iza `TorrentEngine` protokola, pa svi testovi rade sa lažnim engine-om bez mreže. FastAPI sloj je tanak: REST rute plus jedan SSE strim za progres. GUI dobija stavku „Torrenti" u FILMIUM sidebar-u, stranicu sa tri taba i kategoriju u FILMIUM podešavanjima.

**Tech Stack:** Python 3.14, FastAPI, SQLite (`core.database`), `qbittorrent-api`, React 18 + TypeScript, Vite, pytest, vitest.

**Spec:** `docs/superpowers/specs/2026-09-11-filmium-torrenti-design.md`

## Global Constraints

- Python komande idu kroz projektni venv: `./.venv/Scripts/python.exe -m pytest`. Sistemski `python` se ne koristi.
- Sav korisnički vidljiv tekst je na srpskom, ćirilica se ne koristi.
- `torrent_service.py`, `torrent_repository.py` i `torrent_watch_service.py` **ne smeju** da uvoze `qbittorrentapi`. Taj uvoz postoji samo u `torrent_engine.py` i to lenjo, unutar funkcije.
- Testovi ne smeju da otvaraju mrežu niti da zahtevaju pokrenut qBittorrent.
- Svi qBittorrent pozivi koriste kategoriju `FILMIUM` (konstanta `QBIT_CATEGORY`). Torrenti van te kategorije se ne čitaju i ne diraju.
- Nova migracija je `V32`; poslednja postojeća je `V31` u `core/domains/filmium/migrations.py`.
- Komentari u kodu prate postojeći stil FILMIUM modula: `# ========== NASLOV ==========` iznad celina.
- Statusi torrenta su tačno: `detected`, `metadata_fetching`, `awaiting_approval`, `downloading`, `paused`, `completed`, `error`.
- Ekstenzije koje su podrazumevano odštiklirane: `.nfo .txt .url .jpg .png .sfv`.

---

### Task 1: Modeli i migracija baze

**Files:**
- Create: `core/domains/filmium/torrents/__init__.py`
- Create: `core/domains/filmium/torrents/torrent_models.py`
- Create: `core/domains/filmium/migration_v32.py`
- Modify: `core/domains/filmium/migrations.py` (dodati uvoz i stavku u `FILMIUM_MIGRATIONS`)
- Test: `tests/test_filmium_torrent_migration.py`

**Interfaces:**
- Consumes: `core.database.DatabaseMigration`, `core.database.core_database_connection`, `core.database.runtime.initialize_core_database`
- Produces: `TorrentStatus`, `TorrentFileEntry`, `TorrentMetadata`, `TorrentProgress`, `TorrentEntry`, `TorrentSettings`, `EngineHealth`, `QBIT_CATEGORY`, `FILMIUM_MIGRATION_V32`

- [ ] **Step 1: Write the failing test**

`tests/test_filmium_torrent_migration.py`:

```python
# ========== TESTOVI: MIGRACIJA V32 (torrenti) ==========
from __future__ import annotations

from pathlib import Path

from core.database import core_database_connection
from core.database.runtime import initialize_core_database


def _columns(connection, table: str) -> set[str]:
    rows = connection.execute(f"PRAGMA table_info({table})").fetchall()
    return {row[1] for row in rows}


def test_migration_v32_creates_torrent_tables(tmp_path: Path) -> None:
    database_path = tmp_path / "torrents.db"
    initialize_core_database(database_path)

    with core_database_connection(database_path) as connection:
        assert _columns(connection, "filmium_torrents") == {
            "info_hash",
            "name",
            "source",
            "source_kind",
            "status",
            "save_path",
            "total_bytes",
            "added_at",
            "completed_at",
            "error_message",
        }
        assert _columns(connection, "filmium_torrent_files") == {
            "info_hash",
            "file_index",
            "path",
            "size_bytes",
            "selected",
        }
        assert "watch_folder" in _columns(connection, "filmium_torrent_settings")


def test_migration_v32_seeds_single_settings_row(tmp_path: Path) -> None:
    database_path = tmp_path / "torrents.db"
    initialize_core_database(database_path)

    with core_database_connection(database_path) as connection:
        rows = connection.execute(
            "SELECT id, host, port, max_active FROM filmium_torrent_settings"
        ).fetchall()

    assert len(rows) == 1
    assert rows[0][0] == 1
    assert rows[0][1] == "127.0.0.1"
    assert rows[0][2] == 8080
    assert rows[0][3] == 3
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_filmium_torrent_migration.py -v`
Expected: FAIL sa `sqlite3.OperationalError: no such table: filmium_torrents`

- [ ] **Step 3: Write the migration**

`core/domains/filmium/migration_v32.py`:

```python
from core.database import DatabaseMigration


# ==========          TORRENTI (MODUL 6)          ==========
#
# Tri tabele: torrenti koje je modul dodao, njihovi fajlovi sa štikliranjem,
# i jedan red podešavanja. Stanje samog preuzimanja drži qBittorrent; ovde
# se pamti šta je korisnik izabrao i odobrio.

FILMIUM_MIGRATION_V32 = DatabaseMigration(
    scope="filmium",
    version=32,
    name="add_torrents",
    statements=(
        """
        CREATE TABLE IF NOT EXISTS filmium_torrents (
            info_hash TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            source TEXT NOT NULL,
            source_kind TEXT NOT NULL,
            status TEXT NOT NULL,
            save_path TEXT NOT NULL DEFAULT '',
            total_bytes INTEGER NOT NULL DEFAULT 0,
            added_at TEXT NOT NULL,
            completed_at TEXT,
            error_message TEXT
        )
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_filmium_torrents_status
        ON filmium_torrents (status)
        """,
        """
        CREATE TABLE IF NOT EXISTS filmium_torrent_files (
            info_hash TEXT NOT NULL,
            file_index INTEGER NOT NULL,
            path TEXT NOT NULL,
            size_bytes INTEGER NOT NULL DEFAULT 0,
            selected INTEGER NOT NULL DEFAULT 1,
            PRIMARY KEY (info_hash, file_index)
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS filmium_torrent_settings (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            host TEXT NOT NULL DEFAULT '127.0.0.1',
            port INTEGER NOT NULL DEFAULT 8080,
            username TEXT NOT NULL DEFAULT '',
            password TEXT NOT NULL DEFAULT '',
            watch_folder TEXT NOT NULL DEFAULT '',
            download_path TEXT NOT NULL DEFAULT '',
            max_download_kbs INTEGER NOT NULL DEFAULT 0,
            max_upload_kbs INTEGER NOT NULL DEFAULT 0,
            max_active INTEGER NOT NULL DEFAULT 3,
            auto_start INTEGER NOT NULL DEFAULT 1,
            seed_after_complete INTEGER NOT NULL DEFAULT 0,
            delete_source_torrent INTEGER NOT NULL DEFAULT 0,
            unselected_extensions TEXT NOT NULL
                DEFAULT '.nfo,.txt,.url,.jpg,.png,.sfv'
        )
        """,
        """
        INSERT OR IGNORE INTO filmium_torrent_settings (id) VALUES (1)
        """,
    ),
)
```

- [ ] **Step 4: Register the migration**

U `core/domains/filmium/migrations.py`, odmah ispod uvoza za `V31`:

```python
from core.domains.filmium.migration_v32 import (
    FILMIUM_MIGRATION_V32,
)
```

i na kraj torke `FILMIUM_MIGRATIONS`, posle `FILMIUM_MIGRATION_V31,`:

```python
    FILMIUM_MIGRATION_V32,
```

- [ ] **Step 5: Write the models**

`core/domains/filmium/torrents/torrent_models.py`:

```python
# ========== MODELI TORRENT MODULA ==========
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

# Kategorija u qBittorrent-u. Modul vidi i dira isključivo torrente iz nje.
QBIT_CATEGORY = "FILMIUM"

DEFAULT_UNSELECTED_EXTENSIONS: tuple[str, ...] = (
    ".nfo", ".txt", ".url", ".jpg", ".png", ".sfv",
)


# ========== STATUSI ==========
class TorrentStatus(str, Enum):
    DETECTED = "detected"                    # zabeležen, još nije poslat klijentu
    METADATA_FETCHING = "metadata_fetching"  # čeka metapodatke (magnet)
    AWAITING_APPROVAL = "awaiting_approval"  # lista fajlova spremna, čeka korisnika
    DOWNLOADING = "downloading"
    PAUSED = "paused"
    COMPLETED = "completed"
    ERROR = "error"


# ========== FAJL UNUTAR TORRENTA ==========
@dataclass(frozen=True)
class TorrentFileEntry:
    file_index: int
    path: str
    size_bytes: int = 0
    selected: bool = True


# ========== METAPODACI ==========
@dataclass(frozen=True)
class TorrentMetadata:
    info_hash: str
    name: str
    total_bytes: int = 0
    files: tuple[TorrentFileEntry, ...] = ()
    has_metadata: bool = False


# ========== PROGRES ==========
@dataclass(frozen=True)
class TorrentProgress:
    info_hash: str
    progress: float = 0.0        # 0.0 - 1.0
    download_rate: int = 0       # bajtova u sekundi
    upload_rate: int = 0
    eta_seconds: int | None = None
    seeds: int = 0
    peers: int = 0
    is_finished: bool = False
    is_paused: bool = False
    error_message: str | None = None


# ========== ZAPIS TORRENTA ==========
@dataclass
class TorrentEntry:
    info_hash: str
    name: str
    source: str
    source_kind: str = "magnet"   # "magnet" ili "file"
    status: TorrentStatus = TorrentStatus.DETECTED
    save_path: str = ""
    total_bytes: int = 0
    added_at: datetime = field(default_factory=datetime.now)
    completed_at: datetime | None = None
    error_message: str | None = None


# ========== ZDRAVLJE ENGINE-a ==========
@dataclass(frozen=True)
class EngineHealth:
    available: bool
    version: str | None = None
    message: str | None = None


# ========== PODEŠAVANJA ==========
@dataclass
class TorrentSettings:
    host: str = "127.0.0.1"
    port: int = 8080
    username: str = ""
    password: str = ""
    watch_folder: str = ""
    download_path: str = ""
    max_download_kbs: int = 0
    max_upload_kbs: int = 0
    max_active: int = 3
    auto_start: bool = True
    seed_after_complete: bool = False
    delete_source_torrent: bool = False
    unselected_extensions: tuple[str, ...] = DEFAULT_UNSELECTED_EXTENSIONS
```

`core/domains/filmium/torrents/__init__.py`:

```python
from core.domains.filmium.torrents.torrent_models import (
    DEFAULT_UNSELECTED_EXTENSIONS,
    QBIT_CATEGORY,
    EngineHealth,
    TorrentEntry,
    TorrentFileEntry,
    TorrentMetadata,
    TorrentProgress,
    TorrentSettings,
    TorrentStatus,
)

__all__ = [
    "DEFAULT_UNSELECTED_EXTENSIONS",
    "QBIT_CATEGORY",
    "EngineHealth",
    "TorrentEntry",
    "TorrentFileEntry",
    "TorrentMetadata",
    "TorrentProgress",
    "TorrentSettings",
    "TorrentStatus",
]
```

- [ ] **Step 6: Run test to verify it passes**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_filmium_torrent_migration.py -v`
Expected: PASS, 2 testa

- [ ] **Step 7: Run the whole suite (migracije su deljeno stanje)**

Run: `./.venv/Scripts/python.exe -m pytest -q`
Expected: bez novih padova

- [ ] **Step 8: Commit**

```bash
git add core/domains/filmium/torrents core/domains/filmium/migration_v32.py core/domains/filmium/migrations.py tests/test_filmium_torrent_migration.py
git commit -m "feat(filmium): modeli i migracija V32 za torrent modul"
```

---

### Task 2: Repozitorijum i podešavanja

**Files:**
- Create: `core/domains/filmium/torrents/torrent_repository.py`
- Create: `core/domains/filmium/torrents/torrent_settings.py`
- Modify: `core/domains/filmium/torrents/__init__.py` (dodati izvoze)
- Test: `tests/test_filmium_torrent_settings.py`

**Interfaces:**
- Consumes: modeli iz Taska 1, `core.database.core_database_connection`
- Produces:
  - `TorrentRepository(database_path: Path | None = None)` sa metodama
    `upsert(entry: TorrentEntry) -> TorrentEntry`,
    `get(info_hash: str) -> TorrentEntry | None`,
    `list(status: TorrentStatus | None = None) -> list[TorrentEntry]`,
    `update_status(info_hash: str, status: TorrentStatus, *, error_message: str | None = None, completed_at: datetime | None = None) -> None`,
    `replace_files(info_hash: str, files: list[TorrentFileEntry]) -> None`,
    `list_files(info_hash: str) -> list[TorrentFileEntry]`,
    `set_selected(info_hash: str, selected_indexes: list[int]) -> None`,
    `delete(info_hash: str) -> None`
  - `TorrentSettingsStore(database_path: Path | None = None)` sa `load() -> TorrentSettings` i `save(settings: TorrentSettings) -> TorrentSettings`

- [ ] **Step 1: Write the failing test**

`tests/test_filmium_torrent_settings.py`:

```python
# ========== TESTOVI: TORRENT REPOZITORIJUM I PODEŠAVANJA ==========
from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest

from core.database.runtime import initialize_core_database
from core.domains.filmium.torrents.torrent_models import (
    TorrentEntry,
    TorrentFileEntry,
    TorrentSettings,
    TorrentStatus,
)
from core.domains.filmium.torrents.torrent_repository import TorrentRepository
from core.domains.filmium.torrents.torrent_settings import TorrentSettingsStore


@pytest.fixture
def database_path(tmp_path: Path) -> Path:
    path = tmp_path / "torrents.db"
    initialize_core_database(path)
    return path


def _entry(info_hash: str = "abc123") -> TorrentEntry:
    return TorrentEntry(
        info_hash=info_hash,
        name="Dune (2021)",
        source="magnet:?xt=urn:btih:abc123",
        source_kind="magnet",
        status=TorrentStatus.METADATA_FETCHING,
        save_path=r"F:\Preuzimanja",
        total_bytes=0,
        added_at=datetime(2026, 9, 11, 12, 0, 0),
    )


def test_upsert_and_get_roundtrip(database_path: Path) -> None:
    repository = TorrentRepository(database_path)

    repository.upsert(_entry())
    stored = repository.get("abc123")

    assert stored is not None
    assert stored.name == "Dune (2021)"
    assert stored.status is TorrentStatus.METADATA_FETCHING
    assert stored.added_at == datetime(2026, 9, 11, 12, 0, 0)


def test_upsert_twice_updates_instead_of_duplicating(database_path: Path) -> None:
    repository = TorrentRepository(database_path)

    repository.upsert(_entry())
    updated = _entry()
    updated.name = "Dune Part Two"
    repository.upsert(updated)

    assert len(repository.list()) == 1
    stored = repository.get("abc123")
    assert stored is not None
    assert stored.name == "Dune Part Two"


def test_list_filters_by_status(database_path: Path) -> None:
    repository = TorrentRepository(database_path)
    first = _entry("aaa")
    second = _entry("bbb")
    second.status = TorrentStatus.DOWNLOADING
    repository.upsert(first)
    repository.upsert(second)

    downloading = repository.list(TorrentStatus.DOWNLOADING)

    assert [item.info_hash for item in downloading] == ["bbb"]


def test_update_status_writes_error_and_completed_at(database_path: Path) -> None:
    repository = TorrentRepository(database_path)
    repository.upsert(_entry())

    repository.update_status(
        "abc123",
        TorrentStatus.ERROR,
        error_message="Nema mesta na disku",
    )

    stored = repository.get("abc123")
    assert stored is not None
    assert stored.status is TorrentStatus.ERROR
    assert stored.error_message == "Nema mesta na disku"


def test_replace_files_then_set_selected(database_path: Path) -> None:
    repository = TorrentRepository(database_path)
    repository.upsert(_entry())
    repository.replace_files(
        "abc123",
        [
            TorrentFileEntry(file_index=0, path="Dune.mkv", size_bytes=900),
            TorrentFileEntry(file_index=1, path="Dune.nfo", size_bytes=2),
        ],
    )

    repository.set_selected("abc123", [0])

    files = repository.list_files("abc123")
    assert [(f.file_index, f.selected) for f in files] == [(0, True), (1, False)]


def test_delete_removes_torrent_and_its_files(database_path: Path) -> None:
    repository = TorrentRepository(database_path)
    repository.upsert(_entry())
    repository.replace_files(
        "abc123",
        [TorrentFileEntry(file_index=0, path="Dune.mkv", size_bytes=900)],
    )

    repository.delete("abc123")

    assert repository.get("abc123") is None
    assert repository.list_files("abc123") == []


def test_settings_defaults(database_path: Path) -> None:
    store = TorrentSettingsStore(database_path)

    settings = store.load()

    assert settings.host == "127.0.0.1"
    assert settings.port == 8080
    assert settings.max_active == 3
    assert settings.auto_start is True
    assert settings.seed_after_complete is False
    assert settings.unselected_extensions == (
        ".nfo", ".txt", ".url", ".jpg", ".png", ".sfv",
    )


def test_settings_save_roundtrip(database_path: Path) -> None:
    store = TorrentSettingsStore(database_path)

    store.save(
        TorrentSettings(
            host="192.168.0.10",
            port=9090,
            watch_folder=r"C:\Preuzimanja",
            download_path=r"F:\Filmovi",
            max_download_kbs=2048,
            max_active=1,
            auto_start=False,
            unselected_extensions=(".nfo", ".sample"),
        )
    )
    settings = store.load()

    assert settings.host == "192.168.0.10"
    assert settings.port == 9090
    assert settings.watch_folder == r"C:\Preuzimanja"
    assert settings.max_download_kbs == 2048
    assert settings.auto_start is False
    assert settings.unselected_extensions == (".nfo", ".sample")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_filmium_torrent_settings.py -v`
Expected: FAIL sa `ModuleNotFoundError: No module named 'core.domains.filmium.torrents.torrent_repository'`

- [ ] **Step 3: Write the repository**

`core/domains/filmium/torrents/torrent_repository.py`:

```python
# ========== TORRENT REPOZITORIJUM ==========
# CRUD za torrente i njihove fajlove (CORE SQLite baza).
from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path

from core.database import core_database_connection
from core.domains.filmium.torrents.torrent_models import (
    TorrentEntry,
    TorrentFileEntry,
    TorrentStatus,
)


def _to_datetime(raw: str | None) -> datetime | None:
    return datetime.fromisoformat(raw) if raw else None


# ========== REPOSITORY ==========
class TorrentRepository:
    """Perzistencija torrenta koje je FILMIUM dodao i njihovih fajlova."""

    def __init__(self, database_path: Path | None = None) -> None:
        self._database_path = database_path

    def _conn(self):
        return core_database_connection(self._database_path)

    # ---------- torrenti ----------
    def upsert(self, entry: TorrentEntry) -> TorrentEntry:
        with self._conn() as c:
            c.execute(
                """
                INSERT INTO filmium_torrents (
                    info_hash, name, source, source_kind, status,
                    save_path, total_bytes, added_at, completed_at, error_message
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(info_hash) DO UPDATE SET
                    name = excluded.name,
                    source = excluded.source,
                    source_kind = excluded.source_kind,
                    status = excluded.status,
                    save_path = excluded.save_path,
                    total_bytes = excluded.total_bytes,
                    completed_at = excluded.completed_at,
                    error_message = excluded.error_message
                """,
                (
                    entry.info_hash,
                    entry.name,
                    entry.source,
                    entry.source_kind,
                    entry.status.value,
                    entry.save_path,
                    int(entry.total_bytes),
                    entry.added_at.isoformat(),
                    entry.completed_at.isoformat() if entry.completed_at else None,
                    entry.error_message,
                ),
            )
        return entry

    def get(self, info_hash: str) -> TorrentEntry | None:
        with self._conn() as c:
            row = c.execute(
                "SELECT * FROM filmium_torrents WHERE info_hash = ?",
                (info_hash,),
            ).fetchone()
        return self._from_row(row) if row else None

    def list(self, status: TorrentStatus | None = None) -> list[TorrentEntry]:
        query = "SELECT * FROM filmium_torrents"
        params: tuple = ()
        if status is not None:
            query += " WHERE status = ?"
            params = (status.value,)
        query += " ORDER BY added_at DESC"

        with self._conn() as c:
            rows = c.execute(query, params).fetchall()
        return [self._from_row(row) for row in rows]

    def update_status(
        self,
        info_hash: str,
        status: TorrentStatus,
        *,
        error_message: str | None = None,
        completed_at: datetime | None = None,
    ) -> None:
        with self._conn() as c:
            c.execute(
                """
                UPDATE filmium_torrents
                SET status = ?, error_message = ?, completed_at = ?
                WHERE info_hash = ?
                """,
                (
                    status.value,
                    error_message,
                    completed_at.isoformat() if completed_at else None,
                    info_hash,
                ),
            )

    def delete(self, info_hash: str) -> None:
        with self._conn() as c:
            c.execute(
                "DELETE FROM filmium_torrent_files WHERE info_hash = ?",
                (info_hash,),
            )
            c.execute(
                "DELETE FROM filmium_torrents WHERE info_hash = ?",
                (info_hash,),
            )

    # ---------- fajlovi ----------
    def replace_files(
        self,
        info_hash: str,
        files: list[TorrentFileEntry],
    ) -> None:
        with self._conn() as c:
            c.execute(
                "DELETE FROM filmium_torrent_files WHERE info_hash = ?",
                (info_hash,),
            )
            c.executemany(
                """
                INSERT INTO filmium_torrent_files (
                    info_hash, file_index, path, size_bytes, selected
                ) VALUES (?, ?, ?, ?, ?)
                """,
                [
                    (
                        info_hash,
                        item.file_index,
                        item.path,
                        int(item.size_bytes),
                        int(item.selected),
                    )
                    for item in files
                ],
            )

    def list_files(self, info_hash: str) -> list[TorrentFileEntry]:
        with self._conn() as c:
            rows = c.execute(
                """
                SELECT file_index, path, size_bytes, selected
                FROM filmium_torrent_files
                WHERE info_hash = ?
                ORDER BY file_index
                """,
                (info_hash,),
            ).fetchall()
        return [
            TorrentFileEntry(
                file_index=int(row[0]),
                path=str(row[1]),
                size_bytes=int(row[2]),
                selected=bool(row[3]),
            )
            for row in rows
        ]

    def set_selected(self, info_hash: str, selected_indexes: list[int]) -> None:
        wanted = set(selected_indexes)
        with self._conn() as c:
            rows = c.execute(
                "SELECT file_index FROM filmium_torrent_files WHERE info_hash = ?",
                (info_hash,),
            ).fetchall()
            c.executemany(
                """
                UPDATE filmium_torrent_files
                SET selected = ?
                WHERE info_hash = ? AND file_index = ?
                """,
                [
                    (int(int(row[0]) in wanted), info_hash, int(row[0]))
                    for row in rows
                ],
            )

    # ---------- mapiranje ----------
    @staticmethod
    def _from_row(row: sqlite3.Row) -> TorrentEntry:
        return TorrentEntry(
            info_hash=str(row["info_hash"]),
            name=str(row["name"]),
            source=str(row["source"]),
            source_kind=str(row["source_kind"]),
            status=TorrentStatus(str(row["status"])),
            save_path=str(row["save_path"]),
            total_bytes=int(row["total_bytes"]),
            added_at=_to_datetime(row["added_at"]) or datetime.now(),
            completed_at=_to_datetime(row["completed_at"]),
            error_message=row["error_message"],
        )
```

Napomena: `core_database_connection` vraća konekciju sa `sqlite3.Row` fabrikom, isto kao u `library_root_repository.py`. Ako se u toku rada pokaže da nije tako, postaviti `connection.row_factory = sqlite3.Row` u `_conn`.

- [ ] **Step 4: Write the settings store**

`core/domains/filmium/torrents/torrent_settings.py`:

```python
# ========== PODEŠAVANJA TORRENT MODULA ==========
# Jedan red u bazi (id = 1). Backend ih čita i kada GUI nije otvoren.
from __future__ import annotations

from pathlib import Path

from core.database import core_database_connection
from core.domains.filmium.torrents.torrent_models import (
    DEFAULT_UNSELECTED_EXTENSIONS,
    TorrentSettings,
)


def _split_extensions(raw: str) -> tuple[str, ...]:
    parts = [part.strip() for part in raw.split(",")]
    return tuple(part for part in parts if part) or DEFAULT_UNSELECTED_EXTENSIONS


# ========== STORE ==========
class TorrentSettingsStore:
    """Čita i upisuje podešavanja torrent modula."""

    def __init__(self, database_path: Path | None = None) -> None:
        self._database_path = database_path

    def _conn(self):
        return core_database_connection(self._database_path)

    def load(self) -> TorrentSettings:
        with self._conn() as c:
            row = c.execute(
                "SELECT * FROM filmium_torrent_settings WHERE id = 1"
            ).fetchone()

        if row is None:
            return TorrentSettings()

        return TorrentSettings(
            host=str(row["host"]),
            port=int(row["port"]),
            username=str(row["username"]),
            password=str(row["password"]),
            watch_folder=str(row["watch_folder"]),
            download_path=str(row["download_path"]),
            max_download_kbs=int(row["max_download_kbs"]),
            max_upload_kbs=int(row["max_upload_kbs"]),
            max_active=int(row["max_active"]),
            auto_start=bool(row["auto_start"]),
            seed_after_complete=bool(row["seed_after_complete"]),
            delete_source_torrent=bool(row["delete_source_torrent"]),
            unselected_extensions=_split_extensions(
                str(row["unselected_extensions"])
            ),
        )

    def save(self, settings: TorrentSettings) -> TorrentSettings:
        with self._conn() as c:
            c.execute(
                """
                UPDATE filmium_torrent_settings SET
                    host = ?, port = ?, username = ?, password = ?,
                    watch_folder = ?, download_path = ?,
                    max_download_kbs = ?, max_upload_kbs = ?, max_active = ?,
                    auto_start = ?, seed_after_complete = ?,
                    delete_source_torrent = ?, unselected_extensions = ?
                WHERE id = 1
                """,
                (
                    settings.host,
                    int(settings.port),
                    settings.username,
                    settings.password,
                    settings.watch_folder,
                    settings.download_path,
                    int(settings.max_download_kbs),
                    int(settings.max_upload_kbs),
                    int(settings.max_active),
                    int(settings.auto_start),
                    int(settings.seed_after_complete),
                    int(settings.delete_source_torrent),
                    ",".join(settings.unselected_extensions),
                ),
            )
        return self.load()
```

- [ ] **Step 5: Extend the package exports**

U `core/domains/filmium/torrents/__init__.py` dodati:

```python
from core.domains.filmium.torrents.torrent_repository import TorrentRepository
from core.domains.filmium.torrents.torrent_settings import TorrentSettingsStore
```

i u `__all__` dodati `"TorrentRepository"` i `"TorrentSettingsStore"`.

- [ ] **Step 6: Run test to verify it passes**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_filmium_torrent_settings.py -v`
Expected: PASS, 8 testova

- [ ] **Step 7: Commit**

```bash
git add core/domains/filmium/torrents tests/test_filmium_torrent_settings.py
git commit -m "feat(filmium): repozitorijum i podesavanja torrent modula"
```

---

### Task 3: TorrentEngine protokol i qBittorrent implementacija

**Files:**
- Create: `core/domains/filmium/torrents/torrent_engine.py`
- Modify: `core/domains/filmium/torrents/__init__.py`
- Modify: `requirements.txt`
- Modify: `core/foundation/dependencies.py` (nova stavka u `CORE_DEPENDENCIES`)
- Test: `tests/test_filmium_torrent_engine.py`

**Interfaces:**
- Consumes: modeli iz Taska 1, `TorrentSettings`
- Produces:
  - `TorrentEngine` protokol sa metodama: `is_available()`, `add(source, *, save_path)`, `list_files(info_hash)`, `set_file_priorities(info_hash, priorities)`, `start(info_hash)`, `pause(info_hash)`, `resume(info_hash)`, `remove(info_hash, *, delete_files)`, `poll_status()`, `apply_limits(settings)`
  - `QbittorrentEngine(settings_provider: Callable[[], TorrentSettings], *, client_factory: Callable[..., object] | None = None)`
  - `TorrentEngineError` (izuzetak sa čitljivom porukom na srpskom)

- [ ] **Step 1: Write the failing test**

`tests/test_filmium_torrent_engine.py`:

```python
# ========== TESTOVI: QBITTORRENT ENGINE ==========
# Bez mreže i bez pokrenutog qBittorrent-a — klijent je lažan.
from __future__ import annotations

import pytest

from core.domains.filmium.torrents.torrent_engine import (
    QbittorrentEngine,
    TorrentEngineError,
)
from core.domains.filmium.torrents.torrent_models import (
    QBIT_CATEGORY,
    TorrentSettings,
)


class _FakeTorrentsApi:
    def __init__(self, parent: "_FakeClient") -> None:
        self._parent = parent

    def add(self, **kwargs):
        self._parent.add_calls.append(kwargs)
        return "Ok."

    def info(self, **kwargs):
        self._parent.info_calls.append(kwargs)
        return self._parent.rows

    def files(self, torrent_hash: str):
        return self._parent.files_by_hash.get(torrent_hash, [])

    def file_priority(self, torrent_hash: str, file_ids, priority: int):
        self._parent.priority_calls.append((torrent_hash, list(file_ids), priority))

    def resume(self, torrent_hashes):
        self._parent.resumed.append(torrent_hashes)

    def pause(self, torrent_hashes):
        self._parent.paused.append(torrent_hashes)

    def delete(self, torrent_hashes, delete_files: bool):
        self._parent.deleted.append((torrent_hashes, delete_files))


class _FakeTransfer:
    def __init__(self, parent: "_FakeClient") -> None:
        self._parent = parent

    def set_download_limit(self, limit: int):
        self._parent.download_limit = limit

    def set_upload_limit(self, limit: int):
        self._parent.upload_limit = limit


class _FakeApp:
    def __init__(self, parent: "_FakeClient") -> None:
        self._parent = parent
        self.version = "5.0.1"

    def set_preferences(self, prefs: dict):
        self._parent.preferences.update(prefs)


class _FakeClient:
    """Oblik koji kod zove: client.torrents / client.transfer / client.app."""

    def __init__(self, **_kwargs) -> None:
        self.rows: list[dict] = []
        self.files_by_hash: dict[str, list[dict]] = {}
        self.add_calls: list[dict] = []
        self.info_calls: list[dict] = []
        self.priority_calls: list[tuple] = []
        self.resumed: list = []
        self.paused: list = []
        self.deleted: list = []
        self.logged_in = False
        self.download_limit: int | None = None
        self.upload_limit: int | None = None
        self.preferences: dict = {}

        self.torrents = _FakeTorrentsApi(self)
        self.transfer = _FakeTransfer(self)
        self.app = _FakeApp(self)

    def auth_log_in(self):
        self.logged_in = True


def _settings() -> TorrentSettings:
    return TorrentSettings(download_path=r"F:\Preuzimanja")


def _engine(client: _FakeClient) -> QbittorrentEngine:
    return QbittorrentEngine(lambda: _settings(), client_factory=lambda **_: client)


def test_is_available_true_when_login_succeeds() -> None:
    client = _FakeClient()

    health = _engine(client).is_available()

    assert health.available is True
    assert health.version == "5.0.1"


def test_is_available_false_with_message_when_client_raises() -> None:
    def _factory(**_kwargs):
        raise OSError("veza odbijena")

    engine = QbittorrentEngine(lambda: _settings(), client_factory=_factory)

    health = engine.is_available()

    assert health.available is False
    assert "127.0.0.1:8080" in (health.message or "")


def test_add_sends_paused_torrent_into_filmium_category() -> None:
    client = _FakeClient()
    client.rows = []

    engine = _engine(client)
    engine.add("magnet:?xt=urn:btih:abc123", save_path=r"F:\Preuzimanja")

    call = client.add_calls[0]
    assert call["category"] == QBIT_CATEGORY
    assert call["is_paused"] is True
    assert call["save_path"] == r"F:\Preuzimanja"


def test_add_rejects_empty_source() -> None:
    engine = _engine(_FakeClient())

    with pytest.raises(TorrentEngineError):
        engine.add("   ", save_path=r"F:\Preuzimanja")


def test_set_file_priorities_groups_by_priority() -> None:
    client = _FakeClient()
    engine = _engine(client)

    engine.set_file_priorities("abc123", {0: 1, 1: 0, 2: 0})

    grouped = {priority: files for _hash, files, priority in client.priority_calls}
    assert sorted(grouped[0]) == [1, 2]
    assert grouped[1] == [0]


def test_poll_status_maps_qbittorrent_rows() -> None:
    client = _FakeClient()
    client.rows = [
        {
            "hash": "abc123",
            "progress": 0.42,
            "dlspeed": 1024,
            "upspeed": 64,
            "eta": 120,
            "num_seeds": 5,
            "num_leechs": 2,
            "state": "downloading",
        }
    ]
    engine = _engine(client)

    progress = engine.poll_status()

    assert len(progress) == 1
    assert progress[0].info_hash == "abc123"
    assert progress[0].progress == pytest.approx(0.42)
    assert progress[0].download_rate == 1024
    assert progress[0].eta_seconds == 120
    assert progress[0].is_finished is False
    assert progress[0].is_paused is False


def test_poll_status_marks_finished_and_paused_states() -> None:
    client = _FakeClient()
    client.rows = [
        {"hash": "a", "progress": 1.0, "state": "pausedUP"},
        {"hash": "b", "progress": 0.5, "state": "pausedDL"},
    ]
    engine = _engine(client)

    by_hash = {item.info_hash: item for item in engine.poll_status()}

    assert by_hash["a"].is_finished is True
    assert by_hash["b"].is_paused is True
    assert by_hash["b"].is_finished is False


def test_poll_status_only_asks_for_filmium_category() -> None:
    client = _FakeClient()
    client.rows = []
    engine = _engine(client)

    engine.poll_status()

    assert client.info_calls[0]["category"] == QBIT_CATEGORY


def test_apply_limits_converts_kilobytes_to_bytes() -> None:
    client = _FakeClient()
    engine = _engine(client)

    engine.apply_limits(TorrentSettings(max_download_kbs=2048, max_upload_kbs=512, max_active=2))

    assert client.download_limit == 2048 * 1024
    assert client.upload_limit == 512 * 1024
    assert client.preferences["max_active_downloads"] == 2
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_filmium_torrent_engine.py -v`
Expected: FAIL sa `ModuleNotFoundError: No module named 'core.domains.filmium.torrents.torrent_engine'`

- [ ] **Step 3: Write the engine**

`core/domains/filmium/torrents/torrent_engine.py`:

```python
# ========== TORRENT ENGINE (qBittorrent Web API) ==========
# Jedini modul koji zna za qBittorrent. Uvoz `qbittorrentapi` je LENJ, pa
# CORE radi i kada paket nije instaliran — modul tada prijavi da nije spreman.
#
# Svi pozivi idu nad kategorijom FILMIUM: torrenti koje je korisnik ručno
# pustio u qBittorrent-u ostaju nevidljivi i netaknuti.
from __future__ import annotations

import os
from collections.abc import Callable
from typing import Any, Protocol

from core.domains.filmium.torrents.torrent_models import (
    QBIT_CATEGORY,
    EngineHealth,
    TorrentFileEntry,
    TorrentMetadata,
    TorrentProgress,
    TorrentSettings,
)

# qBittorrent stanja koja znače „gotovo" i „pauzirano".
_FINISHED_STATES = {
    "uploading", "stalledUP", "pausedUP", "queuedUP", "forcedUP", "checkingUP",
}
_PAUSED_STATES = {"pausedDL", "pausedUP"}


class TorrentEngineError(RuntimeError):
    """Greška u komunikaciji sa torrent klijentom, sa porukom za korisnika."""


# ========== PROTOKOL ==========
class TorrentEngine(Protocol):
    def is_available(self) -> EngineHealth: ...

    def add(self, source: str, *, save_path: str) -> TorrentMetadata: ...

    def list_files(self, info_hash: str) -> list[TorrentFileEntry]: ...

    def set_file_priorities(
        self, info_hash: str, priorities: dict[int, int]
    ) -> None: ...

    def start(self, info_hash: str) -> None: ...

    def pause(self, info_hash: str) -> None: ...

    def resume(self, info_hash: str) -> None: ...

    def remove(self, info_hash: str, *, delete_files: bool) -> None: ...

    def poll_status(self) -> list[TorrentProgress]: ...

    def apply_limits(self, settings: TorrentSettings) -> None: ...


def _default_client_factory(**kwargs: Any) -> Any:
    # Lenji uvoz: bez instaliranog paketa modul samo nije dostupan.
    import qbittorrentapi  # noqa: PLC0415

    return qbittorrentapi.Client(**kwargs)


def _magnet_hash(source: str) -> str | None:
    marker = "urn:btih:"
    if marker not in source:
        return None
    rest = source.split(marker, 1)[1]
    return rest.split("&", 1)[0].lower() or None


# ========== IMPLEMENTACIJA ==========
class QbittorrentEngine:
    """TorrentEngine nad qBittorrent Web API-jem."""

    def __init__(
        self,
        settings_provider: Callable[[], TorrentSettings],
        *,
        client_factory: Callable[..., Any] | None = None,
    ) -> None:
        self._settings_provider = settings_provider
        self._client_factory = client_factory or _default_client_factory

    # ---------- veza ----------
    def _client(self) -> Any:
        settings = self._settings_provider()
        try:
            client = self._client_factory(
                host=settings.host,
                port=settings.port,
                username=settings.username or None,
                password=settings.password or None,
            )
            client.auth_log_in()
            return client
        except Exception as error:  # noqa: BLE001 — poruka ide korisniku
            raise TorrentEngineError(
                f"qBittorrent nije dostupan na {settings.host}:{settings.port} "
                f"({error})."
            ) from error

    def is_available(self) -> EngineHealth:
        try:
            client = self._client()
            return EngineHealth(available=True, version=str(client.app.version))
        except TorrentEngineError as error:
            return EngineHealth(available=False, message=str(error))
        except ImportError:
            return EngineHealth(
                available=False,
                message=(
                    "Paket qbittorrent-api nije instaliran "
                    "(python -m pip install qbittorrent-api)."
                ),
            )

    # ---------- dodavanje ----------
    def add(self, source: str, *, save_path: str) -> TorrentMetadata:
        cleaned = source.strip()
        if not cleaned:
            raise TorrentEngineError("Prazan magnet link ili putanja do .torrent fajla.")

        client = self._client()
        payload: dict[str, Any] = {
            "category": QBIT_CATEGORY,
            "is_paused": True,
            "save_path": save_path,
        }

        if cleaned.lower().startswith("magnet:"):
            payload["urls"] = cleaned
            info_hash = _magnet_hash(cleaned)
        else:
            if not os.path.isfile(cleaned):
                raise TorrentEngineError(f"Torrent fajl ne postoji: {cleaned}")
            payload["torrent_files"] = cleaned
            info_hash = None

        result = client.torrents.add(**payload)
        if isinstance(result, str) and result.strip().lower() not in {"ok.", "ok"}:
            raise TorrentEngineError(f"qBittorrent je odbio torrent: {result}")

        if info_hash is None:
            info_hash = self._latest_hash(client)

        if not info_hash:
            raise TorrentEngineError(
                "Torrent je dodat, ali qBittorrent nije vratio info hash."
            )

        return TorrentMetadata(
            info_hash=info_hash,
            name=cleaned,
            has_metadata=False,
        )

    def _latest_hash(self, client: Any) -> str | None:
        rows = client.torrents.info(category=QBIT_CATEGORY, sort="added_on", reverse=True)
        for row in rows:
            return str(row["hash"]).lower()
        return None

    # ---------- fajlovi ----------
    def list_files(self, info_hash: str) -> list[TorrentFileEntry]:
        client = self._client()
        rows = client.torrents.files(torrent_hash=info_hash)
        return [
            TorrentFileEntry(
                file_index=int(row.get("index", position)),
                path=str(row["name"]),
                size_bytes=int(row.get("size", 0)),
                selected=int(row.get("priority", 1)) > 0,
            )
            for position, row in enumerate(rows)
        ]

    def set_file_priorities(
        self,
        info_hash: str,
        priorities: dict[int, int],
    ) -> None:
        grouped: dict[int, list[int]] = {}
        for file_index, priority in priorities.items():
            grouped.setdefault(int(priority), []).append(int(file_index))

        client = self._client()
        for priority, file_ids in grouped.items():
            client.torrents.file_priority(
                torrent_hash=info_hash,
                file_ids=sorted(file_ids),
                priority=priority,
            )

    # ---------- kontrola ----------
    def start(self, info_hash: str) -> None:
        self.resume(info_hash)

    def resume(self, info_hash: str) -> None:
        self._client().torrents.resume(torrent_hashes=info_hash)

    def pause(self, info_hash: str) -> None:
        self._client().torrents.pause(torrent_hashes=info_hash)

    def remove(self, info_hash: str, *, delete_files: bool) -> None:
        self._client().torrents.delete(
            torrent_hashes=info_hash,
            delete_files=delete_files,
        )

    # ---------- status ----------
    def poll_status(self) -> list[TorrentProgress]:
        client = self._client()
        rows = client.torrents.info(category=QBIT_CATEGORY)

        progress: list[TorrentProgress] = []
        for row in rows:
            state = str(row.get("state", ""))
            eta = row.get("eta")
            progress.append(
                TorrentProgress(
                    info_hash=str(row["hash"]).lower(),
                    progress=float(row.get("progress", 0.0)),
                    download_rate=int(row.get("dlspeed", 0)),
                    upload_rate=int(row.get("upspeed", 0)),
                    eta_seconds=int(eta) if eta not in (None, 8640000) else None,
                    seeds=int(row.get("num_seeds", 0)),
                    peers=int(row.get("num_leechs", 0)),
                    is_finished=state in _FINISHED_STATES
                    or float(row.get("progress", 0.0)) >= 1.0,
                    is_paused=state in _PAUSED_STATES,
                    error_message="Greška u torrent klijentu."
                    if state == "error"
                    else None,
                )
            )
        return progress

    # ---------- ograničenja ----------
    def apply_limits(self, settings: TorrentSettings) -> None:
        client = self._client()
        client.transfer.set_download_limit(int(settings.max_download_kbs) * 1024)
        client.transfer.set_upload_limit(int(settings.max_upload_kbs) * 1024)
        client.app.set_preferences(
            {"max_active_downloads": int(settings.max_active)}
        )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_filmium_torrent_engine.py -v`
Expected: PASS, 9 testova

Ako lažni klijent iz testa ne odgovara oblicima koje kod zove (npr. `client.torrents.info` vs `client.torrents_api.info`), ispraviti **test dvojnik**, a ne pravi kod — pravi oblik je onaj iz `qbittorrent-api` dokumentacije: `client.torrents.add(...)`, `client.torrents.info(...)`, `client.torrents.files(...)`, `client.torrents.file_priority(...)`, `client.torrents.resume/pause/delete(...)`, `client.transfer.set_download_limit(...)`, `client.app.set_preferences(...)`, `client.app.version`.

- [ ] **Step 5: Register the dependency**

U `requirements.txt`, ispod `psutil`:

```
qbittorrent-api
```

U `core/foundation/dependencies.py`, u torku `CORE_DEPENDENCIES`, odmah posle stavke `watchdog`:

```python
    Dependency(
        key="qbittorrent-api",
        label="qbittorrent-api",
        kind=DependencyKind.PYTHON,
        severity=DependencySeverity.OPTIONAL,
        probe="qbittorrentapi",
        purpose="Torrent modul FILMIUM-a (veza sa qBittorrent Web UI-jem).",
        install_hint="python -m pip install qbittorrent-api",
    ),
```

- [ ] **Step 6: Install and verify the import name**

Run: `./.venv/Scripts/python.exe -m pip install qbittorrent-api`
Run: `./.venv/Scripts/python.exe -c "import qbittorrentapi; print(qbittorrentapi.__name__)"`
Expected: ispisuje `qbittorrentapi`

- [ ] **Step 7: Extend the package exports**

U `core/domains/filmium/torrents/__init__.py` dodati:

```python
from core.domains.filmium.torrents.torrent_engine import (
    QbittorrentEngine,
    TorrentEngine,
    TorrentEngineError,
)
```

i u `__all__` dodati `"QbittorrentEngine"`, `"TorrentEngine"`, `"TorrentEngineError"`.

- [ ] **Step 8: Commit**

```bash
git add core/domains/filmium/torrents requirements.txt core/foundation/dependencies.py tests/test_filmium_torrent_engine.py
git commit -m "feat(filmium): qBittorrent engine iza TorrentEngine protokola"
```

---

### Task 4: Poslovna logika (`torrent_service.py`)

**Files:**
- Create: `core/domains/filmium/torrents/torrent_service.py`
- Modify: `core/domains/filmium/torrents/__init__.py`
- Test: `tests/test_filmium_torrent_service.py`

**Interfaces:**
- Consumes: `TorrentRepository`, `TorrentSettingsStore`, `TorrentEngine`, modeli iz Taska 1
- Produces: `TorrentService` sa javnim metodama:
  - `health() -> EngineHealth`
  - `add(source: str) -> TorrentEntry`
  - `list(status: TorrentStatus | None = None) -> list[TorrentEntry]`
  - `files(info_hash: str) -> list[TorrentFileEntry]`
  - `approve(info_hash: str, selected_indexes: list[int]) -> TorrentEntry`
  - `pause(info_hash: str) -> TorrentEntry`
  - `resume(info_hash: str) -> TorrentEntry`
  - `remove(info_hash: str, *, delete_files: bool = False) -> None`
  - `poll() -> list[TorrentProgress]`
  - `reconcile() -> int`
  - `settings() -> TorrentSettings`, `save_settings(settings: TorrentSettings) -> TorrentSettings`
  - `TorrentServiceError(ValueError)`

- [ ] **Step 1: Write the failing test**

`tests/test_filmium_torrent_service.py`:

```python
# ========== TESTOVI: TORRENT SERVIS ==========
from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

import pytest

from core.database.runtime import initialize_core_database
from core.domains.filmium.torrents.torrent_models import (
    EngineHealth,
    TorrentFileEntry,
    TorrentMetadata,
    TorrentProgress,
    TorrentSettings,
    TorrentStatus,
)
from core.domains.filmium.torrents.torrent_repository import TorrentRepository
from core.domains.filmium.torrents.torrent_service import (
    TorrentService,
    TorrentServiceError,
)
from core.domains.filmium.torrents.torrent_settings import TorrentSettingsStore


class _FakeEngine:
    """TorrentEngine dvojnik — pamti pozive, ne dodiruje mrežu."""

    def __init__(self) -> None:
        self.health = EngineHealth(available=True, version="5.0.1")
        self.files: list[TorrentFileEntry] = []
        self.progress: list[TorrentProgress] = []
        self.priority_calls: list[tuple[str, dict[int, int]]] = []
        self.started: list[str] = []
        self.paused: list[str] = []
        self.resumed: list[str] = []
        self.removed: list[tuple[str, bool]] = []
        self.limits: list[TorrentSettings] = []

    def is_available(self) -> EngineHealth:
        return self.health

    def add(self, source: str, *, save_path: str) -> TorrentMetadata:
        return TorrentMetadata(info_hash="abc123", name=source, has_metadata=False)

    def list_files(self, info_hash: str) -> list[TorrentFileEntry]:
        return list(self.files)

    def set_file_priorities(self, info_hash: str, priorities: dict[int, int]) -> None:
        self.priority_calls.append((info_hash, dict(priorities)))

    def start(self, info_hash: str) -> None:
        self.started.append(info_hash)

    def pause(self, info_hash: str) -> None:
        self.paused.append(info_hash)

    def resume(self, info_hash: str) -> None:
        self.resumed.append(info_hash)

    def remove(self, info_hash: str, *, delete_files: bool) -> None:
        self.removed.append((info_hash, delete_files))

    def poll_status(self) -> list[TorrentProgress]:
        return list(self.progress)

    def apply_limits(self, settings: TorrentSettings) -> None:
        self.limits.append(settings)


@pytest.fixture
def parts(tmp_path: Path):
    database_path = tmp_path / "torrents.db"
    initialize_core_database(database_path)

    repository = TorrentRepository(database_path)
    settings_store = TorrentSettingsStore(database_path)
    settings_store.save(
        TorrentSettings(download_path=str(tmp_path / "preuzimanja"))
    )
    engine = _FakeEngine()
    completed: list[tuple[str, str]] = []
    notices: list[tuple[str, str]] = []

    service = TorrentService(
        repository,
        engine,
        settings_store,
        on_completed=lambda entry: completed.append((entry.info_hash, entry.save_path)),
        notify=lambda title, message: notices.append((title, message)),
    )
    return service, repository, engine, completed, notices


def test_add_stores_entry_awaiting_metadata(parts) -> None:
    service, repository, _engine, _completed, _notices = parts

    entry = service.add("magnet:?xt=urn:btih:abc123")

    assert entry.status is TorrentStatus.METADATA_FETCHING
    assert entry.source_kind == "magnet"
    assert repository.get("abc123") is not None


def test_add_without_download_path_is_rejected(tmp_path: Path) -> None:
    database_path = tmp_path / "torrents.db"
    initialize_core_database(database_path)
    service = TorrentService(
        TorrentRepository(database_path),
        _FakeEngine(),
        TorrentSettingsStore(database_path),
    )

    with pytest.raises(TorrentServiceError):
        service.add("magnet:?xt=urn:btih:abc123")


def test_poll_promotes_to_awaiting_approval_when_files_arrive(parts) -> None:
    service, repository, engine, _completed, notices = parts
    service.add("magnet:?xt=urn:btih:abc123")
    engine.files = [
        TorrentFileEntry(file_index=0, path="Dune.mkv", size_bytes=900),
        TorrentFileEntry(file_index=1, path="Dune.nfo", size_bytes=2),
    ]
    engine.progress = [TorrentProgress(info_hash="abc123", progress=0.0)]

    service.poll()

    stored = repository.get("abc123")
    assert stored is not None
    assert stored.status is TorrentStatus.AWAITING_APPROVAL
    assert len(notices) == 1
    files = repository.list_files("abc123")
    assert [f.selected for f in files] == [True, False]  # .nfo je u filteru


def test_metadata_timeout_marks_error(parts) -> None:
    service, repository, engine, _completed, _notices = parts
    service.add("magnet:?xt=urn:btih:abc123")
    engine.files = []
    engine.progress = [TorrentProgress(info_hash="abc123", progress=0.0)]

    service.poll(now=datetime.now() + timedelta(seconds=61))

    stored = repository.get("abc123")
    assert stored is not None
    assert stored.status is TorrentStatus.ERROR
    assert "metapodat" in (stored.error_message or "").lower()


def test_approve_sets_zero_priority_on_unselected_files(parts) -> None:
    service, repository, engine, _completed, _notices = parts
    service.add("magnet:?xt=urn:btih:abc123")
    engine.files = [
        TorrentFileEntry(file_index=0, path="Dune.mkv", size_bytes=900),
        TorrentFileEntry(file_index=1, path="Dune.nfo", size_bytes=2),
        TorrentFileEntry(file_index=2, path="sample.mkv", size_bytes=5),
    ]
    engine.progress = [TorrentProgress(info_hash="abc123", progress=0.0)]
    service.poll()

    entry = service.approve("abc123", [0])

    assert entry.status is TorrentStatus.DOWNLOADING
    assert engine.priority_calls[0] == ("abc123", {0: 1, 1: 0, 2: 0})
    assert engine.started == ["abc123"]


def test_approve_requires_at_least_one_file(parts) -> None:
    service, _repository, engine, _completed, _notices = parts
    service.add("magnet:?xt=urn:btih:abc123")
    engine.files = [TorrentFileEntry(file_index=0, path="Dune.mkv", size_bytes=900)]
    engine.progress = [TorrentProgress(info_hash="abc123", progress=0.0)]
    service.poll()

    with pytest.raises(TorrentServiceError):
        service.approve("abc123", [])


def test_approve_without_auto_start_leaves_torrent_paused(parts, tmp_path: Path) -> None:
    service, repository, engine, _completed, _notices = parts
    service.save_settings(
        TorrentSettings(
            download_path=str(tmp_path / "preuzimanja"),
            auto_start=False,
        )
    )
    service.add("magnet:?xt=urn:btih:abc123")
    engine.files = [TorrentFileEntry(file_index=0, path="Dune.mkv", size_bytes=900)]
    engine.progress = [TorrentProgress(info_hash="abc123", progress=0.0)]
    service.poll()

    entry = service.approve("abc123", [0])

    assert entry.status is TorrentStatus.PAUSED
    assert engine.started == []


def test_poll_completes_and_hands_path_to_import(parts) -> None:
    service, repository, engine, completed, notices = parts
    service.add("magnet:?xt=urn:btih:abc123")
    engine.files = [TorrentFileEntry(file_index=0, path="Dune.mkv", size_bytes=900)]
    engine.progress = [TorrentProgress(info_hash="abc123", progress=0.0)]
    service.poll()
    service.approve("abc123", [0])

    engine.progress = [
        TorrentProgress(info_hash="abc123", progress=1.0, is_finished=True)
    ]
    service.poll()

    stored = repository.get("abc123")
    assert stored is not None
    assert stored.status is TorrentStatus.COMPLETED
    assert stored.completed_at is not None
    assert completed == [("abc123", stored.save_path)]
    assert any("spreman" in message.lower() for _title, message in notices)


def test_poll_fires_completion_only_once(parts) -> None:
    service, _repository, engine, completed, _notices = parts
    service.add("magnet:?xt=urn:btih:abc123")
    engine.files = [TorrentFileEntry(file_index=0, path="Dune.mkv", size_bytes=900)]
    engine.progress = [TorrentProgress(info_hash="abc123", progress=0.0)]
    service.poll()
    service.approve("abc123", [0])
    engine.progress = [
        TorrentProgress(info_hash="abc123", progress=1.0, is_finished=True)
    ]

    service.poll()
    service.poll()

    assert len(completed) == 1


def test_complete_pauses_when_seeding_is_off(parts) -> None:
    service, _repository, engine, _completed, _notices = parts
    service.add("magnet:?xt=urn:btih:abc123")
    engine.files = [TorrentFileEntry(file_index=0, path="Dune.mkv", size_bytes=900)]
    engine.progress = [TorrentProgress(info_hash="abc123", progress=0.0)]
    service.poll()
    service.approve("abc123", [0])

    engine.progress = [
        TorrentProgress(info_hash="abc123", progress=1.0, is_finished=True)
    ]
    service.poll()

    assert engine.paused == ["abc123"]


def test_complete_keeps_seeding_when_enabled(parts, tmp_path: Path) -> None:
    service, _repository, engine, _completed, _notices = parts
    service.save_settings(
        TorrentSettings(
            download_path=str(tmp_path / "preuzimanja"),
            seed_after_complete=True,
        )
    )
    service.add("magnet:?xt=urn:btih:abc123")
    engine.files = [TorrentFileEntry(file_index=0, path="Dune.mkv", size_bytes=900)]
    engine.progress = [TorrentProgress(info_hash="abc123", progress=0.0)]
    service.poll()
    service.approve("abc123", [0])

    engine.progress = [
        TorrentProgress(info_hash="abc123", progress=1.0, is_finished=True)
    ]
    service.poll()

    assert engine.paused == []


def test_reconcile_marks_torrents_missing_from_client(parts) -> None:
    service, repository, engine, _completed, _notices = parts
    service.add("magnet:?xt=urn:btih:abc123")
    engine.progress = []  # klijent više ne zna za ovaj torrent

    missing = service.reconcile()

    stored = repository.get("abc123")
    assert missing == 1
    assert stored is not None
    assert stored.status is TorrentStatus.ERROR


def test_reconcile_leaves_known_torrents_alone(parts) -> None:
    service, repository, engine, _completed, _notices = parts
    service.add("magnet:?xt=urn:btih:abc123")
    engine.progress = [TorrentProgress(info_hash="abc123", progress=0.0)]

    missing = service.reconcile()

    stored = repository.get("abc123")
    assert missing == 0
    assert stored is not None
    assert stored.status is TorrentStatus.METADATA_FETCHING


def test_remove_deletes_entry_and_calls_engine(parts) -> None:
    service, repository, engine, _completed, _notices = parts
    service.add("magnet:?xt=urn:btih:abc123")

    service.remove("abc123", delete_files=True)

    assert repository.get("abc123") is None
    assert engine.removed == [("abc123", True)]


def test_save_settings_applies_limits_to_engine(parts, tmp_path: Path) -> None:
    service, _repository, engine, _completed, _notices = parts

    service.save_settings(
        TorrentSettings(
            download_path=str(tmp_path / "preuzimanja"),
            max_download_kbs=1024,
        )
    )

    assert engine.limits[-1].max_download_kbs == 1024
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_filmium_torrent_service.py -v`
Expected: FAIL sa `ModuleNotFoundError: No module named 'core.domains.filmium.torrents.torrent_service'`

- [ ] **Step 3: Write the service**

`core/domains/filmium/torrents/torrent_service.py`:

```python
# ========== TORRENT SERVIS ==========
# Poslovna logika modula: dodavanje pauziranog torrenta, čekanje metapodataka,
# štikliranje fajlova, odobrenje, praćenje i predaja uvozu po završetku.
#
# Ovaj modul NE zna za qBittorrent — radi isključivo kroz TorrentEngine.
from __future__ import annotations

import os
from collections.abc import Callable
from datetime import datetime

from core.domains.filmium.torrents.torrent_engine import (
    TorrentEngine,
    TorrentEngineError,
)
from core.domains.filmium.torrents.torrent_models import (
    EngineHealth,
    TorrentEntry,
    TorrentFileEntry,
    TorrentProgress,
    TorrentSettings,
    TorrentStatus,
)
from core.domains.filmium.torrents.torrent_repository import TorrentRepository
from core.domains.filmium.torrents.torrent_settings import TorrentSettingsStore

# Koliko čekamo metapodatke magnet linka pre nego što odustanemo.
METADATA_TIMEOUT_SECONDS = 60

# qBittorrent prioriteti: 0 = ne skidaj, 1 = normalno.
PRIORITY_SKIP = 0
PRIORITY_NORMAL = 1


class TorrentServiceError(ValueError):
    """Neispravan zahtev korisnika (prazan izbor, nepoznat torrent, i slično)."""


def _is_magnet(source: str) -> bool:
    return source.strip().lower().startswith("magnet:")


# ========== SERVIS ==========
class TorrentService:
    """Životni ciklus torrenta koje je FILMIUM dodao."""

    def __init__(
        self,
        repository: TorrentRepository,
        engine: TorrentEngine,
        settings_store: TorrentSettingsStore,
        *,
        on_completed: Callable[[TorrentEntry], None] | None = None,
        notify: Callable[[str, str], None] | None = None,
    ) -> None:
        self._repository = repository
        self._engine = engine
        self._settings_store = settings_store
        self._on_completed = on_completed
        self._notify = notify or (lambda _title, _message: None)

    # ---------- zdravlje i podešavanja ----------
    def health(self) -> EngineHealth:
        return self._engine.is_available()

    def settings(self) -> TorrentSettings:
        return self._settings_store.load()

    def save_settings(self, settings: TorrentSettings) -> TorrentSettings:
        saved = self._settings_store.save(settings)
        try:
            self._engine.apply_limits(saved)
        except TorrentEngineError:
            pass  # klijent nije dostupan; ograničenja idu pri sledećem upisu
        return saved

    # ---------- dodavanje ----------
    def add(self, source: str) -> TorrentEntry:
        cleaned = source.strip()
        if not cleaned:
            raise TorrentServiceError("Unesi magnet link ili izaberi .torrent fajl.")

        settings = self.settings()
        if not settings.download_path:
            raise TorrentServiceError(
                "Odredište preuzimanja nije podešeno "
                "(FILMIUM podešavanja → Torrenti)."
            )
        os.makedirs(settings.download_path, exist_ok=True)

        try:
            metadata = self._engine.add(
                cleaned,
                save_path=settings.download_path,
            )
        except TorrentEngineError as error:
            raise TorrentServiceError(str(error)) from error

        entry = TorrentEntry(
            info_hash=metadata.info_hash,
            name=metadata.name,
            source=cleaned,
            source_kind="magnet" if _is_magnet(cleaned) else "file",
            status=TorrentStatus.METADATA_FETCHING,
            save_path=settings.download_path,
            total_bytes=metadata.total_bytes,
            added_at=datetime.now(),
        )
        self._repository.upsert(entry)

        if settings.delete_source_torrent and entry.source_kind == "file":
            try:
                os.remove(cleaned)
            except OSError:
                pass  # brisanje izvornog fajla nije razlog za pad

        return entry

    # ---------- čitanje ----------
    def list(self, status: TorrentStatus | None = None) -> list[TorrentEntry]:
        return self._repository.list(status)

    def files(self, info_hash: str) -> list[TorrentFileEntry]:
        self._require(info_hash)
        return self._repository.list_files(info_hash)

    # ---------- odobrenje ----------
    def approve(self, info_hash: str, selected_indexes: list[int]) -> TorrentEntry:
        entry = self._require(info_hash)
        if not selected_indexes:
            raise TorrentServiceError("Štikliraj bar jedan fajl pre odobrenja.")

        known = {item.file_index for item in self._repository.list_files(info_hash)}
        unknown = sorted(set(selected_indexes) - known)
        if unknown:
            raise TorrentServiceError(
                f"Nepoznati indeksi fajlova: {', '.join(str(i) for i in unknown)}."
            )

        self._repository.set_selected(info_hash, selected_indexes)
        priorities = {
            index: (
                PRIORITY_NORMAL if index in set(selected_indexes) else PRIORITY_SKIP
            )
            for index in sorted(known)
        }

        try:
            self._engine.set_file_priorities(info_hash, priorities)
        except TorrentEngineError as error:
            raise TorrentServiceError(str(error)) from error

        settings = self.settings()
        if settings.auto_start:
            self._engine.start(info_hash)
            status = TorrentStatus.DOWNLOADING
        else:
            status = TorrentStatus.PAUSED

        self._repository.update_status(info_hash, status)
        entry.status = status
        return entry

    # ---------- kontrola ----------
    def pause(self, info_hash: str) -> TorrentEntry:
        entry = self._require(info_hash)
        self._engine.pause(info_hash)
        self._repository.update_status(info_hash, TorrentStatus.PAUSED)
        entry.status = TorrentStatus.PAUSED
        return entry

    def resume(self, info_hash: str) -> TorrentEntry:
        entry = self._require(info_hash)
        self._engine.resume(info_hash)
        self._repository.update_status(info_hash, TorrentStatus.DOWNLOADING)
        entry.status = TorrentStatus.DOWNLOADING
        return entry

    def remove(self, info_hash: str, *, delete_files: bool = False) -> None:
        self._require(info_hash)
        try:
            self._engine.remove(info_hash, delete_files=delete_files)
        except TorrentEngineError:
            pass  # zapis brišemo i ako klijent trenutno nije dostupan
        self._repository.delete(info_hash)

    # ---------- anketa ----------
    def poll(self, *, now: datetime | None = None) -> list[TorrentProgress]:
        moment = now or datetime.now()

        try:
            progress = self._engine.poll_status()
        except TorrentEngineError:
            return []

        by_hash = {item.info_hash: item for item in progress}
        settings = self.settings()

        for entry in self._repository.list():
            item = by_hash.get(entry.info_hash)

            if entry.status is TorrentStatus.METADATA_FETCHING:
                self._advance_metadata(entry, moment, settings)
                continue

            if item is None:
                continue

            if item.error_message:
                self._repository.update_status(
                    entry.info_hash,
                    TorrentStatus.ERROR,
                    error_message=item.error_message,
                )
                continue

            if item.is_finished and entry.status is not TorrentStatus.COMPLETED:
                self._complete(entry, moment, settings)

        return progress

    def reconcile(self) -> int:
        """Usklađuje bazu sa onim što klijent prijavljuje za kategoriju.

        Torrenti koje je neko obrisao spolja prelaze u ERROR, da lista ne
        prikazuje preuzimanja kojih više nema. Vraća broj takvih zapisa.
        """

        try:
            known = {item.info_hash for item in self._engine.poll_status()}
        except TorrentEngineError:
            return 0

        active = {
            TorrentStatus.METADATA_FETCHING,
            TorrentStatus.AWAITING_APPROVAL,
            TorrentStatus.DOWNLOADING,
            TorrentStatus.PAUSED,
        }

        missing = 0
        for entry in self._repository.list():
            if entry.status in active and entry.info_hash not in known:
                self._repository.update_status(
                    entry.info_hash,
                    TorrentStatus.ERROR,
                    error_message="Torrent više ne postoji u qBittorrent-u.",
                )
                missing += 1

        return missing

    def _advance_metadata(
        self,
        entry: TorrentEntry,
        moment: datetime,
        settings: TorrentSettings,
    ) -> None:
        try:
            files = self._engine.list_files(entry.info_hash)
        except TorrentEngineError:
            files = []

        if files:
            prepared = [
                TorrentFileEntry(
                    file_index=item.file_index,
                    path=item.path,
                    size_bytes=item.size_bytes,
                    selected=not item.path.lower().endswith(
                        tuple(settings.unselected_extensions)
                    ),
                )
                for item in files
            ]
            self._repository.replace_files(entry.info_hash, prepared)
            self._repository.update_status(
                entry.info_hash,
                TorrentStatus.AWAITING_APPROVAL,
            )
            self._notify(
                "FILMIUM torrenti",
                f"„{entry.name}" čeka odobrenje: "
                f"{len(prepared)} fajlova spremno za izbor.",
            )
            return

        waited = (moment - entry.added_at).total_seconds()
        if waited > METADATA_TIMEOUT_SECONDS:
            self._repository.update_status(
                entry.info_hash,
                TorrentStatus.ERROR,
                error_message=(
                    "Metapodaci nisu stigli u roku od "
                    f"{METADATA_TIMEOUT_SECONDS} sekundi."
                ),
            )

    def _complete(
        self,
        entry: TorrentEntry,
        moment: datetime,
        settings: TorrentSettings,
    ) -> None:
        self._repository.update_status(
            entry.info_hash,
            TorrentStatus.COMPLETED,
            completed_at=moment,
        )
        entry.status = TorrentStatus.COMPLETED
        entry.completed_at = moment

        # Bez seed-ovanja torrent se zaustavlja čim je fajl na disku.
        if not settings.seed_after_complete:
            try:
                self._engine.pause(entry.info_hash)
            except TorrentEngineError:
                pass

        self._notify(
            "FILMIUM torrenti",
            f"„{entry.name}" je spreman. Putanja: {entry.save_path}",
        )

        if self._on_completed is not None:
            self._on_completed(entry)

    # ---------- pomoćno ----------
    def _require(self, info_hash: str) -> TorrentEntry:
        entry = self._repository.get(info_hash)
        if entry is None:
            raise TorrentServiceError(f"Torrent nije pronađen: {info_hash}")
        return entry
```

Napomena o navodnicima: u f-stringovima iznad koriste se srpski navodnici `„"`. Ako linter prijavi problem sa mešanjem navodnika, prebaciti tu poruku u pomoćnu promenljivu pre f-stringa.

- [ ] **Step 4: Run test to verify it passes**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_filmium_torrent_service.py -v`
Expected: PASS, 15 testova

- [ ] **Step 5: Extend the package exports**

U `core/domains/filmium/torrents/__init__.py` dodati:

```python
from core.domains.filmium.torrents.torrent_service import (
    TorrentService,
    TorrentServiceError,
)
```

i u `__all__` dodati `"TorrentService"` i `"TorrentServiceError"`.

- [ ] **Step 6: Commit**

```bash
git add core/domains/filmium/torrents tests/test_filmium_torrent_service.py
git commit -m "feat(filmium): poslovna logika torrent modula"
```

---

### Task 5: Nadzor foldera

**Files:**
- Create: `core/domains/filmium/torrents/torrent_watch_service.py`
- Modify: `core/domains/filmium/torrents/__init__.py`
- Test: `tests/test_filmium_torrent_watch.py`

**Interfaces:**
- Consumes: `TorrentService`, `core.system.file_monitor.FileMonitorService`, `FileEvent`, `FileEventType`
- Produces: `TorrentWatchService(service: TorrentService, file_monitor: FileMonitorService)` sa `start() -> bool`, `stop() -> None`, `handle_event(event: FileEvent) -> None`

- [ ] **Step 1: Write the failing test**

`tests/test_filmium_torrent_watch.py`:

```python
# ========== TESTOVI: NADZOR FOLDERA ZA .torrent FAJLOVE ==========
from __future__ import annotations

from pathlib import Path

import pytest

from core.database.runtime import initialize_core_database
from core.domains.filmium.torrents.torrent_models import (
    EngineHealth,
    TorrentFileEntry,
    TorrentMetadata,
    TorrentProgress,
    TorrentSettings,
    TorrentStatus,
)
from core.domains.filmium.torrents.torrent_repository import TorrentRepository
from core.domains.filmium.torrents.torrent_service import TorrentService
from core.domains.filmium.torrents.torrent_settings import TorrentSettingsStore
from core.domains.filmium.torrents.torrent_watch_service import TorrentWatchService
from core.system.file_monitor import FileMonitorService
from core.system.file_monitor.monitor_models import FileEvent, FileEventType

# Dvojnik engine-a. Ponavlja se po test fajlu — projekat nema deljene
# test pomoćnike (isti obrazac kao `_FakeObserver` u drugim testovima).
class _FakeEngine:
    def __init__(self) -> None:
        self.files: list[TorrentFileEntry] = []
        self.progress: list[TorrentProgress] = []
        self.priority_calls: list[tuple[str, dict[int, int]]] = []
        self.started: list[str] = []
        self.paused: list[str] = []
        self.resumed: list[str] = []
        self.removed: list[tuple[str, bool]] = []
        self.limits: list[TorrentSettings] = []

    def is_available(self) -> EngineHealth:
        return EngineHealth(available=True, version="5.0.1")

    def add(self, source: str, *, save_path: str) -> TorrentMetadata:
        return TorrentMetadata(info_hash="abc123", name=source)

    def list_files(self, info_hash: str) -> list[TorrentFileEntry]:
        return list(self.files)

    def set_file_priorities(self, info_hash: str, priorities: dict[int, int]) -> None:
        self.priority_calls.append((info_hash, dict(priorities)))

    def start(self, info_hash: str) -> None:
        self.started.append(info_hash)

    def pause(self, info_hash: str) -> None:
        self.paused.append(info_hash)

    def resume(self, info_hash: str) -> None:
        self.resumed.append(info_hash)

    def remove(self, info_hash: str, *, delete_files: bool) -> None:
        self.removed.append((info_hash, delete_files))

    def poll_status(self) -> list[TorrentProgress]:
        return list(self.progress)

    def apply_limits(self, settings: TorrentSettings) -> None:
        self.limits.append(settings)


class _FakeObserver:
    def schedule(self, *args, **kwargs): ...
    def start(self): ...
    def stop(self): ...
    def join(self, timeout=None): ...


@pytest.fixture
def watch(tmp_path: Path):
    database_path = tmp_path / "torrents.db"
    initialize_core_database(database_path)

    watch_folder = tmp_path / "preuzimanja"
    watch_folder.mkdir()

    store = TorrentSettingsStore(database_path)
    store.save(
        TorrentSettings(
            watch_folder=str(watch_folder),
            download_path=str(tmp_path / "odrediste"),
        )
    )

    repository = TorrentRepository(database_path)
    engine = _FakeEngine()
    service = TorrentService(repository, engine, store)
    monitor = FileMonitorService(observer_factory=_FakeObserver)

    return TorrentWatchService(service, monitor), repository, watch_folder, monitor


def test_start_registers_configured_folder(watch) -> None:
    watcher, _repository, watch_folder, monitor = watch

    started = watcher.start()

    assert started is True
    assert [f.path for f in monitor.get_monitored_folders()] == [
        str(watch_folder.resolve())
    ]


def test_start_returns_false_when_folder_missing(tmp_path: Path) -> None:
    database_path = tmp_path / "torrents.db"
    initialize_core_database(database_path)
    store = TorrentSettingsStore(database_path)
    store.save(TorrentSettings(watch_folder=str(tmp_path / "nema-me")))
    service = TorrentService(
        TorrentRepository(database_path), _FakeEngine(), store
    )
    watcher = TorrentWatchService(
        service, FileMonitorService(observer_factory=_FakeObserver)
    )

    assert watcher.start() is False


def test_new_torrent_file_is_registered_but_not_started(watch) -> None:
    watcher, repository, watch_folder, _monitor = watch
    watcher.start()
    torrent_file = watch_folder / "Dune.torrent"
    torrent_file.write_bytes(b"d8:announce")

    watcher.handle_event(
        FileEvent(event_type=FileEventType.CREATED, src_path=str(torrent_file))
    )

    entries = repository.list()
    assert len(entries) == 1
    assert entries[0].status is TorrentStatus.METADATA_FETCHING
    assert entries[0].source_kind == "file"


def test_non_torrent_file_is_ignored(watch) -> None:
    watcher, repository, watch_folder, _monitor = watch
    watcher.start()
    other = watch_folder / "beleska.txt"
    other.write_text("zdravo", encoding="utf-8")

    watcher.handle_event(
        FileEvent(event_type=FileEventType.CREATED, src_path=str(other))
    )

    assert repository.list() == []


def test_directory_event_is_ignored(watch) -> None:
    watcher, repository, watch_folder, _monitor = watch
    watcher.start()

    watcher.handle_event(
        FileEvent(
            event_type=FileEventType.CREATED,
            src_path=str(watch_folder / "podfolder"),
            is_directory=True,
        )
    )

    assert repository.list() == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_filmium_torrent_watch.py -v`
Expected: FAIL sa `ModuleNotFoundError: No module named 'core.domains.filmium.torrents.torrent_watch_service'`

- [ ] **Step 3: Write the watch service**

`core/domains/filmium/torrents/torrent_watch_service.py`:

```python
# ========== NADZOR FOLDERA ZA .torrent FAJLOVE ==========
# Nov .torrent u nadziranom folderu se SAMO zabeleži i pošalje klijentu
# pauziran. Skidanje kreće tek posle korisnikovog odobrenja.
from __future__ import annotations

import os

from core.domains.filmium.torrents.torrent_service import (
    TorrentService,
    TorrentServiceError,
)
from core.system.file_monitor import FileMonitorService
from core.system.file_monitor.monitor_models import FileEvent, FileEventType


# ========== WATCH SERVIS ==========
class TorrentWatchService:
    """Prati folder iz podešavanja i registruje nove .torrent fajlove."""

    def __init__(
        self,
        service: TorrentService,
        file_monitor: FileMonitorService,
    ) -> None:
        self._service = service
        self._monitor = file_monitor
        self._folder: str | None = None
        self._registered = False

    def start(self) -> bool:
        folder = self._service.settings().watch_folder.strip()
        if not folder or not os.path.isdir(folder):
            return False

        resolved = str(os.path.abspath(folder))

        if not self._registered:
            self._monitor.register_callback(
                FileEventType.CREATED,
                self.handle_event,
            )
            self._registered = True

        self._monitor.start_monitoring(resolved, recursive=False)
        self._folder = resolved
        return True

    def stop(self) -> None:
        if self._folder is not None:
            self._monitor.stop_monitoring(self._folder)
            self._folder = None

    def handle_event(self, event: FileEvent) -> None:
        if event.is_directory:
            return
        if not event.src_path.lower().endswith(".torrent"):
            return

        try:
            self._service.add(event.src_path)
        except TorrentServiceError:
            # Neispravan ili nedostupan torrent ne sme da obori nadzor.
            return
```

- [ ] **Step 4: Run test to verify it passes**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_filmium_torrent_watch.py -v`
Expected: PASS, 5 testova

Ako test `test_start_registers_configured_folder` padne na poređenju putanje, uskladiti očekivanje sa onim što `FileMonitorService.start_monitoring` vraća — taj servis radi `os.path.abspath`, bez `resolve()`.

- [ ] **Step 5: Extend the package exports**

U `core/domains/filmium/torrents/__init__.py` dodati:

```python
from core.domains.filmium.torrents.torrent_watch_service import TorrentWatchService
```

i u `__all__` dodati `"TorrentWatchService"`.

- [ ] **Step 6: Commit**

```bash
git add core/domains/filmium/torrents tests/test_filmium_torrent_watch.py
git commit -m "feat(filmium): nadzor foldera za .torrent fajlove"
```

---

### Task 6: API rute, SSE i runtime

**Files:**
- Create: `apps/api/schemas/filmium_torrents.py`
- Create: `apps/api/routers/filmium_torrents.py`
- Create: `apps/api/torrent_runtime.py`
- Modify: `apps/api/main.py` (uvoz rutera, `include_router`, `_start_torrents` i `_stop_torrents` u `core_lifespan`)
- Test: `tests/test_api_filmium_torrents.py`

**Interfaces:**
- Consumes: `TorrentService`, `TorrentServiceError`, modeli iz Taska 1
- Produces: rute pod `/api/v1/filmium/torrents`, `get_service()` za `dependency_overrides`, `build_torrent_runtime(*, service=None, watch=None)`

- [ ] **Step 1: Write the failing test**

`tests/test_api_filmium_torrents.py`:

```python
# ========== TESTOVI: API FILMIUM torrenti ==========
from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from apps.api.main import app
from apps.api.routers.filmium_torrents import get_service
from core.database.runtime import initialize_core_database
from core.domains.filmium.torrents.torrent_models import (
    EngineHealth,
    TorrentFileEntry,
    TorrentMetadata,
    TorrentProgress,
    TorrentSettings,
)
from core.domains.filmium.torrents.torrent_repository import TorrentRepository
from core.domains.filmium.torrents.torrent_service import TorrentService
from core.domains.filmium.torrents.torrent_settings import TorrentSettingsStore

# Dvojnik engine-a. Ponavlja se po test fajlu — projekat nema deljene
# test pomoćnike (isti obrazac kao `_FakeObserver` u drugim testovima).
class _FakeEngine:
    def __init__(self) -> None:
        self.files: list[TorrentFileEntry] = []
        self.progress: list[TorrentProgress] = []
        self.priority_calls: list[tuple[str, dict[int, int]]] = []
        self.started: list[str] = []
        self.paused: list[str] = []
        self.resumed: list[str] = []
        self.removed: list[tuple[str, bool]] = []
        self.limits: list[TorrentSettings] = []

    def is_available(self) -> EngineHealth:
        return EngineHealth(available=True, version="5.0.1")

    def add(self, source: str, *, save_path: str) -> TorrentMetadata:
        return TorrentMetadata(info_hash="abc123", name=source)

    def list_files(self, info_hash: str) -> list[TorrentFileEntry]:
        return list(self.files)

    def set_file_priorities(self, info_hash: str, priorities: dict[int, int]) -> None:
        self.priority_calls.append((info_hash, dict(priorities)))

    def start(self, info_hash: str) -> None:
        self.started.append(info_hash)

    def pause(self, info_hash: str) -> None:
        self.paused.append(info_hash)

    def resume(self, info_hash: str) -> None:
        self.resumed.append(info_hash)

    def remove(self, info_hash: str, *, delete_files: bool) -> None:
        self.removed.append((info_hash, delete_files))

    def poll_status(self) -> list[TorrentProgress]:
        return list(self.progress)

    def apply_limits(self, settings: TorrentSettings) -> None:
        self.limits.append(settings)


@pytest.fixture
def client(tmp_path: Path) -> Iterator[tuple[TestClient, TorrentService, _FakeEngine]]:
    database_path = tmp_path / "torrents.db"
    initialize_core_database(database_path)

    store = TorrentSettingsStore(database_path)
    store.save(TorrentSettings(download_path=str(tmp_path / "odrediste")))
    engine = _FakeEngine()
    service = TorrentService(TorrentRepository(database_path), engine, store)

    app.dependency_overrides[get_service] = lambda: service
    test_client = TestClient(app)
    try:
        yield test_client, service, engine
    finally:
        app.dependency_overrides.pop(get_service, None)


def test_health_reports_engine(client) -> None:
    test_client, _service, _engine = client

    response = test_client.get("/api/v1/filmium/torrents/health")

    assert response.status_code == 200
    assert response.json()["engine_available"] is True


def test_add_returns_created_entry(client) -> None:
    test_client, _service, _engine = client

    response = test_client.post(
        "/api/v1/filmium/torrents/add",
        json={"source": "magnet:?xt=urn:btih:abc123"},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["info_hash"] == "abc123"
    assert body["status"] == "metadata_fetching"


def test_add_without_download_path_returns_400(tmp_path: Path) -> None:
    database_path = tmp_path / "torrents.db"
    initialize_core_database(database_path)
    service = TorrentService(
        TorrentRepository(database_path),
        _FakeEngine(),
        TorrentSettingsStore(database_path),
    )
    app.dependency_overrides[get_service] = lambda: service
    try:
        response = TestClient(app).post(
            "/api/v1/filmium/torrents/add",
            json={"source": "magnet:?xt=urn:btih:abc123"},
        )
    finally:
        app.dependency_overrides.pop(get_service, None)

    assert response.status_code == 400
    assert "Odredište" in response.json()["detail"]


def test_list_and_files_and_approve(client) -> None:
    test_client, service, engine = client
    test_client.post(
        "/api/v1/filmium/torrents/add",
        json={"source": "magnet:?xt=urn:btih:abc123"},
    )
    engine.files = [
        TorrentFileEntry(file_index=0, path="Dune.mkv", size_bytes=900),
        TorrentFileEntry(file_index=1, path="Dune.nfo", size_bytes=2),
    ]
    engine.progress = [TorrentProgress(info_hash="abc123", progress=0.0)]
    service.poll()

    listed = test_client.get("/api/v1/filmium/torrents/").json()
    files = test_client.get("/api/v1/filmium/torrents/abc123/files").json()
    approved = test_client.post(
        "/api/v1/filmium/torrents/abc123/approve",
        json={"selected_indexes": [0]},
    )

    assert len(listed) == 1
    assert [f["path"] for f in files] == ["Dune.mkv", "Dune.nfo"]
    assert approved.status_code == 200
    assert approved.json()["status"] == "downloading"


def test_approve_with_empty_selection_returns_400(client) -> None:
    test_client, service, engine = client
    test_client.post(
        "/api/v1/filmium/torrents/add",
        json={"source": "magnet:?xt=urn:btih:abc123"},
    )
    engine.files = [TorrentFileEntry(file_index=0, path="Dune.mkv", size_bytes=900)]
    engine.progress = [TorrentProgress(info_hash="abc123", progress=0.0)]
    service.poll()

    response = test_client.post(
        "/api/v1/filmium/torrents/abc123/approve",
        json={"selected_indexes": []},
    )

    assert response.status_code == 400


def test_unknown_torrent_returns_404(client) -> None:
    test_client, _service, _engine = client

    response = test_client.post("/api/v1/filmium/torrents/nema/pause")

    assert response.status_code == 404


def test_settings_get_and_put(client, tmp_path: Path) -> None:
    test_client, _service, _engine = client

    before = test_client.get("/api/v1/filmium/torrents/settings").json()
    updated = test_client.put(
        "/api/v1/filmium/torrents/settings",
        json={**before, "max_active": 5, "host": "192.168.0.10"},
    )

    assert updated.status_code == 200
    assert updated.json()["max_active"] == 5
    assert updated.json()["host"] == "192.168.0.10"


def test_settings_put_never_returns_password(client) -> None:
    test_client, _service, _engine = client
    before = test_client.get("/api/v1/filmium/torrents/settings").json()

    response = test_client.put(
        "/api/v1/filmium/torrents/settings",
        json={**before, "password": "tajna"},
    )

    assert "password" not in response.json()
    assert response.json()["has_password"] is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_api_filmium_torrents.py -v`
Expected: FAIL sa `ModuleNotFoundError: No module named 'apps.api.routers.filmium_torrents'`

- [ ] **Step 3: Write the schemas**

`apps/api/schemas/filmium_torrents.py`:

```python
# ========== ŠEME: FILMIUM TORRENTI ==========
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from core.domains.filmium.torrents.torrent_models import (
    EngineHealth,
    TorrentEntry,
    TorrentFileEntry,
    TorrentProgress,
    TorrentSettings,
)


class TorrentHealthResponse(BaseModel):
    engine_available: bool
    version: str | None = None
    message: str | None = None

    @classmethod
    def from_domain(cls, health: EngineHealth) -> "TorrentHealthResponse":
        return cls(
            engine_available=health.available,
            version=health.version,
            message=health.message,
        )


class TorrentAddRequest(BaseModel):
    source: str = Field(min_length=1)


class TorrentApproveRequest(BaseModel):
    selected_indexes: list[int] = Field(default_factory=list)


class TorrentFileResponse(BaseModel):
    file_index: int
    path: str
    size_bytes: int
    selected: bool

    @classmethod
    def from_domain(cls, item: TorrentFileEntry) -> "TorrentFileResponse":
        return cls(
            file_index=item.file_index,
            path=item.path,
            size_bytes=item.size_bytes,
            selected=item.selected,
        )


class TorrentResponse(BaseModel):
    info_hash: str
    name: str
    source_kind: str
    status: str
    save_path: str
    total_bytes: int
    added_at: datetime
    completed_at: datetime | None = None
    error_message: str | None = None

    @classmethod
    def from_domain(cls, entry: TorrentEntry) -> "TorrentResponse":
        return cls(
            info_hash=entry.info_hash,
            name=entry.name,
            source_kind=entry.source_kind,
            status=entry.status.value,
            save_path=entry.save_path,
            total_bytes=entry.total_bytes,
            added_at=entry.added_at,
            completed_at=entry.completed_at,
            error_message=entry.error_message,
        )


class TorrentProgressResponse(BaseModel):
    info_hash: str
    progress: float
    download_rate: int
    upload_rate: int
    eta_seconds: int | None = None
    seeds: int
    peers: int
    is_finished: bool
    is_paused: bool

    @classmethod
    def from_domain(cls, item: TorrentProgress) -> "TorrentProgressResponse":
        return cls(
            info_hash=item.info_hash,
            progress=item.progress,
            download_rate=item.download_rate,
            upload_rate=item.upload_rate,
            eta_seconds=item.eta_seconds,
            seeds=item.seeds,
            peers=item.peers,
            is_finished=item.is_finished,
            is_paused=item.is_paused,
        )


class TorrentSettingsRequest(BaseModel):
    host: str = "127.0.0.1"
    port: int = 8080
    username: str = ""
    # Prazna lozinka znači „ne diraj postojeću".
    password: str | None = None
    watch_folder: str = ""
    download_path: str = ""
    max_download_kbs: int = 0
    max_upload_kbs: int = 0
    max_active: int = 3
    auto_start: bool = True
    seed_after_complete: bool = False
    delete_source_torrent: bool = False
    unselected_extensions: list[str] = Field(
        default_factory=lambda: [".nfo", ".txt", ".url", ".jpg", ".png", ".sfv"]
    )


class TorrentSettingsResponse(BaseModel):
    """Lozinka se NIKADA ne vraća klijentu; šalje se samo da li postoji."""

    host: str
    port: int
    username: str
    has_password: bool
    watch_folder: str
    download_path: str
    max_download_kbs: int
    max_upload_kbs: int
    max_active: int
    auto_start: bool
    seed_after_complete: bool
    delete_source_torrent: bool
    unselected_extensions: list[str]

    @classmethod
    def from_domain(cls, settings: TorrentSettings) -> "TorrentSettingsResponse":
        return cls(
            host=settings.host,
            port=settings.port,
            username=settings.username,
            has_password=bool(settings.password),
            watch_folder=settings.watch_folder,
            download_path=settings.download_path,
            max_download_kbs=settings.max_download_kbs,
            max_upload_kbs=settings.max_upload_kbs,
            max_active=settings.max_active,
            auto_start=settings.auto_start,
            seed_after_complete=settings.seed_after_complete,
            delete_source_torrent=settings.delete_source_torrent,
            unselected_extensions=list(settings.unselected_extensions),
        )
```

- [ ] **Step 4: Write the router**

`apps/api/routers/filmium_torrents.py`:

```python
# ========== ROUTER: FILMIUM TORRENTI ==========
from __future__ import annotations

import json
import time
from collections.abc import Iterator

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse

from apps.api import torrent_runtime
from apps.api.schemas.filmium_torrents import (
    TorrentAddRequest,
    TorrentApproveRequest,
    TorrentFileResponse,
    TorrentHealthResponse,
    TorrentProgressResponse,
    TorrentResponse,
    TorrentSettingsRequest,
    TorrentSettingsResponse,
)
from core.domains.filmium.torrents.torrent_models import (
    TorrentSettings,
    TorrentStatus,
)
from core.domains.filmium.torrents.torrent_service import (
    TorrentService,
    TorrentServiceError,
)

router = APIRouter(
    prefix="/api/v1/filmium/torrents",
    tags=["FILMIUM Torrenti"],
)

# Razmak između dva SSE otkucaja.
STREAM_INTERVAL_SECONDS = 1.0


def get_service() -> TorrentService:
    return torrent_runtime.get_service()


def _not_found(error: TorrentServiceError) -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error))


def _bad_request(error: TorrentServiceError) -> HTTPException:
    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error))


def _raise(error: TorrentServiceError) -> None:
    if "nije pronađen" in str(error):
        raise _not_found(error)
    raise _bad_request(error)


# ==========          ZDRAVLJE          ==========

@router.get("/health", response_model=TorrentHealthResponse)
def health(
    service: TorrentService = Depends(get_service),
) -> TorrentHealthResponse:
    return TorrentHealthResponse.from_domain(service.health())


# ==========          PODEŠAVANJA          ==========

@router.get("/settings", response_model=TorrentSettingsResponse)
def read_settings(
    service: TorrentService = Depends(get_service),
) -> TorrentSettingsResponse:
    return TorrentSettingsResponse.from_domain(service.settings())


@router.put("/settings", response_model=TorrentSettingsResponse)
def write_settings(
    payload: TorrentSettingsRequest,
    service: TorrentService = Depends(get_service),
) -> TorrentSettingsResponse:
    current = service.settings()
    saved = service.save_settings(
        TorrentSettings(
            host=payload.host,
            port=payload.port,
            username=payload.username,
            # None ili prazno znači „zadrži postojeću lozinku".
            password=payload.password or current.password,
            watch_folder=payload.watch_folder,
            download_path=payload.download_path,
            max_download_kbs=payload.max_download_kbs,
            max_upload_kbs=payload.max_upload_kbs,
            max_active=payload.max_active,
            auto_start=payload.auto_start,
            seed_after_complete=payload.seed_after_complete,
            delete_source_torrent=payload.delete_source_torrent,
            unselected_extensions=tuple(payload.unselected_extensions),
        )
    )
    return TorrentSettingsResponse.from_domain(saved)


# ==========          LISTA I DODAVANJE          ==========

@router.get("/", response_model=list[TorrentResponse])
def list_torrents(
    status_filter: str | None = None,
    service: TorrentService = Depends(get_service),
) -> list[TorrentResponse]:
    parsed = TorrentStatus(status_filter) if status_filter else None
    return [TorrentResponse.from_domain(item) for item in service.list(parsed)]


@router.post(
    "/add",
    response_model=TorrentResponse,
    status_code=status.HTTP_201_CREATED,
)
def add_torrent(
    payload: TorrentAddRequest,
    service: TorrentService = Depends(get_service),
) -> TorrentResponse:
    try:
        return TorrentResponse.from_domain(service.add(payload.source))
    except TorrentServiceError as error:
        _raise(error)
        raise  # pragma: no cover — _raise uvek baca


# ==========          FAJLOVI I ODOBRENJE          ==========

@router.get("/{info_hash}/files", response_model=list[TorrentFileResponse])
def list_files(
    info_hash: str,
    service: TorrentService = Depends(get_service),
) -> list[TorrentFileResponse]:
    try:
        return [
            TorrentFileResponse.from_domain(item)
            for item in service.files(info_hash)
        ]
    except TorrentServiceError as error:
        _raise(error)
        raise  # pragma: no cover


@router.post("/{info_hash}/approve", response_model=TorrentResponse)
def approve(
    info_hash: str,
    payload: TorrentApproveRequest,
    service: TorrentService = Depends(get_service),
) -> TorrentResponse:
    try:
        return TorrentResponse.from_domain(
            service.approve(info_hash, payload.selected_indexes)
        )
    except TorrentServiceError as error:
        _raise(error)
        raise  # pragma: no cover


# ==========          KONTROLA          ==========

@router.post("/{info_hash}/pause", response_model=TorrentResponse)
def pause(
    info_hash: str,
    service: TorrentService = Depends(get_service),
) -> TorrentResponse:
    try:
        return TorrentResponse.from_domain(service.pause(info_hash))
    except TorrentServiceError as error:
        _raise(error)
        raise  # pragma: no cover


@router.post("/{info_hash}/resume", response_model=TorrentResponse)
def resume(
    info_hash: str,
    service: TorrentService = Depends(get_service),
) -> TorrentResponse:
    try:
        return TorrentResponse.from_domain(service.resume(info_hash))
    except TorrentServiceError as error:
        _raise(error)
        raise  # pragma: no cover


@router.delete("/{info_hash}", status_code=status.HTTP_204_NO_CONTENT)
def remove(
    info_hash: str,
    delete_files: bool = False,
    service: TorrentService = Depends(get_service),
) -> None:
    try:
        service.remove(info_hash, delete_files=delete_files)
    except TorrentServiceError as error:
        _raise(error)


# ==========          SSE PROGRES          ==========

@router.get("/stream")
def stream(service: TorrentService = Depends(get_service)) -> StreamingResponse:
    """Jedan strim za sve aktivne torrente; otkucaj svake sekunde."""

    def events() -> Iterator[str]:
        while True:
            payload = [
                TorrentProgressResponse.from_domain(item).model_dump()
                for item in service.poll()
            ]
            body = json.dumps(payload, ensure_ascii=False, default=str)
            yield f"event: progress\ndata: {body}\n\n"
            time.sleep(STREAM_INTERVAL_SECONDS)

    return StreamingResponse(events(), media_type="text/event-stream")
```

- [ ] **Step 5: Write the runtime**

`apps/api/torrent_runtime.py`:

```python
# ========== TORRENT RUNTIME (deljeni servis za API + startup) ==========
# Drži deljenu instancu TorrentService-a sa qBittorrent engine-om, CORE
# file_monitor-om za nadzor foldera i OS toast notifikacijama.
from __future__ import annotations

from core.domains.filmium.torrents.torrent_engine import QbittorrentEngine
from core.domains.filmium.torrents.torrent_models import TorrentEntry
from core.domains.filmium.torrents.torrent_repository import TorrentRepository
from core.domains.filmium.torrents.torrent_service import TorrentService
from core.domains.filmium.torrents.torrent_settings import TorrentSettingsStore
from core.domains.filmium.torrents.torrent_watch_service import TorrentWatchService
from core.system.file_monitor import FileMonitorService, OsToastNotifier

# ---------- deljene instance ----------
_repository = TorrentRepository()
_settings_store = TorrentSettingsStore()
_engine = QbittorrentEngine(_settings_store.load)
_monitor = FileMonitorService()
_notifier = OsToastNotifier()


def _on_completed(entry: TorrentEntry) -> None:
    """Predaja putanje postojećem FILMIUM uvozu.

    Uvoz se NE pokreće sam — korisnik potvrđuje pregled. Ovde se samo
    beleži da je sadržaj spreman; GUI ga pokupi kroz listu završenih.
    """

    print(f"CORE: FILMIUM torrent završen — {entry.name} ({entry.save_path}).")


_service = TorrentService(
    _repository,
    _engine,
    _settings_store,
    on_completed=_on_completed,
    notify=_notifier.notify,
)

_watch = TorrentWatchService(_service, _monitor)


def get_service() -> TorrentService:
    return _service


# ========== RUNTIME (start/stop iz lifespan-a) ==========
class TorrentRuntime:
    """Usklađuje bazu sa klijentom i pali nadzor foldera; gasi ga na stop."""

    def __init__(self, service: TorrentService, watch: TorrentWatchService) -> None:
        self.service = service
        self.watch = watch

    def start(self) -> bool:
        # Restart CORE-a: qBittorrent je nastavio sam, pa se baza usklađuje
        # sa onim što klijent prijavljuje za kategoriju FILMIUM.
        self.service.reconcile()
        return self.watch.start()

    def stop(self) -> None:
        self.watch.stop()


def build_torrent_runtime(
    *,
    service: TorrentService | None = None,
    watch: TorrentWatchService | None = None,
) -> TorrentRuntime:
    return TorrentRuntime(service or _service, watch or _watch)
```

- [ ] **Step 6: Wire into main.py**

U `apps/api/main.py`, uz ostale FILMIUM uvoze rutera:

```python
from apps.api.routers.filmium_torrents import (
    router as filmium_torrents_router,
)
```

Uz ostale `include_router` pozive, odmah posle `app.include_router(filmium_auto_import_router)`:

```python
app.include_router(filmium_torrents_router)
```

Pored `_start_auto_import` / `_stop_auto_import` dodati:

```python
_torrent_runtime = None


def _start_torrents() -> None:
    """Pali FILMIUM nadzor foldera za .torrent fajlove."""

    global _torrent_runtime
    try:
        from apps.api.torrent_runtime import build_torrent_runtime

        _torrent_runtime = build_torrent_runtime()
        started = _torrent_runtime.start()
        if started:
            print("CORE: FILMIUM nadzor torrent foldera aktivan.")
        else:
            print("CORE: FILMIUM torrenti — nadzirani folder nije podešen.")
    except Exception as error:  # noqa: BLE001 — ne rušimo start API-ja
        print(f"CORE upozorenje: torrent modul nije pokrenut: {error}")


def _stop_torrents() -> None:
    global _torrent_runtime
    try:
        if _torrent_runtime is not None:
            _torrent_runtime.stop()
    except Exception as error:  # noqa: BLE001
        print(f"CORE upozorenje: gašenje torrent modula: {error}")
```

U `core_lifespan`, odmah posle `_start_auto_import()` dodati `_start_torrents()`, a u delu za gašenje, odmah pre `_stop_auto_import()` dodati `_stop_torrents()`.

- [ ] **Step 7: Run test to verify it passes**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_api_filmium_torrents.py -v`
Expected: PASS, 8 testova

- [ ] **Step 8: Run the whole Python suite**

Run: `./.venv/Scripts/python.exe -m pytest -q`
Expected: bez novih padova

- [ ] **Step 9: Commit**

```bash
git add apps/api/schemas/filmium_torrents.py apps/api/routers/filmium_torrents.py apps/api/torrent_runtime.py apps/api/main.py tests/test_api_filmium_torrents.py
git commit -m "feat(filmium): API rute, SSE progres i runtime torrent modula"
```

---

### Task 7: GUI tipovi, API klijent i SSE hook

**Files:**
- Create: `apps/gui/src/types/filmiumTorrents.ts`
- Create: `apps/gui/src/services/filmiumTorrentsApi.ts`
- Create: `apps/gui/src/features/filmium/hooks/useTorrentProgress.ts`
- Test: `apps/gui/src/features/filmium/hooks/useTorrentProgress.test.ts`

**Interfaces:**
- Consumes: `getJson`, `postJson`, `putJson`, `deleteRequest`, `getApiUrl` iz `apps/gui/src/services/httpClient.ts`
- Produces: tipovi `TorrentStatus`, `Torrent`, `TorrentFile`, `TorrentProgress`, `TorrentSettings`, `TorrentHealth`; funkcije `listTorrents`, `addTorrent`, `listTorrentFiles`, `approveTorrent`, `pauseTorrent`, `resumeTorrent`, `removeTorrent`, `getTorrentHealth`, `getTorrentSettings`, `saveTorrentSettings`; hook `useTorrentProgress()`

- [ ] **Step 1: Write the failing test**

`apps/gui/src/features/filmium/hooks/useTorrentProgress.test.ts`:

```typescript
import { act, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { useTorrentProgress } from "./useTorrentProgress";

class FakeEventSource {
  static last: FakeEventSource | null = null;

  url: string;
  onerror: ((event: Event) => void) | null = null;
  closed = false;
  private listeners = new Map<string, (event: MessageEvent) => void>();

  constructor(url: string) {
    this.url = url;
    FakeEventSource.last = this;
  }

  addEventListener(type: string, handler: (event: MessageEvent) => void) {
    this.listeners.set(type, handler);
  }

  emit(type: string, data: unknown) {
    const handler = this.listeners.get(type);
    handler?.({ data: JSON.stringify(data) } as MessageEvent);
  }

  close() {
    this.closed = true;
  }
}

describe("useTorrentProgress", () => {
  beforeEach(() => {
    vi.stubGlobal("EventSource", FakeEventSource);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    FakeEventSource.last = null;
  });

  it("mapira progress događaj po info hash-u", () => {
    const { result } = renderHook(() => useTorrentProgress());

    act(() => {
      FakeEventSource.last?.emit("progress", [
        {
          info_hash: "abc123",
          progress: 0.5,
          download_rate: 2048,
          upload_rate: 0,
          eta_seconds: 60,
          seeds: 3,
          peers: 1,
          is_finished: false,
          is_paused: false,
        },
      ]);
    });

    expect(result.current.progressByHash.abc123.progress).toBe(0.5);
    expect(result.current.progressByHash.abc123.downloadRate).toBe(2048);
  });

  it("prazan događaj briše prethodni progres", () => {
    const { result } = renderHook(() => useTorrentProgress());

    act(() => {
      FakeEventSource.last?.emit("progress", [
        { info_hash: "abc123", progress: 0.5 },
      ]);
    });
    act(() => {
      FakeEventSource.last?.emit("progress", []);
    });

    expect(result.current.progressByHash).toEqual({});
  });

  it("greška veze postavlja isConnected na false", () => {
    const { result } = renderHook(() => useTorrentProgress());

    act(() => {
      FakeEventSource.last?.onerror?.(new Event("error"));
    });

    expect(result.current.isConnected).toBe(false);
  });

  it("zatvara strim pri odmontiranju", () => {
    const { unmount } = renderHook(() => useTorrentProgress());
    const source = FakeEventSource.last;

    unmount();

    expect(source?.closed).toBe(true);
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd apps/gui && npx vitest run src/features/filmium/hooks/useTorrentProgress.test.ts`
Expected: FAIL sa `Failed to resolve import "./useTorrentProgress"`

- [ ] **Step 3: Write the types**

`apps/gui/src/types/filmiumTorrents.ts`:

```typescript
// ==========          TIPOVI: FILMIUM TORRENTI          ==========

export type TorrentStatus =
  | "detected"
  | "metadata_fetching"
  | "awaiting_approval"
  | "downloading"
  | "paused"
  | "completed"
  | "error";

export type Torrent = {
  info_hash: string;
  name: string;
  source_kind: "magnet" | "file";
  status: TorrentStatus;
  save_path: string;
  total_bytes: number;
  added_at: string;
  completed_at: string | null;
  error_message: string | null;
};

export type TorrentFile = {
  file_index: number;
  path: string;
  size_bytes: number;
  selected: boolean;
};

export type TorrentHealth = {
  engine_available: boolean;
  version: string | null;
  message: string | null;
};

export type TorrentSettings = {
  host: string;
  port: number;
  username: string;
  has_password: boolean;
  watch_folder: string;
  download_path: string;
  max_download_kbs: number;
  max_upload_kbs: number;
  max_active: number;
  auto_start: boolean;
  seed_after_complete: boolean;
  delete_source_torrent: boolean;
  unselected_extensions: string[];
};

/** Telo PUT zahteva; `password` se šalje samo kad se menja. */
export type TorrentSettingsRequest = Omit<TorrentSettings, "has_password"> & {
  password?: string;
};

/** Normalizovan progres, onako kako ga hook izlaže komponentama. */
export type TorrentProgress = {
  infoHash: string;
  progress: number;
  downloadRate: number;
  uploadRate: number;
  etaSeconds: number | null;
  seeds: number;
  peers: number;
  isFinished: boolean;
  isPaused: boolean;
};
```

- [ ] **Step 4: Write the API client**

`apps/gui/src/services/filmiumTorrentsApi.ts`:

```typescript
import {
  deleteRequest,
  getJson,
  postJson,
  putJson,
} from "./httpClient";

import type {
  Torrent,
  TorrentFile,
  TorrentHealth,
  TorrentSettings,
  TorrentSettingsRequest,
  TorrentStatus,
} from "../types/filmiumTorrents";


const BASE = "/api/v1/filmium/torrents";


// ==========          FILMIUM TORRENTI API          ==========

/** Zdravlje veze sa qBittorrent-om. */
export function getTorrentHealth(): Promise<TorrentHealth> {
  return getJson<TorrentHealth>(`${BASE}/health`);
}

/** Lista torrenta; bez filtera vraća sve. */
export function listTorrents(status?: TorrentStatus): Promise<Torrent[]> {
  const query = status ? `?status_filter=${encodeURIComponent(status)}` : "";
  return getJson<Torrent[]>(`${BASE}/${query}`);
}

/** Dodaje magnet link ili putanju do .torrent fajla (pauzirano). */
export function addTorrent(source: string): Promise<Torrent> {
  return postJson<Torrent, { source: string }>(`${BASE}/add`, { source });
}

/** Lista fajlova unutar torrenta. */
export function listTorrentFiles(infoHash: string): Promise<TorrentFile[]> {
  return getJson<TorrentFile[]>(`${BASE}/${infoHash}/files`);
}

/** Odobrava izabrane fajlove i pokreće preuzimanje. */
export function approveTorrent(
  infoHash: string,
  selectedIndexes: number[],
): Promise<Torrent> {
  return postJson<Torrent, { selected_indexes: number[] }>(
    `${BASE}/${infoHash}/approve`,
    { selected_indexes: selectedIndexes },
  );
}

export function pauseTorrent(infoHash: string): Promise<Torrent> {
  return postJson<Torrent, Record<string, never>>(
    `${BASE}/${infoHash}/pause`,
    {},
  );
}

export function resumeTorrent(infoHash: string): Promise<Torrent> {
  return postJson<Torrent, Record<string, never>>(
    `${BASE}/${infoHash}/resume`,
    {},
  );
}

/** Otkazuje torrent; opciono briše i već skinute fajlove. */
export function removeTorrent(
  infoHash: string,
  deleteFiles = false,
): Promise<void> {
  return deleteRequest<void>(
    `${BASE}/${infoHash}?delete_files=${deleteFiles ? "true" : "false"}`,
  );
}

export function getTorrentSettings(): Promise<TorrentSettings> {
  return getJson<TorrentSettings>(`${BASE}/settings`);
}

export function saveTorrentSettings(
  settings: TorrentSettingsRequest,
): Promise<TorrentSettings> {
  return putJson<TorrentSettings, TorrentSettingsRequest>(
    `${BASE}/settings`,
    settings,
  );
}
```

- [ ] **Step 5: Write the hook**

`apps/gui/src/features/filmium/hooks/useTorrentProgress.ts`:

```typescript
import { useEffect, useRef, useState } from "react";

import { getApiUrl } from "../../../services/httpClient";

import type { TorrentProgress } from "../../../types/filmiumTorrents";


type ProgressPayload = {
  info_hash: string;
  progress?: number;
  download_rate?: number;
  upload_rate?: number;
  eta_seconds?: number | null;
  seeds?: number;
  peers?: number;
  is_finished?: boolean;
  is_paused?: boolean;
};

// Pauza pre ponovnog povezivanja kad strim pukne.
const RECONNECT_DELAY_MS = 3000;


// ==========          PROGRES TORRENTA (SSE)          ==========

/**
 * Čita `/api/v1/filmium/torrents/stream` i drži progres po info hash-u.
 *
 * Strim se otvara jednom po komponenti; pri prekidu veze pokušava ponovo
 * posle kratke pauze. Tolerantan na neispravan JSON — takav otkucaj
 * se preskače umesto da obori komponentu.
 */
export function useTorrentProgress(): {
  progressByHash: Record<string, TorrentProgress>;
  isConnected: boolean;
} {
  const [progressByHash, setProgressByHash] = useState<
    Record<string, TorrentProgress>
  >({});
  const [isConnected, setIsConnected] = useState(true);
  const timerRef = useRef<number | null>(null);

  useEffect(() => {
    let source: EventSource | null = null;
    let cancelled = false;

    const connect = () => {
      if (cancelled) {
        return;
      }

      source = new EventSource(getApiUrl("/api/v1/filmium/torrents/stream"));
      setIsConnected(true);

      source.addEventListener("progress", (event: MessageEvent) => {
        try {
          const rows = JSON.parse(event.data) as ProgressPayload[];
          const next: Record<string, TorrentProgress> = {};

          for (const row of rows) {
            next[row.info_hash] = {
              infoHash: row.info_hash,
              progress: row.progress ?? 0,
              downloadRate: row.download_rate ?? 0,
              uploadRate: row.upload_rate ?? 0,
              etaSeconds: row.eta_seconds ?? null,
              seeds: row.seeds ?? 0,
              peers: row.peers ?? 0,
              isFinished: row.is_finished ?? false,
              isPaused: row.is_paused ?? false,
            };
          }

          setProgressByHash(next);
        } catch {
          // Neispravan otkucaj se preskače.
        }
      });

      source.onerror = () => {
        setIsConnected(false);
        source?.close();
        timerRef.current = window.setTimeout(connect, RECONNECT_DELAY_MS);
      };
    };

    connect();

    return () => {
      cancelled = true;
      if (timerRef.current !== null) {
        window.clearTimeout(timerRef.current);
      }
      source?.close();
    };
  }, []);

  return { progressByHash, isConnected };
}
```

- [ ] **Step 6: Run test to verify it passes**

Run: `cd apps/gui && npx vitest run src/features/filmium/hooks/useTorrentProgress.test.ts`
Expected: PASS, 4 testa

- [ ] **Step 7: Type check**

Run: `cd apps/gui && npx tsc --noEmit`
Expected: bez grešaka

- [ ] **Step 8: Commit**

```bash
git add apps/gui/src/types/filmiumTorrents.ts apps/gui/src/services/filmiumTorrentsApi.ts apps/gui/src/features/filmium/hooks/useTorrentProgress.ts apps/gui/src/features/filmium/hooks/useTorrentProgress.test.ts
git commit -m "feat(filmium): GUI tipovi, API klijent i SSE hook za torrente"
```

---

### Task 8: Picker fajlova

**Files:**
- Create: `apps/gui/src/features/filmium/components/torrents/FilmiumTorrentFilePicker.tsx`
- Test: `apps/gui/src/features/filmium/components/torrents/FilmiumTorrentFilePicker.test.tsx`

**Interfaces:**
- Consumes: `TorrentFile` iz `types/filmiumTorrents`
- Produces: `FilmiumTorrentFilePicker` sa props `{ files: TorrentFile[]; isBusy?: boolean; onApprove: (selectedIndexes: number[]) => void; onCancel: () => void }`, i izvezena pomoćna `formatBytes(value: number): string`

- [ ] **Step 1: Write the failing test**

`apps/gui/src/features/filmium/components/torrents/FilmiumTorrentFilePicker.test.tsx`:

```typescript
import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import FilmiumTorrentFilePicker, { formatBytes } from "./FilmiumTorrentFilePicker";

import type { TorrentFile } from "../../../../types/filmiumTorrents";


const files: TorrentFile[] = [
  { file_index: 0, path: "Dune.mkv", size_bytes: 2_000_000_000, selected: true },
  { file_index: 1, path: "Dune.nfo", size_bytes: 1024, selected: false },
  { file_index: 2, path: "sample.mkv", size_bytes: 5_000_000, selected: true },
];

describe("FilmiumTorrentFilePicker", () => {
  it("poštuje početno štikliranje sa servera", () => {
    render(
      <FilmiumTorrentFilePicker files={files} onApprove={vi.fn()} onCancel={vi.fn()} />,
    );

    const boxes = screen.getAllByRole("checkbox");
    expect((boxes[0] as HTMLInputElement).checked).toBe(true);
    expect((boxes[1] as HTMLInputElement).checked).toBe(false);
  });

  it("šalje samo štiklirane indekse", () => {
    const onApprove = vi.fn();
    render(
      <FilmiumTorrentFilePicker files={files} onApprove={onApprove} onCancel={vi.fn()} />,
    );

    fireEvent.click(screen.getAllByRole("checkbox")[2]);
    fireEvent.click(screen.getByRole("button", { name: /odobri i skini/i }));

    expect(onApprove).toHaveBeenCalledWith([0]);
  });

  it("dugme je onemogućeno kad ništa nije štiklirano", () => {
    render(
      <FilmiumTorrentFilePicker files={files} onApprove={vi.fn()} onCancel={vi.fn()} />,
    );

    fireEvent.click(screen.getAllByRole("checkbox")[0]);
    fireEvent.click(screen.getAllByRole("checkbox")[2]);

    expect(screen.getByRole("button", { name: /odobri i skini/i })).toBeDisabled();
  });

  it("prikazuje zbir izabranog", () => {
    render(
      <FilmiumTorrentFilePicker files={files} onApprove={vi.fn()} onCancel={vi.fn()} />,
    );

    expect(screen.getByText(/izabrano: 2 od 3/i)).toBeInTheDocument();
  });

  it("formatBytes daje čitljive vrednosti", () => {
    expect(formatBytes(0)).toBe("0 B");
    expect(formatBytes(1024)).toBe("1,0 KB");
    expect(formatBytes(2_000_000_000)).toBe("1,9 GB");
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd apps/gui && npx vitest run src/features/filmium/components/torrents/FilmiumTorrentFilePicker.test.tsx`
Expected: FAIL sa `Failed to resolve import "./FilmiumTorrentFilePicker"`

- [ ] **Step 3: Write the component**

`apps/gui/src/features/filmium/components/torrents/FilmiumTorrentFilePicker.tsx`:

```typescript
import { useMemo, useState } from "react";

import type { TorrentFile } from "../../../../types/filmiumTorrents";


// ==========          FORMATIRANJE          ==========

const UNITS = ["B", "KB", "MB", "GB", "TB"];

/** Veličina fajla u čitljivom obliku, sa zarezom kao decimalnim znakom. */
export function formatBytes(value: number): string {
  if (value <= 0) {
    return "0 B";
  }

  let size = value;
  let unit = 0;

  while (size >= 1024 && unit < UNITS.length - 1) {
    size /= 1024;
    unit += 1;
  }

  const rounded = unit === 0 ? String(Math.round(size)) : size.toFixed(1);
  return `${rounded.replace(".", ",")} ${UNITS[unit]}`;
}


// ==========          PICKER FAJLOVA          ==========

type Props = {
  files: TorrentFile[];
  isBusy?: boolean;
  onApprove: (selectedIndexes: number[]) => void;
  onCancel: () => void;
};

/**
 * Lista fajlova unutar torrenta sa štikliranjem.
 *
 * Početno stanje dolazi sa servera (ekstenzije iz filtera stižu
 * odštiklirane). Neštiklirani fajlovi dobijaju prioritet 0 i ne skidaju se.
 */
function FilmiumTorrentFilePicker({
  files,
  isBusy = false,
  onApprove,
  onCancel,
}: Props) {
  const [selected, setSelected] = useState<Set<number>>(
    () => new Set(files.filter((f) => f.selected).map((f) => f.file_index)),
  );

  const totalSelectedBytes = useMemo(
    () =>
      files
        .filter((file) => selected.has(file.file_index))
        .reduce((sum, file) => sum + file.size_bytes, 0),
    [files, selected],
  );

  const toggle = (fileIndex: number) => {
    setSelected((previous) => {
      const next = new Set(previous);

      if (next.has(fileIndex)) {
        next.delete(fileIndex);
      } else {
        next.add(fileIndex);
      }

      return next;
    });
  };

  return (
    <div className="filmium-torrent-picker">
      <header className="filmium-torrent-picker-head">
        <p className="filmium-torrent-picker-summary">
          {`Izabrano: ${selected.size} od ${files.length} · ${formatBytes(totalSelectedBytes)}`}
        </p>
      </header>

      <ul className="filmium-torrent-picker-list">
        {files.map((file) => (
          <li className="filmium-torrent-picker-row" key={file.file_index}>
            <label className="filmium-torrent-picker-label">
              <input
                checked={selected.has(file.file_index)}
                onChange={() => toggle(file.file_index)}
                type="checkbox"
              />

              <span className="filmium-torrent-picker-path">{file.path}</span>

              <span className="filmium-torrent-picker-size">
                {formatBytes(file.size_bytes)}
              </span>
            </label>
          </li>
        ))}
      </ul>

      <footer className="filmium-torrent-picker-foot">
        <button
          className="filmium-button ghost"
          onClick={onCancel}
          type="button"
        >
          Otkaži
        </button>

        <button
          className="filmium-button primary"
          disabled={selected.size === 0 || isBusy}
          onClick={() => onApprove([...selected].sort((a, b) => a - b))}
          type="button"
        >
          Odobri i skini
        </button>
      </footer>
    </div>
  );
}

export default FilmiumTorrentFilePicker;
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd apps/gui && npx vitest run src/features/filmium/components/torrents/FilmiumTorrentFilePicker.test.tsx`
Expected: PASS, 5 testova

- [ ] **Step 5: Commit**

```bash
git add apps/gui/src/features/filmium/components/torrents
git commit -m "feat(filmium): picker fajlova u torrentu sa stikliranjem"
```

---

### Task 9: Stranica Torrenti, lista, unos i sidebar

**Files:**
- Create: `apps/gui/src/features/filmium/components/torrents/FilmiumTorrentAddBar.tsx`
- Create: `apps/gui/src/features/filmium/components/torrents/FilmiumTorrentList.tsx`
- Create: `apps/gui/src/pages/FilmiumTorrentsPage.tsx`
- Modify: `apps/gui/src/components/layout/Sidebar.tsx` (nova stavka u `filmiumNavigationItems`, uvoz ikone `Download`)
- Modify: `apps/gui/src/App.tsx` (ruta `torrents`, lenji uvoz stranice po uzoru na ostale FILMIUM rute)
- Modify: `apps/gui/src/features/filmium/styles/filmium-pages.css` (stilovi `filmium-torrent-*`)

**Interfaces:**
- Consumes: `useTorrentProgress`, ceo `filmiumTorrentsApi`, `FilmiumTorrentFilePicker`, `formatBytes`
- Produces: `FilmiumTorrentsPage` (default export), `FilmiumTorrentAddBar` sa props `{ onAdd: (source: string) => Promise<void>; isBusy: boolean }`, `FilmiumTorrentList` sa props `{ torrents: Torrent[]; progressByHash: Record<string, TorrentProgress>; onPause: (hash: string) => void; onResume: (hash: string) => void; onRemove: (hash: string) => void; onSelect: (hash: string) => void }`

- [ ] **Step 1: Add the sidebar entry**

U `apps/gui/src/components/layout/Sidebar.tsx`, dodati `Download` u postojeći `lucide-react` uvoz, pa u `filmiumNavigationItems` **između** stavki `filmium-collections` i `filmium-history`:

```typescript
  {
    id: "filmium-torrents",
    label: "Torrenti",
    icon: Download,
    path: "/filmium/torrents",
  },
```

- [ ] **Step 2: Add the route**

U `apps/gui/src/App.tsx`, unutar `<Route path="/filmium" element={<FilmiumWorkspaceProvider />}>`, odmah posle rute `uploads`:

```tsx
          <Route
            path="torrents"
            element={<FilmiumTorrentsPage />}
          />
```

Uvoz stranice dodati uz ostale FILMIUM uvoze stranica, istim stilom koji fajl već koristi za `FilmiumUploadsPage`.

- [ ] **Step 3: Write the add bar**

`apps/gui/src/features/filmium/components/torrents/FilmiumTorrentAddBar.tsx`:

```typescript
import { useState } from "react";


// ==========          UNOS TORRENTA          ==========

type Props = {
  onAdd: (source: string) => Promise<void>;
  isBusy: boolean;
};

/**
 * Polje za magnet link ili putanju do .torrent fajla.
 *
 * Torrent se dodaje PAUZIRAN — skidanje kreće tek posle odobrenja u pickeru.
 */
function FilmiumTorrentAddBar({ onAdd, isBusy }: Props) {
  const [source, setSource] = useState("");

  const submit = async () => {
    const cleaned = source.trim();

    if (!cleaned || isBusy) {
      return;
    }

    await onAdd(cleaned);
    setSource("");
  };

  return (
    <div className="filmium-torrent-addbar">
      <input
        className="filmium-torrent-addbar-input"
        onChange={(event) => setSource(event.target.value)}
        onKeyDown={(event) => {
          if (event.key === "Enter") {
            void submit();
          }
        }}
        placeholder="Nalepi magnet link ili putanju do .torrent fajla"
        type="text"
        value={source}
      />

      <button
        className="filmium-button primary"
        disabled={source.trim().length === 0 || isBusy}
        onClick={() => void submit()}
        type="button"
      >
        Dodaj
      </button>
    </div>
  );
}

export default FilmiumTorrentAddBar;
```

- [ ] **Step 4: Write the list**

`apps/gui/src/features/filmium/components/torrents/FilmiumTorrentList.tsx`:

```typescript
import { Pause, Play, Trash2 } from "lucide-react";

import { formatBytes } from "./FilmiumTorrentFilePicker";

import type {
  Torrent,
  TorrentProgress,
} from "../../../../types/filmiumTorrents";


// ==========          FORMATIRANJE          ==========

/** Preostalo vreme u obliku `1h 05m` ili `45s`; bez podatka daje crticu. */
function formatEta(seconds: number | null): string {
  if (seconds === null || seconds <= 0) {
    return "—";
  }

  const hours = Math.floor(seconds / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);

  if (hours > 0) {
    return `${hours}h ${String(minutes).padStart(2, "0")}m`;
  }

  if (minutes > 0) {
    return `${minutes}m`;
  }

  return `${seconds}s`;
}

const STATUS_LABELS: Record<string, string> = {
  detected: "Zabeležen",
  metadata_fetching: "Čeka metapodatke",
  awaiting_approval: "Čeka odobrenje",
  downloading: "Skida se",
  paused: "Pauziran",
  completed: "Završen",
  error: "Greška",
};


// ==========          LISTA TORRENTA          ==========

type Props = {
  torrents: Torrent[];
  progressByHash: Record<string, TorrentProgress>;
  onPause: (infoHash: string) => void;
  onResume: (infoHash: string) => void;
  onRemove: (infoHash: string) => void;
  onSelect: (infoHash: string) => void;
};

function FilmiumTorrentList({
  torrents,
  progressByHash,
  onPause,
  onResume,
  onRemove,
  onSelect,
}: Props) {
  if (torrents.length === 0) {
    return <p className="filmium-torrent-empty">Nema torrenta u ovom prikazu.</p>;
  }

  return (
    <ul className="filmium-torrent-list">
      {torrents.map((torrent) => {
        const progress = progressByHash[torrent.info_hash];
        const percent = Math.round((progress?.progress ?? 0) * 100);

        return (
          <li className="filmium-torrent-row" key={torrent.info_hash}>
            <button
              className="filmium-torrent-title"
              onClick={() => onSelect(torrent.info_hash)}
              type="button"
            >
              {torrent.name}
            </button>

            <div
              aria-label={`Napredak: ${percent}%`}
              className="filmium-torrent-bar"
              role="progressbar"
              aria-valuenow={percent}
              aria-valuemin={0}
              aria-valuemax={100}
            >
              <span style={{ width: `${percent}%` }} />
            </div>

            <p className="filmium-torrent-meta">
              {`${STATUS_LABELS[torrent.status] ?? torrent.status} · ${percent}% · `}
              {`${formatBytes(progress?.downloadRate ?? 0)}/s · `}
              {`preostalo ${formatEta(progress?.etaSeconds ?? null)} · `}
              {`seed ${progress?.seeds ?? 0} / peer ${progress?.peers ?? 0}`}
            </p>

            {torrent.error_message !== null && (
              <p className="filmium-torrent-error">{torrent.error_message}</p>
            )}

            <div className="filmium-torrent-actions">
              {torrent.status === "downloading" ? (
                <button
                  aria-label="Pauziraj"
                  className="filmium-icon-button"
                  onClick={() => onPause(torrent.info_hash)}
                  type="button"
                >
                  <Pause size={16} />
                </button>
              ) : (
                <button
                  aria-label="Nastavi"
                  className="filmium-icon-button"
                  onClick={() => onResume(torrent.info_hash)}
                  type="button"
                >
                  <Play size={16} />
                </button>
              )}

              <button
                aria-label="Otkaži"
                className="filmium-icon-button danger"
                onClick={() => onRemove(torrent.info_hash)}
                type="button"
              >
                <Trash2 size={16} />
              </button>
            </div>
          </li>
        );
      })}
    </ul>
  );
}

export default FilmiumTorrentList;
```

- [ ] **Step 5: Write the page**

`apps/gui/src/pages/FilmiumTorrentsPage.tsx`:

```typescript
import { useCallback, useEffect, useState } from "react";

import FilmiumTorrentAddBar from "../features/filmium/components/torrents/FilmiumTorrentAddBar";
import FilmiumTorrentFilePicker from "../features/filmium/components/torrents/FilmiumTorrentFilePicker";
import FilmiumTorrentList from "../features/filmium/components/torrents/FilmiumTorrentList";
import { useTorrentProgress } from "../features/filmium/hooks/useTorrentProgress";
import {
  addTorrent,
  approveTorrent,
  getTorrentHealth,
  listTorrentFiles,
  listTorrents,
  pauseTorrent,
  removeTorrent,
  resumeTorrent,
} from "../services/filmiumTorrentsApi";

import type {
  Torrent,
  TorrentFile,
  TorrentHealth,
} from "../types/filmiumTorrents";


// ==========          TABOVI          ==========

type TabId = "active" | "awaiting" | "done";

const TABS: { id: TabId; label: string }[] = [
  { id: "active", label: "Aktivni" },
  { id: "awaiting", label: "Čekaju odobrenje" },
  { id: "done", label: "Završeni" },
];

function belongsTo(tab: TabId, torrent: Torrent): boolean {
  if (tab === "awaiting") {
    return (
      torrent.status === "awaiting_approval"
      || torrent.status === "metadata_fetching"
      || torrent.status === "detected"
    );
  }

  if (tab === "done") {
    return torrent.status === "completed" || torrent.status === "error";
  }

  return torrent.status === "downloading" || torrent.status === "paused";
}


// ==========          STRANICA: TORRENTI          ==========

function FilmiumTorrentsPage() {
  const [tab, setTab] = useState<TabId>("active");
  const [torrents, setTorrents] = useState<Torrent[]>([]);
  const [health, setHealth] = useState<TorrentHealth | null>(null);
  const [pickerHash, setPickerHash] = useState<string | null>(null);
  const [pickerFiles, setPickerFiles] = useState<TorrentFile[]>([]);
  const [isBusy, setIsBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const { progressByHash } = useTorrentProgress();

  const refresh = useCallback(async () => {
    try {
      setTorrents(await listTorrents());
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : String(cause));
    }
  }, []);

  useEffect(() => {
    void refresh();
    void getTorrentHealth().then(setHealth).catch(() => setHealth(null));
  }, [refresh]);

  // Progres stiže svake sekunde; lista se osvežava kad se neki torrent završi.
  useEffect(() => {
    const finished = Object.values(progressByHash).some(
      (item) => item.isFinished,
    );

    if (finished) {
      void refresh();
    }
  }, [progressByHash, refresh]);

  const guard = async (action: () => Promise<unknown>) => {
    setIsBusy(true);
    setError(null);

    try {
      await action();
      await refresh();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : String(cause));
    } finally {
      setIsBusy(false);
    }
  };

  const openPicker = async (infoHash: string) => {
    setError(null);

    try {
      setPickerFiles(await listTorrentFiles(infoHash));
      setPickerHash(infoHash);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : String(cause));
    }
  };

  const visible = torrents.filter((item) => belongsTo(tab, item));

  return (
    <section className="filmium-page filmium-torrents-page">
      <header className="filmium-page-head">
        <h1 className="filmium-page-title">Torrenti</h1>
      </header>

      {health !== null && !health.engine_available && (
        <p className="filmium-torrent-banner">
          {health.message
            ?? "qBittorrent nije dostupan. Proveri da li radi i da li je Web UI uključen."}
        </p>
      )}

      <FilmiumTorrentAddBar
        isBusy={isBusy}
        onAdd={(source) => guard(() => addTorrent(source))}
      />

      <nav className="filmium-torrent-tabs">
        {TABS.map((item) => (
          <button
            className={`filmium-torrent-tab ${tab === item.id ? "active" : ""}`}
            key={item.id}
            onClick={() => setTab(item.id)}
            type="button"
          >
            {item.label}
          </button>
        ))}
      </nav>

      {error !== null && <p className="filmium-torrent-error">{error}</p>}

      {pickerHash !== null ? (
        <FilmiumTorrentFilePicker
          files={pickerFiles}
          isBusy={isBusy}
          onApprove={(indexes) => {
            void guard(async () => {
              await approveTorrent(pickerHash, indexes);
              setPickerHash(null);
              setTab("active");
            });
          }}
          onCancel={() => setPickerHash(null)}
        />
      ) : (
        <FilmiumTorrentList
          onPause={(hash) => void guard(() => pauseTorrent(hash))}
          onRemove={(hash) => void guard(() => removeTorrent(hash))}
          onResume={(hash) => void guard(() => resumeTorrent(hash))}
          onSelect={(hash) => void openPicker(hash)}
          progressByHash={progressByHash}
          torrents={visible}
        />
      )}
    </section>
  );
}

export default FilmiumTorrentsPage;
```

- [ ] **Step 6: Add the styles**

Na kraj `apps/gui/src/features/filmium/styles/filmium-pages.css` dodati:

```css
/* ==========          TORRENTI          ========== */

.filmium-torrents-page {
  display: flex;
  flex-direction: column;
  gap: 18px;
}

.filmium-torrent-addbar {
  display: flex;
  gap: 10px;
}

.filmium-torrent-addbar-input {
  flex: 1;
  padding: 10px 12px;
  border-radius: 8px;
  border: 1px solid rgba(255, 255, 255, 0.12);
  background: rgba(255, 255, 255, 0.04);
  color: inherit;
  font-size: 14px;
}

.filmium-torrent-tabs {
  display: flex;
  gap: 6px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
}

.filmium-torrent-tab {
  padding: 9px 14px;
  border: 0;
  background: transparent;
  color: rgba(255, 255, 255, 0.6);
  font-size: 14px;
  cursor: pointer;
  border-bottom: 2px solid transparent;
}

.filmium-torrent-tab.active {
  color: inherit;
  border-bottom-color: currentColor;
}

.filmium-torrent-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.filmium-torrent-row {
  position: relative;
  padding: 14px 16px;
  border-radius: 10px;
  background: rgba(255, 255, 255, 0.04);
  border: 1px solid rgba(255, 255, 255, 0.07);
}

.filmium-torrent-title {
  border: 0;
  background: transparent;
  color: inherit;
  font-size: 15px;
  font-weight: 600;
  text-align: left;
  padding: 0;
  cursor: pointer;
}

.filmium-torrent-bar {
  margin: 10px 0 8px;
  height: 6px;
  border-radius: 3px;
  background: rgba(255, 255, 255, 0.1);
  overflow: hidden;
}

.filmium-torrent-bar > span {
  display: block;
  height: 100%;
  background: currentColor;
  transition: width 0.3s ease;
}

.filmium-torrent-meta {
  margin: 0;
  font-size: 12px;
  color: rgba(255, 255, 255, 0.6);
}

.filmium-torrent-error {
  margin: 6px 0 0;
  font-size: 12px;
  color: #ff8080;
}

.filmium-torrent-banner {
  padding: 10px 14px;
  border-radius: 8px;
  background: rgba(255, 176, 0, 0.12);
  border: 1px solid rgba(255, 176, 0, 0.3);
  font-size: 13px;
}

.filmium-torrent-empty {
  padding: 24px;
  text-align: center;
  color: rgba(255, 255, 255, 0.45);
}

.filmium-torrent-actions {
  position: absolute;
  top: 12px;
  right: 12px;
  display: flex;
  gap: 6px;
}

/* ---------- picker fajlova ---------- */

.filmium-torrent-picker {
  border-radius: 10px;
  background: rgba(255, 255, 255, 0.04);
  border: 1px solid rgba(255, 255, 255, 0.07);
  padding: 16px;
}

.filmium-torrent-picker-head {
  margin-bottom: 10px;
}

.filmium-torrent-picker-summary {
  margin: 0;
  font-size: 13px;
  color: rgba(255, 255, 255, 0.7);
}

.filmium-torrent-picker-list {
  list-style: none;
  margin: 0 0 14px;
  padding: 0;
  max-height: 360px;
  overflow-y: auto;
}

.filmium-torrent-picker-row {
  border-bottom: 1px solid rgba(255, 255, 255, 0.05);
}

.filmium-torrent-picker-label {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 4px;
  cursor: pointer;
  font-size: 13px;
}

.filmium-torrent-picker-path {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.filmium-torrent-picker-size {
  color: rgba(255, 255, 255, 0.5);
  font-variant-numeric: tabular-nums;
}

.filmium-torrent-picker-foot {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
}

/* ---------- kartica na komandnoj tabli ---------- */

.filmium-torrent-card {
  padding: 16px;
  border-radius: 12px;
  background: rgba(255, 255, 255, 0.04);
  border: 1px solid rgba(255, 255, 255, 0.07);
}

.filmium-torrent-card-head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 10px;
  margin-bottom: 10px;
}

.filmium-torrent-card-head h3 {
  margin: 0;
  font-size: 15px;
}

.filmium-torrent-card-head span {
  font-size: 12px;
  color: rgba(255, 255, 255, 0.6);
}

.filmium-torrent-card-list {
  list-style: none;
  margin: 0 0 12px;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.filmium-torrent-card-list li {
  display: flex;
  justify-content: space-between;
  gap: 10px;
  font-size: 13px;
}

.filmium-torrent-card-name {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.filmium-torrent-card-percent {
  font-variant-numeric: tabular-nums;
  color: rgba(255, 255, 255, 0.6);
}

.filmium-torrent-card-link {
  font-size: 13px;
}
```

Boje su namerno u istim `rgba(255, 255, 255, …)` vrednostima koje fajl već koristi za tamne FILMIUM ekrane; nove CSS promenljive se ne uvode. Ako `.filmium-button`, `.filmium-icon-button`, `.filmium-page` ili `.filmium-page-title` ne postoje u projektu, zameniti ih klasama koje postojeći FILMIUM ekrani koriste za dugmad i naslov stranice umesto pisanja novih.

- [ ] **Step 7: Type check and lint**

Run: `cd apps/gui && npx tsc --noEmit`
Expected: bez grešaka

Run: `cd apps/gui && npx eslint src/features/filmium/components/torrents src/pages/FilmiumTorrentsPage.tsx src/components/layout/Sidebar.tsx`
Expected: bez grešaka

- [ ] **Step 8: Run the GUI test suite**

Run: `cd apps/gui && npx vitest run`
Expected: bez novih padova (`Sidebar.test.tsx` i `AppShell.test.tsx` moraju i dalje da prolaze)

- [ ] **Step 9: Commit**

```bash
git add apps/gui/src
git commit -m "feat(filmium): stranica Torrenti sa tabovima i sidebar stavka"
```

---

### Task 10: Kategorija „Torrenti" u FILMIUM podešavanjima

**Files:**
- Create: `apps/gui/src/features/filmium/components/torrents/FilmiumTorrentSettingsPanel.tsx`
- Modify: `apps/gui/src/pages/FilmiumSettingsPage.tsx` (nova kategorija u nizu `kategorije`)

**Interfaces:**
- Consumes: `getTorrentSettings`, `saveTorrentSettings`, `getTorrentHealth`, tipovi `TorrentSettings`, `TorrentSettingsRequest`
- Produces: `FilmiumTorrentSettingsPanel` (default export, bez props)

- [ ] **Step 1: Write the panel**

`apps/gui/src/features/filmium/components/torrents/FilmiumTorrentSettingsPanel.tsx`:

```typescript
import { useEffect, useState } from "react";

import {
  getTorrentHealth,
  getTorrentSettings,
  saveTorrentSettings,
} from "../../../../services/filmiumTorrentsApi";

import type {
  TorrentHealth,
  TorrentSettings,
} from "../../../../types/filmiumTorrents";


// ==========          PODEŠAVANJA TORRENT MODULA          ==========

/**
 * Četiri grupe: veza sa qBittorrent-om, putanje, ograničenja i ponašanje,
 * plus filter ekstenzija koje su unapred odštiklirane u pickeru.
 *
 * Lozinka se nikad ne čita nazad sa servera — prazno polje znači „ne diraj".
 */
function FilmiumTorrentSettingsPanel() {
  const [settings, setSettings] = useState<TorrentSettings | null>(null);
  const [password, setPassword] = useState("");
  const [health, setHealth] = useState<TorrentHealth | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  useEffect(() => {
    void getTorrentSettings().then(setSettings).catch(() => setSettings(null));
    void getTorrentHealth().then(setHealth).catch(() => setHealth(null));
  }, []);

  if (settings === null) {
    return (
      <section className="cset-panel">
        <p className="cset-panel-sub">Podešavanja torrenta nisu dostupna.</p>
      </section>
    );
  }

  const update = <K extends keyof TorrentSettings>(
    key: K,
    value: TorrentSettings[K],
  ) => {
    setSettings({ ...settings, [key]: value });
  };

  const save = async () => {
    setNotice(null);

    try {
      const { has_password: _ignored, ...rest } = settings;
      const saved = await saveTorrentSettings(
        password ? { ...rest, password } : rest,
      );
      setSettings(saved);
      setPassword("");
      setNotice("Sačuvano.");
      setHealth(await getTorrentHealth());
    } catch (cause) {
      setNotice(cause instanceof Error ? cause.message : String(cause));
    }
  };

  return (
    <section className="cset-panel">
      <header className="cset-panel-head">
        <div>
          <h2 className="cset-panel-title">Torrenti</h2>
          <p className="cset-panel-sub">
            Veza sa qBittorrent-om, putanje i ograničenja preuzimanja.
            Torrent se uvek dodaje pauziran i čeka tvoje odobrenje.
          </p>
        </div>
      </header>

      {health !== null && (
        <p className="cset-panel-sub">
          {health.engine_available
            ? `Veza radi (qBittorrent ${health.version ?? "nepoznata verzija"}).`
            : (health.message ?? "qBittorrent nije dostupan.")}
        </p>
      )}

      <div className="core-settings-row">
        <div className="core-settings-copy">
          <strong>qBittorrent Web UI</strong>
          <span>
            Preporuka: u qBittorrent-u uključi „Bypass authentication for
            clients on localhost" pa korisničko ime i lozinka nisu potrebni.
            Ako ih upišeš, čuvaju se u lokalnoj bazi u čistom tekstu.
          </span>
        </div>
      </div>

      <label className="cset-field">
        Host
        <input
          onChange={(event) => update("host", event.target.value)}
          type="text"
          value={settings.host}
        />
      </label>

      <label className="cset-field">
        Port
        <input
          onChange={(event) => update("port", Number(event.target.value))}
          type="number"
          value={settings.port}
        />
      </label>

      <label className="cset-field">
        Korisničko ime
        <input
          onChange={(event) => update("username", event.target.value)}
          type="text"
          value={settings.username}
        />
      </label>

      <label className="cset-field">
        Lozinka
        <input
          onChange={(event) => setPassword(event.target.value)}
          placeholder={settings.has_password ? "Sačuvana — ostavi prazno da ne menjaš" : ""}
          type="password"
          value={password}
        />
      </label>

      <label className="cset-field">
        Nadzirani folder za .torrent fajlove
        <input
          onChange={(event) => update("watch_folder", event.target.value)}
          type="text"
          value={settings.watch_folder}
        />
      </label>

      <label className="cset-field">
        Odredište preuzimanja
        <input
          onChange={(event) => update("download_path", event.target.value)}
          type="text"
          value={settings.download_path}
        />
      </label>

      <label className="cset-field">
        Maksimalna brzina preuzimanja (kB/s, 0 = bez ograničenja)
        <input
          onChange={(event) =>
            update("max_download_kbs", Number(event.target.value))
          }
          type="number"
          value={settings.max_download_kbs}
        />
      </label>

      <label className="cset-field">
        Maksimalna brzina slanja (kB/s, 0 = bez ograničenja)
        <input
          onChange={(event) =>
            update("max_upload_kbs", Number(event.target.value))
          }
          type="number"
          value={settings.max_upload_kbs}
        />
      </label>

      <label className="cset-field">
        Maksimalno aktivnih torrenta
        <input
          onChange={(event) => update("max_active", Number(event.target.value))}
          type="number"
          value={settings.max_active}
        />
      </label>

      <label className="cset-field">
        <input
          checked={settings.auto_start}
          onChange={(event) => update("auto_start", event.target.checked)}
          type="checkbox"
        />
        Automatski start posle odobrenja
      </label>

      <label className="cset-field">
        <input
          checked={settings.seed_after_complete}
          onChange={(event) =>
            update("seed_after_complete", event.target.checked)
          }
          type="checkbox"
        />
        Nastavi seed posle završetka
      </label>

      <label className="cset-field">
        <input
          checked={settings.delete_source_torrent}
          onChange={(event) =>
            update("delete_source_torrent", event.target.checked)
          }
          type="checkbox"
        />
        Obriši izvorni .torrent fajl po dodavanju
      </label>

      <label className="cset-field">
        Ekstenzije koje se podrazumevano ne štikliraju
        <input
          onChange={(event) =>
            update(
              "unselected_extensions",
              event.target.value.split(",").map((part) => part.trim()),
            )
          }
          type="text"
          value={settings.unselected_extensions.join(", ")}
        />
      </label>

      <button className="filmium-button primary" onClick={() => void save()} type="button">
        Sačuvaj
      </button>

      {notice !== null && <p className="cset-panel-sub">{notice}</p>}
    </section>
  );
}

export default FilmiumTorrentSettingsPanel;
```

- [ ] **Step 2: Register the category**

U `apps/gui/src/pages/FilmiumSettingsPage.tsx`:

- u `lucide-react` uvoz dodati `Download`
- dodati uvoz: `import FilmiumTorrentSettingsPanel from "../features/filmium/components/torrents/FilmiumTorrentSettingsPanel";`
- u niz `kategorije`, posle stavke `prikaz`, umetnuti:

```typescript
    {
      id: "torrenti",
      label: "Torrenti",
      icon: Download,
      render: () => <FilmiumTorrentSettingsPanel />,
    },
```

- [ ] **Step 3: Type check and lint**

Run: `cd apps/gui && npx tsc --noEmit`
Expected: bez grešaka

Run: `cd apps/gui && npx eslint src/features/filmium/components/torrents src/pages/FilmiumSettingsPage.tsx`
Expected: bez grešaka

Ako `.cset-field` ne postoji u postojećem CSS-u, dodati ga u `apps/gui/src/styles/` uz ostale `cset-` klase: label u koloni, razmak 6px, input puna širina sa istim okvirom kao ostala CORE polja.

- [ ] **Step 4: Commit**

```bash
git add apps/gui/src
git commit -m "feat(filmium): kategorija Torrenti u FILMIUM podesavanjima"
```

---

### Task 11: Kartica na CORE Dashboard-u

**Files:**
- Create: `apps/gui/src/features/filmium/components/torrents/FilmiumTorrentDashboardCard.tsx`
- Modify: `apps/gui/src/pages/DashboardPage.tsx`

**Interfaces:**
- Consumes: `useTorrentProgress`, `listTorrents`, `formatBytes`
- Produces: `FilmiumTorrentDashboardCard` (default export, bez props)

- [ ] **Step 1: Write the card**

`apps/gui/src/features/filmium/components/torrents/FilmiumTorrentDashboardCard.tsx`:

```typescript
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { formatBytes } from "./FilmiumTorrentFilePicker";
import { useTorrentProgress } from "../../hooks/useTorrentProgress";
import { listTorrents } from "../../../../services/filmiumTorrentsApi";

import type { Torrent } from "../../../../types/filmiumTorrents";


// ==========          DASHBOARD: AKTIVNA PREUZIMANJA          ==========

/**
 * Kompaktan pregled aktivnih torrenta na CORE komandnoj tabli.
 *
 * Čita isti SSE strim kao stranica Torrenti. Kad nema aktivnih preuzimanja
 * kartica se ne prikazuje — komandna tabla ostaje čista.
 */
function FilmiumTorrentDashboardCard() {
  const [torrents, setTorrents] = useState<Torrent[]>([]);
  const { progressByHash } = useTorrentProgress();

  useEffect(() => {
    void listTorrents().then(setTorrents).catch(() => setTorrents([]));
  }, []);

  const active = torrents.filter(
    (item) => item.status === "downloading" || item.status === "paused",
  );

  if (active.length === 0) {
    return null;
  }

  const totalRate = active.reduce(
    (sum, item) => sum + (progressByHash[item.info_hash]?.downloadRate ?? 0),
    0,
  );

  return (
    <article className="filmium-torrent-card">
      <header className="filmium-torrent-card-head">
        <h3>Torrenti</h3>
        <span>{`${active.length} aktivnih · ${formatBytes(totalRate)}/s`}</span>
      </header>

      <ul className="filmium-torrent-card-list">
        {active.slice(0, 3).map((item) => {
          const percent = Math.round(
            (progressByHash[item.info_hash]?.progress ?? 0) * 100,
          );

          return (
            <li key={item.info_hash}>
              <span className="filmium-torrent-card-name">{item.name}</span>
              <span className="filmium-torrent-card-percent">{`${percent}%`}</span>
            </li>
          );
        })}
      </ul>

      <Link className="filmium-torrent-card-link" to="/filmium/torrents">
        Otvori Torrente
      </Link>
    </article>
  );
}

export default FilmiumTorrentDashboardCard;
```

- [ ] **Step 2: Mount it on the dashboard**

U `apps/gui/src/pages/DashboardPage.tsx` dodati uvoz:

```typescript
import FilmiumTorrentDashboardCard from "../features/filmium/components/torrents/FilmiumTorrentDashboardCard";
```

i postaviti `<FilmiumTorrentDashboardCard />` u mrežu kartica komandne table, uz postojeće kartice domena. Kartica sama vraća `null` kad nema aktivnih preuzimanja, pa ne treba dodatni uslov.

- [ ] **Step 3: Verify the card styles**

Stilovi `.filmium-torrent-card*` su već dodati u Tasku 9, Step 6. Ovde samo
proveriti da kartica izgleda uredno na komandnoj tabli i ne dodavati ih ponovo.

- [ ] **Step 4: Type check and run the GUI suite**

Run: `cd apps/gui && npx tsc --noEmit`
Expected: bez grešaka

Run: `cd apps/gui && npx vitest run`
Expected: bez novih padova

- [ ] **Step 5: Commit**

```bash
git add apps/gui/src
git commit -m "feat(filmium): kartica aktivnih torrenta na CORE Dashboard-u"
```

---

### Task 12: Zaokruživanje — dokumentacija i puna provera

**Files:**
- Modify: `docs/DEPENDENCIES.md`
- Modify: `NADOGRADNJE/TODO - Prevodni Sidebar + KALIMA.md`

- [ ] **Step 1: Document the dependency**

U `docs/DEPENDENCIES.md`, u odeljak sa Python zavisnostima, dodati red za `qbittorrent-api`: opcionalna zavisnost, potrebna samo za FILMIUM torrent modul, zahteva instaliran qBittorrent sa uključenim Web UI-jem, instalacija `python -m pip install qbittorrent-api`. Napomenuti i preporuku da se u qBittorrent-u uključi *Bypass authentication for clients on localhost*, pa lozinka nije potrebna.

- [ ] **Step 2: Tick off the TODO**

U `NADOGRADNJE/TODO - Prevodni Sidebar + KALIMA.md`, u odeljku `1C`, staviti `[x]` na stavku Modula 6 i dopisati jednu liniju: plan je izvršen, engine je qBittorrent Web API (libtorrent nije dostupan za Python 3.14).

- [ ] **Step 3: Run every check**

Run: `./.venv/Scripts/python.exe -m pytest -q`
Expected: sve prolazi

Run: `cd apps/gui && npx tsc --noEmit`
Expected: bez grešaka

Run: `cd apps/gui && npx vitest run`
Expected: sve prolazi

Run: `cd apps/gui && npx eslint src`
Expected: bez grešaka

- [ ] **Step 4: Manual smoke test**

Uz pokrenut qBittorrent sa uključenim Web UI-jem:

1. FILMIUM podešavanja → Torrenti: upisati host, port, nadzirani folder i odredište, sačuvati. Poruka mora da potvrdi da veza radi i da ispiše verziju.
2. Sidebar → Torrenti: nalepiti magnet link poznatog slobodnog torrenta, pritisnuti „Dodaj".
3. Tab „Čekaju odobrenje": kliknuti na torrent, proveriti da su `.nfo` i `.txt` unapred odštiklirani.
4. „Odobri i skini": torrent prelazi u tab „Aktivni", traka se pomera, brzina i preostalo vreme se menjaju svake sekunde.
5. CORE Dashboard: kartica „Torrenti" pokazuje isto preuzimanje.
6. Sačekati kraj: torrent prelazi u „Završeni", stiže OS notifikacija.
7. U qBittorrent-u proveriti da neštiklirani fajlovi imaju prioritet „Do not download".

- [ ] **Step 5: Commit**

```bash
git add docs/DEPENDENCIES.md "NADOGRADNJE/TODO - Prevodni Sidebar + KALIMA.md"
git commit -m "docs(filmium): zavisnost qbittorrent-api i zatvaranje Modula 6"
```
