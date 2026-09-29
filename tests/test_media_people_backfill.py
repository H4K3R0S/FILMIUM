"""Catch-up glumaca: naslovi sa cast_names bez `filmium_media_people` se dopunjavaju.

Testira novu logiku iz `TmdbPeopleImportJob` (bug: `media_people` je bila izgrađena
samo za prvih ATOM_BATCH_DEFAULT naslova, pa je film-stranica krila glumce).
"""
from __future__ import annotations

import contextlib
import sqlite3
import threading

import pytest

from core.cell.jobs import JobContext
from core.domains.filmium.jobs import tmdb_people_import as mod
from core.domains.filmium.jobs.tmdb_people_import import TmdbPeopleImportJob


@pytest.fixture
def temp_catalog(tmp_path, monkeypatch):
    db = tmp_path / "filmium.db"
    con = sqlite3.connect(db)
    con.executescript(
        """
        CREATE TABLE filmium_media_items (id INTEGER PRIMARY KEY, media_type TEXT, cast_names TEXT);
        INSERT INTO filmium_media_items VALUES
            (1, 'movie', '["A","B"]'),   -- ima cast, bez linkova -> nedostaje
            (2, 'movie', '[]'),          -- prazan cast -> preskoči
            (3, 'movie', '["C"]'),       -- ima cast, već linkovan -> preskoči
            (4, 'movie', NULL);          -- nema cast -> preskoči
        """
    )
    con.commit()
    con.close()

    @contextlib.contextmanager
    def _fake_conn():
        c = sqlite3.connect(db)
        c.row_factory = sqlite3.Row
        try:
            yield c
            c.commit()
        finally:
            c.close()

    monkeypatch.setattr(mod, "_catalog_connection", _fake_conn)
    # obeleži da naslov 3 već ima link (posle _ensure_people_tables kreira tabelu)
    return db, _fake_conn


def _seed_existing_link(fake_conn, media_id: int) -> None:
    job = TmdbPeopleImportJob()
    with fake_conn() as con:
        job._ensure_people_tables(con)
        con.execute(
            "INSERT OR IGNORE INTO filmium_people(name, slug, created_at, updated_at) "
            "VALUES ('C','c','x','x')"
        )
        pid = con.execute("SELECT id FROM filmium_people WHERE slug='c'").fetchone()["id"]
        con.execute(
            "INSERT INTO filmium_media_people(media_id, person_id, role) VALUES (?,?, 'glumac')",
            (media_id, pid),
        )


def test_missing_ids_only_uncovered_with_cast(temp_catalog):
    _db, fake_conn = temp_catalog
    _seed_existing_link(fake_conn, 3)
    job = TmdbPeopleImportJob()
    assert job._media_ids_missing_people() == [1]  # samo 1 (2=[], 3 linkovan, 4 NULL)


def test_backfill_calls_regenerate_for_missing(temp_catalog, monkeypatch):
    _db, fake_conn = temp_catalog
    _seed_existing_link(fake_conn, 3)
    job = TmdbPeopleImportJob()
    calls: list[list[int]] = []
    monkeypatch.setattr(job, "_regenerate_atoms", lambda ctx, media_ids=None: calls.append(media_ids) or 0)
    ctx = JobContext(job.id, "filmium", threading.Event(), lambda e: None)
    n = job._backfill_missing_media_people(ctx)
    assert n == 1
    assert calls == [[1]]


def test_backfill_noop_when_all_covered(temp_catalog, monkeypatch):
    _db, fake_conn = temp_catalog
    _seed_existing_link(fake_conn, 3)
    _seed_existing_link(fake_conn, 1)  # sad i 1 ima link
    job = TmdbPeopleImportJob()
    monkeypatch.setattr(job, "_regenerate_atoms", lambda *a, **k: 0)
    ctx = JobContext(job.id, "filmium", threading.Event(), lambda e: None)
    assert job._backfill_missing_media_people(ctx) == 0
