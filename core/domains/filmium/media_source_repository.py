import sqlite3
from datetime import datetime
from pathlib import Path

from core.database import core_database_connection
from core.domains.filmium.library_models import (
    MediaFileRole,
    MediaFileStatus,
)
from core.domains.filmium.media_source_models import (
    MediaFile,
    MediaFileCreate,
    MediaSource,
    MediaSourceCreate,
)

# ==========          MEDIA SOURCE REPOSITORY          ==========

class MediaSourceRepository:
    """Cuva fizicke izvore i njihove datoteke u CORE bazi."""

    def __init__(self, database_path: Path | None = None) -> None:
        self._database_path = database_path

    def create(self, item: MediaSourceCreate) -> MediaSource:
        """Upisuje izvor i sve njegove datoteke u jednoj transakciji."""

        with core_database_connection(self._database_path) as connection:
            cursor = connection.execute(
                """
                INSERT INTO filmium_media_sources (
                    media_id,
                    library_root_id,
                    root_path_snapshot,
                    relative_directory,
                    manifest_path,
                    availability_status,
                    last_verified_at
                )
                VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                """,
                (
                    item.media_id,
                    item.library_root_id,
                    item.root_path_snapshot,
                    item.relative_directory,
                    item.manifest_path,
                    item.availability_status.value,
                ),
            )

            if cursor.lastrowid is None:
                raise RuntimeError(
                    "SQLite nije vratio ID novog FILMIUM izvora."
                )

            source_id = int(cursor.lastrowid)
            self._insert_files(connection, source_id, item.files)
            row = self._get_source_row(connection, source_id)
            files = self._load_files(connection, source_id)

        if row is None:
            raise RuntimeError(
                "Novi FILMIUM izvor nije pronadjen nakon upisa."
            )

        return self._row_to_source(row, files)

    def get(self, source_id: int) -> MediaSource | None:
        """Ucitava izvor zajedno sa njegovim datotekama."""

        with core_database_connection(self._database_path) as connection:
            row = self._get_source_row(connection, source_id)

            if row is None:
                return None

            files = self._load_files(connection, source_id)

        return self._row_to_source(row, files)

    def list_for_media(self, media_id: int) -> tuple[MediaSource, ...]:
        """Vraca sve fizicke izvore jednog kataloskog sadrzaja."""

        with core_database_connection(self._database_path) as connection:
            rows = connection.execute(
                """
                SELECT *
                FROM filmium_media_sources
                WHERE media_id = ?
                ORDER BY
                    CASE availability_status
                        WHEN 'available' THEN 0
                        WHEN 'offline' THEN 1
                        ELSE 2
                    END,
                    id
                """,
                (media_id,),
            ).fetchall()

            sources = tuple(
                self._row_to_source(
                    row,
                    self._load_files(connection, int(row["id"])),
                )
                for row in rows
            )

        return sources

    def replace_files(
        self,
        source_id: int,
        files: tuple[MediaFileCreate, ...],
    ) -> MediaSource | None:
        """Atomski menja indeks datoteka jednog izvora."""

        with core_database_connection(self._database_path) as connection:
            if self._get_source_row(connection, source_id) is None:
                return None

            connection.execute(
                """
                DELETE FROM filmium_media_files
                WHERE source_id = ?
                """,
                (source_id,),
            )
            self._insert_files(connection, source_id, files)
            connection.execute(
                """
                UPDATE filmium_media_sources
                SET
                    last_verified_at = CURRENT_TIMESTAMP,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (source_id,),
            )

            row = self._get_source_row(connection, source_id)
            loaded_files = self._load_files(connection, source_id)

        return (
            None
            if row is None
            else self._row_to_source(row, loaded_files)
        )

    def set_availability(
        self,
        source_id: int,
        status: MediaFileStatus,
    ) -> MediaSource | None:
        """Belezi dostupnost izvora i po potrebi njegovih datoteka."""

        with core_database_connection(self._database_path) as connection:
            cursor = connection.execute(
                """
                UPDATE filmium_media_sources
                SET
                    availability_status = ?,
                    last_verified_at = CURRENT_TIMESTAMP,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (status.value, source_id),
            )

            if cursor.rowcount == 0:
                return None

            # Povratak izvora online ne dokazuje da se svaka datoteka
            # ponovo pojavila. Precizne statuse tada daje novo skeniranje.
            if status is not MediaFileStatus.AVAILABLE:
                connection.execute(
                    """
                    UPDATE filmium_media_files
                    SET
                        file_status = ?,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE source_id = ?
                    """,
                    (status.value, source_id),
                )

            row = self._get_source_row(connection, source_id)
            files = self._load_files(connection, source_id)

        return None if row is None else self._row_to_source(row, files)

    def delete(self, source_id: int) -> bool:
        """Brise samo bazni zapis izvora i njegove indeksirane datoteke."""

        with core_database_connection(self._database_path) as connection:
            cursor = connection.execute(
                """
                DELETE FROM filmium_media_sources
                WHERE id = ?
                """,
                (source_id,),
            )

        return cursor.rowcount > 0

    @staticmethod
    def _insert_files(
        connection: sqlite3.Connection,
        source_id: int,
        files: tuple[MediaFileCreate, ...],
    ) -> None:
        connection.executemany(
            """
            INSERT INTO filmium_media_files (
                source_id,
                role,
                relative_path,
                language,
                size_bytes,
                modified_at,
                file_status
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                (
                    source_id,
                    item.role.value,
                    item.relative_path,
                    item.language,
                    item.size_bytes,
                    (
                        None
                        if item.modified_at is None
                        else item.modified_at.isoformat()
                    ),
                    item.file_status.value,
                )
                for item in files
            ),
        )

    @staticmethod
    def _get_source_row(
        connection: sqlite3.Connection,
        source_id: int,
    ) -> sqlite3.Row | None:
        return connection.execute(
            """
            SELECT *
            FROM filmium_media_sources
            WHERE id = ?
            """,
            (source_id,),
        ).fetchone()

    @classmethod
    def _load_files(
        cls,
        connection: sqlite3.Connection,
        source_id: int,
    ) -> tuple[MediaFile, ...]:
        rows = connection.execute(
            """
            SELECT *
            FROM filmium_media_files
            WHERE source_id = ?
            ORDER BY
                CASE role
                    WHEN 'video' THEN 0
                    WHEN 'trailer' THEN 1
                    WHEN 'poster' THEN 2
                    WHEN 'backdrop' THEN 3
                    WHEN 'subtitle' THEN 4
                    WHEN 'manifest' THEN 5
                    ELSE 6
                END,
                relative_path COLLATE NOCASE,
                id
            """,
            (source_id,),
        ).fetchall()

        return tuple(cls._row_to_file(row) for row in rows)

    @staticmethod
    def _optional_datetime(value: str | None) -> datetime | None:
        return None if value is None else datetime.fromisoformat(value)

    @classmethod
    def _row_to_file(cls, row: sqlite3.Row) -> MediaFile:
        return MediaFile(
            id=int(row["id"]),
            source_id=int(row["source_id"]),
            role=MediaFileRole(row["role"]),
            relative_path=str(row["relative_path"]),
            language=row["language"],
            size_bytes=int(row["size_bytes"]),
            modified_at=cls._optional_datetime(row["modified_at"]),
            file_status=MediaFileStatus(row["file_status"]),
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )

    @classmethod
    def _row_to_source(
        cls,
        row: sqlite3.Row,
        files: tuple[MediaFile, ...],
    ) -> MediaSource:
        return MediaSource(
            id=int(row["id"]),
            media_id=int(row["media_id"]),
            library_root_id=(
                None
                if row["library_root_id"] is None
                else int(row["library_root_id"])
            ),
            root_path_snapshot=str(row["root_path_snapshot"]),
            relative_directory=str(row["relative_directory"]),
            manifest_path=str(row["manifest_path"]),
            availability_status=MediaFileStatus(
                row["availability_status"]
            ),
            last_verified_at=cls._optional_datetime(
                row["last_verified_at"]
            ),
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
            files=files,
        )