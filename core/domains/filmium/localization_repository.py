import sqlite3
from datetime import datetime
from pathlib import Path

from core.database import core_database_connection
from core.domains.filmium.localization_models import (
    MediaLocalization,
    MediaLocalizationCreate,
    MediaLocalizationSettings,
    MediaLocalizationSettingsUpdate,
    MediaLocalizationType,
    MediaOriginScope,
)

# ==========          LOCALIZATION REPOSITORY          ==========

class LocalizationRepository:
    """Cuva poreklo, originalni jezik, titlove i sinhronizacije."""

    def __init__(self, database_path: Path | None = None) -> None:
        self._database_path = database_path

    def get_settings(
        self,
        media_id: int,
    ) -> MediaLocalizationSettings | None:
        """Ucitava kompletna jezicka podesavanja jednog sadrzaja."""

        with core_database_connection(self._database_path) as connection:
            media_row = self._get_media_row(connection, media_id)

            if media_row is None:
                return None

            localizations = self._load_localizations(
                connection,
                media_id,
            )

        return self._to_settings(media_row, localizations)

    def source_belongs_to_media(
        self,
        source_id: int,
        media_id: int,
    ) -> bool:
        """Proverava da li fizicki izvor pripada trazenom filmu."""

        with core_database_connection(self._database_path) as connection:
            row = connection.execute(
                """
                SELECT 1
                FROM filmium_media_sources
                WHERE id = ? AND media_id = ?
                """,
                (source_id, media_id),
            ).fetchone()

        return row is not None

    def replace_settings(
        self,
        item: MediaLocalizationSettingsUpdate,
    ) -> MediaLocalizationSettings | None:
        """Atomski menja poreklo, jezik i sve lokalizacije."""

        with core_database_connection(self._database_path) as connection:
            cursor = connection.execute(
                """
                UPDATE filmium_media_items
                SET
                    origin_scope = ?,
                    original_language_code = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (
                    item.origin_scope.value,
                    item.original_language_code,
                    item.media_id,
                ),
            )

            if cursor.rowcount == 0:
                return None

            connection.execute(
                """
                DELETE FROM filmium_media_localizations
                WHERE media_id = ?
                """,
                (item.media_id,),
            )
            self._insert_localizations(
                connection,
                item.localizations,
            )
            media_row = self._get_media_row(
                connection,
                item.media_id,
            )
            localizations = self._load_localizations(
                connection,
                item.media_id,
            )

        if media_row is None:
            return None

        return self._to_settings(media_row, localizations)

    @staticmethod
    def _insert_localizations(
        connection: sqlite3.Connection,
        localizations: tuple[MediaLocalizationCreate, ...],
    ) -> None:
        connection.executemany(
            """
            INSERT INTO filmium_media_localizations (
                media_id,
                source_id,
                localization_type,
                language_code,
                label,
                is_primary
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                (
                    item.media_id,
                    item.source_id,
                    item.localization_type.value,
                    item.language_code,
                    item.label,
                    int(item.is_primary),
                )
                for item in localizations
            ),
        )

    @staticmethod
    def _get_media_row(
        connection: sqlite3.Connection,
        media_id: int,
    ) -> sqlite3.Row | None:
        return connection.execute(
            """
            SELECT
                id,
                origin_scope,
                original_language_code
            FROM filmium_media_items
            WHERE id = ?
            """,
            (media_id,),
        ).fetchone()

    @classmethod
    def _load_localizations(
        cls,
        connection: sqlite3.Connection,
        media_id: int,
    ) -> tuple[MediaLocalization, ...]:
        rows = connection.execute(
            """
            SELECT *
            FROM filmium_media_localizations
            WHERE media_id = ?
            ORDER BY
                localization_type,
                language_code COLLATE NOCASE,
                is_primary DESC,
                id
            """,
            (media_id,),
        ).fetchall()

        return tuple(cls._row_to_localization(row) for row in rows)

    @staticmethod
    def _row_to_localization(
        row: sqlite3.Row,
    ) -> MediaLocalization:
        return MediaLocalization(
            id=int(row["id"]),
            media_id=int(row["media_id"]),
            source_id=(
                None
                if row["source_id"] is None
                else int(row["source_id"])
            ),
            localization_type=MediaLocalizationType(
                row["localization_type"]
            ),
            language_code=str(row["language_code"]),
            label=row["label"],
            is_primary=bool(row["is_primary"]),
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )

    @staticmethod
    def _to_settings(
        media_row: sqlite3.Row,
        localizations: tuple[MediaLocalization, ...],
    ) -> MediaLocalizationSettings:
        return MediaLocalizationSettings(
            media_id=int(media_row["id"]),
            origin_scope=MediaOriginScope(
                media_row["origin_scope"]
            ),
            original_language_code=media_row[
                "original_language_code"
            ],
            localizations=localizations,
        )