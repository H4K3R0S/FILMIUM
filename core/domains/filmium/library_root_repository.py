import sqlite3
from datetime import datetime
from pathlib import Path

from core.database import core_database_connection
from core.domains.filmium.library_root_models import (
    LibraryRoot,
    LibraryRootCreate,
    LibraryRootScanStatus,
)

# ==========          LIBRARY ROOT REPOSITORY          ==========

class LibraryRootRepository:
    """Cuva registrovane FILMIUM biblioteke u CORE bazi."""

    def __init__(self, database_path: Path | None = None) -> None:
        self._database_path = database_path

    def create(self, item: LibraryRootCreate) -> LibraryRoot:
        with core_database_connection(self._database_path) as connection:
            cursor = connection.execute(
                """
                INSERT INTO filmium_library_roots (
                    name,
                    path,
                    volume_id,
                    volume_label,
                    is_enabled,
                    is_persistent,
                    last_scan_status
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    item.name,
                    item.path,
                    item.volume_id,
                    item.volume_label,
                    int(item.is_enabled),
                    int(item.is_persistent),
                    (
                        LibraryRootScanStatus.NEVER_SCANNED.value
                        if item.is_enabled
                        else LibraryRootScanStatus.DISABLED.value
                    ),
                ),
            )

            if cursor.lastrowid is None:
                raise RuntimeError(
                    "SQLite nije vratio ID nove FILMIUM biblioteke."
                )

            row = connection.execute(
                """
                SELECT *
                FROM filmium_library_roots
                WHERE id = ?
                """,
                (cursor.lastrowid,),
            ).fetchone()

        if row is None:
            raise RuntimeError(
                "Nova FILMIUM biblioteka nije pronadjena nakon upisa."
            )

        return self._row_to_library_root(row)

    def list_all(self) -> tuple[LibraryRoot, ...]:
        with core_database_connection(self._database_path) as connection:
            rows = connection.execute(
                """
                SELECT *
                FROM filmium_library_roots
                ORDER BY name COLLATE NOCASE, id
                """
            ).fetchall()

        return tuple(self._row_to_library_root(row) for row in rows)

    def get(self, root_id: int) -> LibraryRoot | None:
        with core_database_connection(self._database_path) as connection:
            row = connection.execute(
                """
                SELECT *
                FROM filmium_library_roots
                WHERE id = ?
                """,
                (root_id,),
            ).fetchone()

        return None if row is None else self._row_to_library_root(row)

    def update(
        self,
        root_id: int,
        item: LibraryRootCreate,
    ) -> LibraryRoot | None:
        with core_database_connection(self._database_path) as connection:
            cursor = connection.execute(
                """
                UPDATE filmium_library_roots
                SET
                    name = ?,
                    path = ?,
                    volume_id = ?,
                    volume_label = ?,
                    is_enabled = ?,
                    is_persistent = ?,
                    last_scan_status = CASE
                        WHEN ? = 0 THEN 'disabled'
                        WHEN is_enabled = 0 THEN 'never_scanned'
                        ELSE last_scan_status
                    END,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (
                    item.name,
                    item.path,
                    item.volume_id,
                    item.volume_label,
                    int(item.is_enabled),
                    int(item.is_persistent),
                    int(item.is_enabled),
                    root_id,
                ),
            )

            if cursor.rowcount == 0:
                return None

            row = connection.execute(
                "SELECT * FROM filmium_library_roots WHERE id = ?",
                (root_id,),
            ).fetchone()

        return None if row is None else self._row_to_library_root(row)

    def record_scan(
        self,
        root_id: int,
        status: LibraryRootScanStatus,
    ) -> LibraryRoot | None:
        with core_database_connection(self._database_path) as connection:
            cursor = connection.execute(
                """
                UPDATE filmium_library_roots
                SET
                    last_scan_status = ?,
                    last_scanned_at = CURRENT_TIMESTAMP,
                    last_seen_at = CASE
                        WHEN ? = 'available' THEN CURRENT_TIMESTAMP
                        ELSE last_seen_at
                    END,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (status.value, status.value, root_id),
            )

            if cursor.rowcount == 0:
                return None

            row = connection.execute(
                "SELECT * FROM filmium_library_roots WHERE id = ?",
                (root_id,),
            ).fetchone()

        return None if row is None else self._row_to_library_root(row)

    def set_main(self, root_id: int) -> LibraryRoot | None:
        """Postavlja jedan disk kao glavni; ostale skida sa te oznake."""

        with core_database_connection(self._database_path) as connection:
            exists = connection.execute(
                "SELECT id FROM filmium_library_roots WHERE id = ?",
                (root_id,),
            ).fetchone()

            if exists is None:
                return None

            connection.execute(
                "UPDATE filmium_library_roots SET is_main = 0 "
                "WHERE is_main = 1"
            )
            connection.execute(
                """
                UPDATE filmium_library_roots
                SET is_main = 1,
                    is_persistent = 1,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (root_id,),
            )

            row = connection.execute(
                "SELECT * FROM filmium_library_roots WHERE id = ?",
                (root_id,),
            ).fetchone()

        return None if row is None else self._row_to_library_root(row)

    def delete(self, root_id: int) -> bool:
        with core_database_connection(self._database_path) as connection:
            cursor = connection.execute(
                """
                DELETE FROM filmium_library_roots
                WHERE id = ?
                """,
                (root_id,),
            )

        return cursor.rowcount > 0

    @staticmethod
    def _optional_datetime(value: str | None) -> datetime | None:
        return None if value is None else datetime.fromisoformat(value)

    @classmethod
    def _row_to_library_root(cls, row: sqlite3.Row) -> LibraryRoot:
        return LibraryRoot(
            id=int(row["id"]),
            name=str(row["name"]),
            path=str(row["path"]),
            volume_id=row["volume_id"],
            volume_label=row["volume_label"],
            is_enabled=bool(row["is_enabled"]),
            is_persistent=bool(row["is_persistent"]),
            is_main=bool(row["is_main"]),
            last_scan_status=LibraryRootScanStatus(
                row["last_scan_status"]
            ),
            last_scanned_at=cls._optional_datetime(
                row["last_scanned_at"]
            ),
            last_seen_at=cls._optional_datetime(row["last_seen_at"]),
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )
