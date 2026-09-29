"""OS-most: prepoznavanje diska koji drži biblioteku (proba) + sinhronizacija korena.

Reprodukuje bug: app na sistemskom disku, biblioteka na odvojenom disku → koren u bazi
je bio pogrešan (`/`), a alat ga sad popravlja na stvarni mount (validacija probom).
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from core.domains.filmium import os_library_bridge as bridge


def _make_db(db_path: Path, root_path: str, snapshot: str, rel_dir: str) -> None:
    con = sqlite3.connect(db_path)
    con.executescript(
        """
        CREATE TABLE filmium_library_roots (id INTEGER PRIMARY KEY, path TEXT, updated_at TEXT);
        CREATE TABLE filmium_media_sources (id INTEGER PRIMARY KEY, root_path_snapshot TEXT, relative_directory TEXT);
        """
    )
    con.execute("INSERT INTO filmium_library_roots (id, path) VALUES (1, ?)", (root_path,))
    con.execute(
        "INSERT INTO filmium_media_sources (id, root_path_snapshot, relative_directory) VALUES (1, ?, ?)",
        (snapshot, rel_dir),
    )
    con.commit()
    con.close()


@pytest.fixture
def library(tmp_path):
    """Sintetički 'disk' sa strukturom biblioteke + baza sa pogrešnim korenom '/'."""
    disk = tmp_path / "mnt" / "FILMIUM"
    rel = "Strano/Filmovi/Avengers 1 (2012)"
    (disk / rel).mkdir(parents=True)
    db = tmp_path / "filmium.db"
    _make_db(db, root_path="/", snapshot="/", rel_dir=rel)
    return disk, db, rel


def test_holds_library_true_false(library):
    disk, _db, rel = library
    assert bridge._holds_library(str(disk), [rel]) is True
    assert bridge._holds_library("/", [rel]) is False           # '/'+rel ne postoji
    assert bridge._holds_library(str(disk), ["Nema/Ovog"]) is False


def test_find_library_root_probes(monkeypatch, library):
    disk, db, _rel = library
    # kandidat-mountovi: nevažeći pa pravi disk
    monkeypatch.setattr(bridge, "_candidate_roots", lambda: ["/", str(disk)])
    assert bridge.find_library_root(str(db)) == str(disk)


def test_sync_fixes_wrong_root(monkeypatch, library):
    disk, db, _rel = library
    monkeypatch.setattr(bridge, "_candidate_roots", lambda: ["/", str(disk)])
    changed = bridge.sync_library_roots_for_current_os(str(db), cell_root="/tmp")
    assert changed >= 2  # library_roots.path + root_path_snapshot
    con = sqlite3.connect(db)
    assert con.execute("SELECT path FROM filmium_library_roots WHERE id=1").fetchone()[0] == str(disk)
    assert con.execute("SELECT root_path_snapshot FROM filmium_media_sources WHERE id=1").fetchone()[0] == str(disk)
    con.close()


def test_sync_idempotent(monkeypatch, library):
    disk, db, _rel = library
    monkeypatch.setattr(bridge, "_candidate_roots", lambda: [str(disk)])
    bridge.sync_library_roots_for_current_os(str(db), cell_root="/tmp")
    # drugi put: koren je već ispravan → 0 izmena
    assert bridge.sync_library_roots_for_current_os(str(db), cell_root="/tmp") == 0


def test_sync_noop_when_disk_absent(monkeypatch, library):
    _disk, db, _rel = library
    # nijedan kandidat ne drži biblioteku (disk „nije montiran") → ne diraj bazu
    monkeypatch.setattr(bridge, "_candidate_roots", lambda: ["/"])
    changed = bridge.sync_library_roots_for_current_os(str(db), cell_root="/tmp")
    assert changed == 0
    con = sqlite3.connect(db)
    assert con.execute("SELECT path FROM filmium_library_roots WHERE id=1").fetchone()[0] == "/"
    con.close()
