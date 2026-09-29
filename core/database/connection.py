import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from core.foundation.paths import core_paths

# ==========          DATABASE KONEKCIJA          ==========

@contextmanager
def core_database_connection(
    database_path: Path | None = None,
) -> Iterator[sqlite3.Connection]:
    """
    Otvara kontrolisanu konekciju prema CORE SQLite bazi.

    Konekcija automatski potvrđuje uspešne izmene, poništava neuspešne
    izmene i uvek se zatvara nakon korišćenja.

    Args:
        database_path: Opciona putanja baze, prvenstveno namenjena testovima.

    Yields:
        Aktivna SQLite konekcija.
    """
    target_path = database_path or core_paths.core_database
    target_path.parent.mkdir(parents=True, exist_ok=True)

    connection = sqlite3.connect(target_path, timeout=5.0)
    connection.row_factory = sqlite3.Row

    try:
        # SQLite strane ključeve mora eksplicitno uključiti za svaku konekciju.
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 5000")
        # Manje fsync-ova = brži upisi na sporom disku (bezbedno za katalog;
        # rizik je samo gubitak poslednjeg upisa pri nestanku struje). WAL se
        # NE koristi jer baza ume da živi na NTFS disku gde WAL (deljena
        # memorija/-shm) ume da zakaže.
        connection.execute("PRAGMA synchronous = NORMAL")

        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()