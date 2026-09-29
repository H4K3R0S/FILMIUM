"""Bootstrap RAG baze ćelije: napravi SOPSTVENU bazu + primeni migracije.

Svaka ćelija ima svoju bazu `rag_<domen>` na Postgres serveru (podrazumevano
isti pgvector server, `db.name` po domenu iz `config/rag.json`). Ovaj modul na
podizanju ćelije osigura da ta baza postoji i da je migrirana.

Sve je TOLERANTNO: nema `config/rag.json`, server dole, nalog bez `CREATEDB`,
bilo koja greška → proguta se i zabeleži; ćelija se diže i bez RAG-a (RAG je
opcion — Agent tada radi bez konteksta).
"""
from __future__ import annotations

import json
import logging
import os
from pathlib import Path

_logger = logging.getLogger(__name__)


def _rag_config_path() -> Path:
    from core.foundation.paths import core_paths

    return core_paths.root / "config" / "rag.json"


def _db_params() -> dict | None:
    """Parametri baze iz `config/rag.json` (uz env override), ili None ako nema."""

    path = _rag_config_path()
    if not path.is_file():
        return None
    try:
        db = json.loads(path.read_text(encoding="utf-8"))["db"]
    except (OSError, ValueError, KeyError):
        return None
    return {
        "host": os.environ.get("RAG_DB_HOST", db["host"]),
        "port": str(os.environ.get("RAG_DB_PORT", db["port"])),
        "name": db["name"],
        "user": db["user"],
        "password": db.get("password") or os.environ.get("RAG_DB_PASSWORD", ""),
    }


def _dsn(params: dict, dbname: str) -> str:
    return (
        f"host={params['host']} port={params['port']} dbname={dbname} "
        f"user={params['user']} password={params['password']}"
    ).strip()


def _database_exists(params: dict) -> bool:
    import psycopg

    with psycopg.connect(_dsn(params, "postgres"), autocommit=True, connect_timeout=2) as conn:
        row = conn.execute(
            "SELECT 1 FROM pg_database WHERE datname = %s", (params["name"],)
        ).fetchone()
        return row is not None


def _create_database(params: dict) -> None:
    import psycopg
    from psycopg import sql

    # CREATE DATABASE ne sme u transakciji — autocommit veza ka `postgres` bazi.
    with psycopg.connect(_dsn(params, "postgres"), autocommit=True, connect_timeout=2) as conn:
        conn.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(params["name"])))


def ensure_cell_rag_db() -> bool:
    """Osigura da ćelijska RAG baza postoji i da je migrirana.

    Returns:
        True ako je RAG baza spremna (postoji + migrirana); False ako je RAG
        isključen (nema configa) ili bootstrap nije uspeo (greška se proguta).
    """
    params = _db_params()
    if params is None:
        _logger.info("RAG bootstrap: nema config/rag.json — RAG isključen.")
        return False
    try:
        if not _database_exists(params):
            try:
                _create_database(params)
                _logger.info("RAG bootstrap: napravljena baza %s.", params["name"])
            except Exception:
                if not _database_exists(params):
                    raise  # stvarni neuspeh (npr. nema CREATEDB) — u spoljni except

        from core.rag.runtime import initialize_rag_database

        initialize_rag_database(_dsn(params, params["name"]))
        return True
    except Exception as error:  # noqa: BLE001 — RAG je opcion; nikad ne ruši ćeliju
        _logger.warning("RAG bootstrap nije uspeo (%s) — RAG isključen.", error)
        return False
