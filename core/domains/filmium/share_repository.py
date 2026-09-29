import sqlite3
from datetime import datetime
from pathlib import Path

from core.database import core_database_connection
from core.domains.filmium.share_models import (
    ShareProfile,
    ShareProfileCreate,
    ShareQueueItem,
    ShareQueueStatus,
    ShareTransferMode,
)

# ==========          SHARE REPOSITORY          ==========

class ShareRepository:
    """Cuva profile i red funkcije Podeli u CORE SQLite bazi."""

    def __init__(self, database_path: Path | None = None) -> None:
        self._database_path = database_path

    def create_profile(
        self,
        item: ShareProfileCreate,
    ) -> ShareProfile:
        """Pravi novi profil za deljenje."""

        with core_database_connection(self._database_path) as connection:
            cursor = connection.execute(
                """
                INSERT INTO filmium_share_profiles (
                    name,
                    description,
                    default_destination_folder,
                    is_active
                )
                VALUES (?, ?, ?, ?)
                """,
                (
                    item.name,
                    item.description,
                    item.default_destination_folder,
                    int(item.is_active),
                ),
            )

            if cursor.lastrowid is None:
                raise RuntimeError(
                    "SQLite nije vratio ID novog profila za deljenje."
                )

            row = self._get_profile_row(
                connection,
                int(cursor.lastrowid),
            )

        if row is None:
            raise RuntimeError(
                "Novi profil za deljenje nije pronadjen nakon upisa."
            )

        return self._row_to_profile(row)

    def list_profiles(self) -> tuple[ShareProfile, ...]:
        """Vraca sve profile, aktivne pre neaktivnih."""

        with core_database_connection(self._database_path) as connection:
            rows = connection.execute(
                """
                SELECT *
                FROM filmium_share_profiles
                ORDER BY
                    is_active DESC,
                    name COLLATE NOCASE,
                    id
                """
            ).fetchall()

        return tuple(self._row_to_profile(row) for row in rows)

    def get_profile(self, profile_id: int) -> ShareProfile | None:
        """Ucitava jedan profil po ID-u."""

        with core_database_connection(self._database_path) as connection:
            row = self._get_profile_row(connection, profile_id)

        return None if row is None else self._row_to_profile(row)

    def update_profile(
        self,
        profile_id: int,
        item: ShareProfileCreate,
    ) -> ShareProfile | None:
        """Menja naziv, opis, folder i aktivnost profila."""

        with core_database_connection(self._database_path) as connection:
            cursor = connection.execute(
                """
                UPDATE filmium_share_profiles
                SET
                    name = ?,
                    description = ?,
                    default_destination_folder = ?,
                    is_active = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (
                    item.name,
                    item.description,
                    item.default_destination_folder,
                    int(item.is_active),
                    profile_id,
                ),
            )

            if cursor.rowcount == 0:
                return None

            row = self._get_profile_row(connection, profile_id)

        return None if row is None else self._row_to_profile(row)

    def delete_profile(self, profile_id: int) -> bool:
        """Brise profil i njegove stavke reda kroz FK kaskadu."""

        with core_database_connection(self._database_path) as connection:
            cursor = connection.execute(
                """
                DELETE FROM filmium_share_profiles
                WHERE id = ?
                """,
                (profile_id,),
            )

        return cursor.rowcount > 0

    def media_exists(self, media_id: int) -> bool:
        """Proverava postojanje kataloskog sadrzaja."""

        with core_database_connection(self._database_path) as connection:
            row = connection.execute(
                """
                SELECT 1
                FROM filmium_media_items
                WHERE id = ?
                """,
                (media_id,),
            ).fetchone()

        return row is not None

    def add_to_queue(
        self,
        profile_id: int,
        media_id: int,
        transfer_mode: ShareTransferMode,
    ) -> ShareQueueItem:
        """Dodaje film u red jednog profila."""

        with core_database_connection(self._database_path) as connection:
            cursor = connection.execute(
                """
                INSERT INTO filmium_share_queue (
                    profile_id,
                    media_id,
                    transfer_mode
                )
                VALUES (?, ?, ?)
                """,
                (
                    profile_id,
                    media_id,
                    transfer_mode.value,
                ),
            )

            if cursor.lastrowid is None:
                raise RuntimeError(
                    "SQLite nije vratio ID nove stavke za deljenje."
                )

            row = self._get_queue_row(
                connection,
                int(cursor.lastrowid),
            )

        if row is None:
            raise RuntimeError(
                "Nova stavka za deljenje nije pronadjena nakon upisa."
            )

        return self._row_to_queue_item(row)

    def list_queue(
        self,
        profile_id: int,
    ) -> tuple[ShareQueueItem, ...]:
        """Vraca red izabranog profila, od najnovijeg dodatog."""

        with core_database_connection(self._database_path) as connection:
            rows = connection.execute(
                """
                SELECT *
                FROM filmium_share_queue
                WHERE profile_id = ?
                ORDER BY added_at DESC, id DESC
                """,
                (profile_id,),
            ).fetchall()

        return tuple(self._row_to_queue_item(row) for row in rows)

    def get_queue_item(
        self,
        queue_item_id: int,
    ) -> ShareQueueItem | None:
        """Ucitava jednu stavku reda."""

        with core_database_connection(self._database_path) as connection:
            row = self._get_queue_row(connection, queue_item_id)

        return None if row is None else self._row_to_queue_item(row)

    def set_transfer_mode(
        self,
        queue_item_id: int,
        transfer_mode: ShareTransferMode,
    ) -> ShareQueueItem | None:
        """Menja rezim i vraca zavrsenu stavku u red za prenos."""

        with core_database_connection(self._database_path) as connection:
            cursor = connection.execute(
                """
                UPDATE filmium_share_queue
                SET
                    transfer_mode = ?,
                    status = ?,
                    error_message = NULL,
                    completed_at = NULL,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (
                    transfer_mode.value,
                    ShareQueueStatus.PENDING.value,
                    queue_item_id,
                ),
            )

            if cursor.rowcount == 0:
                return None

            row = self._get_queue_row(connection, queue_item_id)

        return None if row is None else self._row_to_queue_item(row)

    def remove_from_queue(self, queue_item_id: int) -> bool:
        """Uklanja stavku iz reda bez brisanja filma."""

        with core_database_connection(self._database_path) as connection:
            cursor = connection.execute(
                """
                DELETE FROM filmium_share_queue
                WHERE id = ?
                """,
                (queue_item_id,),
            )

        return cursor.rowcount > 0

    @staticmethod
    def _get_profile_row(
        connection: sqlite3.Connection,
        profile_id: int,
    ) -> sqlite3.Row | None:
        return connection.execute(
            """
            SELECT *
            FROM filmium_share_profiles
            WHERE id = ?
            """,
            (profile_id,),
        ).fetchone()

    @staticmethod
    def _get_queue_row(
        connection: sqlite3.Connection,
        queue_item_id: int,
    ) -> sqlite3.Row | None:
        return connection.execute(
            """
            SELECT *
            FROM filmium_share_queue
            WHERE id = ?
            """,
            (queue_item_id,),
        ).fetchone()

    @staticmethod
    def _optional_datetime(value: str | None) -> datetime | None:
        return None if value is None else datetime.fromisoformat(value)

    @classmethod
    def _row_to_profile(cls, row: sqlite3.Row) -> ShareProfile:
        return ShareProfile(
            id=int(row["id"]),
            name=str(row["name"]),
            description=row["description"],
            default_destination_folder=str(
                row["default_destination_folder"]
            ),
            is_active=bool(row["is_active"]),
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )

    @classmethod
    def _row_to_queue_item(cls, row: sqlite3.Row) -> ShareQueueItem:
        return ShareQueueItem(
            id=int(row["id"]),
            profile_id=int(row["profile_id"]),
            media_id=int(row["media_id"]),
            transfer_mode=ShareTransferMode(row["transfer_mode"]),
            status=ShareQueueStatus(row["status"]),
            error_message=row["error_message"],
            added_at=datetime.fromisoformat(row["added_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
            completed_at=cls._optional_datetime(row["completed_at"]),
        )