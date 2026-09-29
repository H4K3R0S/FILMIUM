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
