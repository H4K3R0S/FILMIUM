from __future__ import annotations

from dataclasses import dataclass

import psycopg


@dataclass(frozen=True)
class RagMigration:
    """Jedna nepromenljiva verzija RAG seme."""

    version: int
    name: str
    statements: tuple[str, ...]


def apply_rag_migrations(
    connection: psycopg.Connection,
    migrations: tuple[RagMigration, ...],
) -> None:
    """Primenjuje neizvrsene migracije po rastucoj verziji."""
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS rag_schema_migrations (
            version integer PRIMARY KEY,
            name text NOT NULL,
            applied_at timestamptz NOT NULL DEFAULT now()
        )
        """
    )

    for migration in sorted(migrations, key=lambda m: m.version):
        postojeca = connection.execute(
            "SELECT name FROM rag_schema_migrations WHERE version = %s",
            (migration.version,),
        ).fetchone()

        if postojeca is not None:
            if postojeca["name"] != migration.name:
                raise RuntimeError(
                    f"Migracija {migration.version} preimenovana: "
                    f"'{postojeca['name']}' -> '{migration.name}'"
                )
            continue

        for statement in migration.statements:
            connection.execute(statement)
        connection.execute(
            "INSERT INTO rag_schema_migrations (version, name) VALUES (%s, %s)",
            (migration.version, migration.name),
        )
    connection.commit()
