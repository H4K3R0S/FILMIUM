from __future__ import annotations

import os
from collections.abc import Iterator
from contextlib import contextmanager

import psycopg
from pgvector.psycopg import register_vector
from psycopg.rows import dict_row

from core.rag.config import load_rag_config


def resolve_dsn(dsn: str | None = None) -> str:
    """Bira DSN: eksplicitni argument > RAG_TEST_DSN > konfiguracija."""
    if dsn is not None:
        return dsn
    test_dsn = os.environ.get("RAG_TEST_DSN")
    if test_dsn:
        return test_dsn
    return load_rag_config().dsn


def _try_register_vector(connection: psycopg.Connection) -> None:
    """Registruje pgvector tipove ako 'vector' ekstenzija postoji.

    Pre prve migracije (koja kreira ekstenziju) tip jos ne postoji, pa se
    registracija tiho preskace. Sve konekcije posle migracije je uhvate.
    """
    try:
        register_vector(connection)
    except psycopg.ProgrammingError:
        connection.rollback()


@contextmanager
def rag_connection(dsn: str | None = None) -> Iterator[psycopg.Connection]:
    """Kontrolisana konekcija ka RAG Postgres bazi.

    Potvrdjuje uspesne izmene, ponistava neuspesne i uvek zatvara konekciju.
    """
    resolved = resolve_dsn(dsn)
    # Podrazumevani connect_timeout da mrtva/filtrirana baza NE blokira zauvek
    # (boot ćelije, ingest, retrieve). Ne dira ako DSN već zadaje timeout.
    kwargs: dict = {"row_factory": dict_row}
    if "connect_timeout" not in resolved:
        kwargs["connect_timeout"] = 5
    connection = psycopg.connect(resolved, **kwargs)
    try:
        _try_register_vector(connection)
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()
