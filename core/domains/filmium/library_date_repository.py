import sqlite3
from datetime import datetime
from pathlib import Path

from core.database import core_database_connection
from core.domains.filmium.library_date_models import (
    MediaLibraryDateRecord,
)
from core.domains.filmium.models import MediaType

# ==========          LIBRARY DATE REPOSITORY          ==========

class LibraryDateRepository:
    """Cuva korisnicki datum ulaska sadrzaja u biblioteku."""

    def __init__(self, database_path: Path | None = None) -> None:
        self._database_path = database_path

    def get(self, media_id: int) -> MediaLibraryDateRecord | None:
        """Ucitava datum jednog FILMIUM sadrzaja."""

        with core_database_connection(self._database_path) as connection:
            row = self._get_row(connection, media_id)

        return None if row is None else self._row_to_record(row)

    def update(
        self,
        media_id: int,
        library_added_at: datetime,
    ) -> MediaLibraryDateRecord | None:
        """Menja samo korisnicki datum, bez promene created_at polja."""

        with core_database_connection(self._database_path) as connection:
            cursor = connection.execute(
                """
                UPDATE filmium_media_items
                SET
                    library_added_at = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (
                    library_added_at.isoformat(
                        sep=" ",
                        timespec="seconds",
                    ),
                    media_id,
                ),
            )

            if cursor.rowcount == 0:
                return None

            row = self._get_row(connection, media_id)

        return None if row is None else self._row_to_record(row)

    def list_recent(
        self,
        limit: int,
    ) -> tuple[MediaLibraryDateRecord, ...]:
        """Vraca najnovije dodat sadrzaj po korisnickom datumu."""

        with core_database_connection(self._database_path) as connection:
            rows = connection.execute(
                """
                SELECT
                    id,
                    title,
                    media_type,
                    release_year,
                    library_added_at
                FROM filmium_media_items
                WHERE library_added_at IS NOT NULL
                ORDER BY library_added_at DESC, id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()

        return tuple(self._row_to_record(row) for row in rows)

    @staticmethod
    def _get_row(
        connection: sqlite3.Connection,
        media_id: int,
    ) -> sqlite3.Row | None:
        return connection.execute(
            """
            SELECT
                id,
                title,
                media_type,
                release_year,
                library_added_at
            FROM filmium_media_items
            WHERE id = ?
            """,
            (media_id,),
        ).fetchone()

    @staticmethod
    def _row_to_record(
        row: sqlite3.Row,
    ) -> MediaLibraryDateRecord:
        return MediaLibraryDateRecord(
            media_id=int(row["id"]),
            title=str(row["title"]),
            media_type=MediaType(row["media_type"]),
            release_year=(
                None
                if row["release_year"] is None
                else int(row["release_year"])
            ),
            library_added_at=datetime.fromisoformat(
                row["library_added_at"]
            ),
        )