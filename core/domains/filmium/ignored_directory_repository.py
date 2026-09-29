from pathlib import Path

from core.database import core_database_connection

# ==========          IGNORISANI FOLDERI          ==========

class IgnoredDirectoryRepository:
    """Čuva foldere koje korisnik trajno izuzima iz skeniranja."""

    def __init__(self, database_path: Path | None = None) -> None:
        self._database_path = database_path

    def add(
        self,
        library_root_id: int,
        relative_directory: str,
    ) -> None:
        """Dodaje folder u listu ignorisanih (bez dupliranja)."""

        with core_database_connection(self._database_path) as connection:
            connection.execute(
                """
                INSERT OR IGNORE INTO filmium_ignored_directories (
                    library_root_id,
                    relative_directory
                )
                VALUES (?, ?)
                """,
                (library_root_id, relative_directory),
            )

    def remove(
        self,
        library_root_id: int,
        relative_directory: str,
    ) -> bool:
        """Uklanja folder iz liste ignorisanih; True ako je postojao."""

        with core_database_connection(self._database_path) as connection:
            cursor = connection.execute(
                """
                DELETE FROM filmium_ignored_directories
                WHERE library_root_id = ?
                  AND relative_directory = ?
                """,
                (library_root_id, relative_directory),
            )

        return cursor.rowcount > 0

    def list_for_root(
        self,
        library_root_id: int,
    ) -> tuple[str, ...]:
        """Vraća sve ignorisane relativne foldere jedne biblioteke."""

        with core_database_connection(self._database_path) as connection:
            rows = connection.execute(
                """
                SELECT relative_directory
                FROM filmium_ignored_directories
                WHERE library_root_id = ?
                ORDER BY relative_directory COLLATE NOCASE
                """,
                (library_root_id,),
            ).fetchall()

        return tuple(str(row["relative_directory"]) for row in rows)
