import sqlite3
from dataclasses import dataclass

# ==========          MODEL MIGRACIJE          ==========

@dataclass(frozen=True)
class DatabaseMigration:
    """
    Predstavlja jednu nepromenljivu verziju database šeme.

    Svaki CORE domen ima sopstveni scope i nezavisno numerisanje verzija.
    """

    scope: str
    version: int
    name: str
    statements: tuple[str, ...]


# ==========          MIGRATION SISTEM          ==========

def apply_database_migrations(
    connection: sqlite3.Connection,
    migrations: tuple[DatabaseMigration, ...],
) -> None:
    """
    Primenjuje database migracije koje ranije nisu izvršene.

    Već izvršene migracije se ne ponavljaju. Ako je naziv prethodno
    izvršene migracije naknadno promenjen, pokretanje se prekida.

    Args:
        connection: Aktivna CORE SQLite konekcija.
        migrations: Migracije koje treba proveriti i primeniti.
    """
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS core_schema_migrations (
            scope TEXT NOT NULL,
            version INTEGER NOT NULL,
            name TEXT NOT NULL,
            applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (scope, version)
        )
        """
    )

    for migration in sorted(
        migrations,
        key=lambda item: (item.scope, item.version),
    ):
        applied_migration = connection.execute(
            """
            SELECT name
            FROM core_schema_migrations
            WHERE scope = ? AND version = ?
            """,
            (migration.scope, migration.version),
        ).fetchone()

        if applied_migration is not None:
            if applied_migration["name"] != migration.name:
                raise RuntimeError(
                    "Prethodno izvršena migracija je naknadno promenjena: "
                    f"{migration.scope}:{migration.version}"
                )

            continue

        for statement in migration.statements:
            connection.execute(statement)

        connection.execute(
            """
            INSERT INTO core_schema_migrations (scope, version, name)
            VALUES (?, ?, ?)
            """,
            (migration.scope, migration.version, migration.name),
        )