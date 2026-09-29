import sqlite3
from datetime import datetime
from pathlib import Path

from core.database import core_database_connection
from core.domains.filmium.artwork_models import (
    ArtworkStorageKind,
    ArtworkType,
    MediaArtwork,
    MediaArtworkCreate,
)

# ==========          ARTWORK REPOSITORY          ==========

class ArtworkRepository:
    """Cuva i bira slike povezane sa FILMIUM katalogom."""

    def __init__(self, database_path: Path | None = None) -> None:
        self._database_path = database_path

    def save(self, item: MediaArtworkCreate) -> MediaArtwork:
        """Kreira sliku ili osvezava isti vec indeksirani zapis."""

        with core_database_connection(self._database_path) as connection:
            return self._save(connection, item)

    def replace_for_source(
        self,
        media_id: int,
        source_id: int,
        items: tuple[MediaArtworkCreate, ...],
    ) -> tuple[MediaArtwork, ...]:
        """Atomski menja registry slike koje pripadaju jednom izvoru."""

        for item in items:
            if (
                item.media_id != media_id
                or item.source_id != source_id
                or item.storage_kind is not ArtworkStorageKind.SOURCE
            ):
                raise ValueError(
                    "Source artwork ne pripada zadatom mediju i izvoru."
                )

        with core_database_connection(self._database_path) as connection:
            connection.execute(
                """
                DELETE FROM filmium_media_artworks
                WHERE source_id = ?
                """,
                (source_id,),
            )
            for item in items:
                self._save(connection, item)

            saved = self._load_for_source(
                connection,
                source_id,
            )

        return saved

    def get(self, artwork_id: int) -> MediaArtwork | None:
        """Ucitava jednu sliku prema njenom ID-u."""

        with core_database_connection(self._database_path) as connection:
            row = connection.execute(
                """
                SELECT *
                FROM filmium_media_artworks
                WHERE id = ?
                """,
                (artwork_id,),
            ).fetchone()

        return None if row is None else self._row_to_artwork(row)

    def list_for_media(
        self,
        media_id: int,
        artwork_type: ArtworkType | None = None,
    ) -> tuple[MediaArtwork, ...]:
        """Vraca sve ili samo trazeni tip slika jednog sadrzaja."""

        parameters: tuple[object, ...]
        type_filter: str

        if artwork_type is None:
            type_filter = ""
            parameters = (media_id,)
        else:
            type_filter = "AND artwork_type = ?"
            parameters = (media_id, artwork_type.value)

        with core_database_connection(self._database_path) as connection:
            rows = connection.execute(
                f"""
                SELECT *
                FROM filmium_media_artworks
                WHERE media_id = ?
                    {type_filter}
                ORDER BY
                    CASE artwork_type
                        WHEN 'poster' THEN 0
                        WHEN 'backdrop' THEN 1
                        WHEN 'wallpaper' THEN 2
                        WHEN 'fanart' THEN 3
                        WHEN 'logo' THEN 4
                        ELSE 5
                    END,
                    is_primary DESC,
                    sort_order,
                    relative_path COLLATE NOCASE,
                    id
                """,
                parameters,
            ).fetchall()

        return tuple(self._row_to_artwork(row) for row in rows)

    def list_for_source(
        self,
        source_id: int,
    ) -> tuple[MediaArtwork, ...]:
        """Vraca registry slike povezane sa jednim fizickim izvorom."""

        with core_database_connection(self._database_path) as connection:
            return self._load_for_source(connection, source_id)

    def set_primary(
        self,
        artwork_id: int,
    ) -> MediaArtwork | None:
        """Postavlja izabranu sliku kao jedinu primarnu za njen tip."""

        with core_database_connection(self._database_path) as connection:
            row = connection.execute(
                """
                SELECT *
                FROM filmium_media_artworks
                WHERE id = ?
                """,
                (artwork_id,),
            ).fetchone()

            if row is None:
                return None

            artwork_type = ArtworkType(row["artwork_type"])
            self._demote_primary(
                connection,
                int(row["media_id"]),
                artwork_type,
            )
            connection.execute(
                """
                UPDATE filmium_media_artworks
                SET
                    is_primary = 1,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (artwork_id,),
            )
            updated_row = connection.execute(
                """
                SELECT *
                FROM filmium_media_artworks
                WHERE id = ?
                """,
                (artwork_id,),
            ).fetchone()

        return (
            None
            if updated_row is None
            else self._row_to_artwork(updated_row)
        )

    def delete(self, artwork_id: int) -> bool:
        """Brise samo zapis slike, bez brisanja fizicke datoteke."""

        with core_database_connection(self._database_path) as connection:
            cursor = connection.execute(
                """
                DELETE FROM filmium_media_artworks
                WHERE id = ?
                """,
                (artwork_id,),
            )

        return cursor.rowcount > 0

    @staticmethod
    def _demote_primary(
        connection: sqlite3.Connection,
        media_id: int,
        artwork_type: ArtworkType,
    ) -> None:
        connection.execute(
            """
            UPDATE filmium_media_artworks
            SET
                is_primary = 0,
                updated_at = CURRENT_TIMESTAMP
            WHERE media_id = ?
                AND artwork_type = ?
                AND is_primary = 1
            """,
            (media_id, artwork_type.value),
        )

    @classmethod
    def _save(
        cls,
        connection: sqlite3.Connection,
        item: MediaArtworkCreate,
    ) -> MediaArtwork:
        if item.is_primary:
            cls._demote_primary(
                connection,
                item.media_id,
                item.artwork_type,
            )

        connection.execute(
            """
            INSERT INTO filmium_media_artworks (
                media_id,
                source_id,
                artwork_type,
                storage_kind,
                relative_path,
                label,
                width_pixels,
                height_pixels,
                file_size_bytes,
                is_primary,
                sort_order
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT DO UPDATE SET
                label = excluded.label,
                width_pixels = excluded.width_pixels,
                height_pixels = excluded.height_pixels,
                file_size_bytes = excluded.file_size_bytes,
                is_primary = excluded.is_primary,
                sort_order = excluded.sort_order,
                updated_at = CURRENT_TIMESTAMP
            """,
            (
                item.media_id,
                item.source_id,
                item.artwork_type.value,
                item.storage_kind.value,
                item.relative_path,
                item.label,
                item.width_pixels,
                item.height_pixels,
                item.file_size_bytes,
                int(item.is_primary),
                item.sort_order,
            ),
        )
        row = cls._find_identity_row(connection, item)

        if row is None:
            raise RuntimeError(
                "FILMIUM slika nije pronadjena nakon upisa."
            )

        return cls._row_to_artwork(row)

    @staticmethod
    def _find_identity_row(
        connection: sqlite3.Connection,
        item: MediaArtworkCreate,
    ) -> sqlite3.Row | None:
        return connection.execute(
            """
            SELECT *
            FROM filmium_media_artworks
            WHERE media_id = ?
                AND artwork_type = ?
                AND storage_kind = ?
                AND (
                    source_id = ?
                    OR (
                        source_id IS NULL
                        AND ? IS NULL
                    )
                )
                AND relative_path = ? COLLATE NOCASE
            """,
            (
                item.media_id,
                item.artwork_type.value,
                item.storage_kind.value,
                item.source_id,
                item.source_id,
                item.relative_path,
            ),
        ).fetchone()

    @classmethod
    def _load_for_source(
        cls,
        connection: sqlite3.Connection,
        source_id: int,
    ) -> tuple[MediaArtwork, ...]:
        rows = connection.execute(
            """
            SELECT *
            FROM filmium_media_artworks
            WHERE source_id = ?
            ORDER BY
                CASE artwork_type
                    WHEN 'poster' THEN 0
                    WHEN 'backdrop' THEN 1
                    WHEN 'wallpaper' THEN 2
                    WHEN 'fanart' THEN 3
                    WHEN 'logo' THEN 4
                    ELSE 5
                END,
                is_primary DESC,
                sort_order,
                relative_path COLLATE NOCASE,
                id
            """,
            (source_id,),
        ).fetchall()

        return tuple(cls._row_to_artwork(row) for row in rows)

    @staticmethod
    def _optional_integer(value: object) -> int | None:
        return None if value is None else int(value)

    @classmethod
    def _row_to_artwork(
        cls,
        row: sqlite3.Row,
    ) -> MediaArtwork:
        return MediaArtwork(
            id=int(row["id"]),
            media_id=int(row["media_id"]),
            source_id=cls._optional_integer(row["source_id"]),
            artwork_type=ArtworkType(row["artwork_type"]),
            storage_kind=ArtworkStorageKind(row["storage_kind"]),
            relative_path=str(row["relative_path"]),
            label=row["label"],
            width_pixels=cls._optional_integer(row["width_pixels"]),
            height_pixels=cls._optional_integer(row["height_pixels"]),
            file_size_bytes=int(row["file_size_bytes"]),
            is_primary=bool(row["is_primary"]),
            sort_order=int(row["sort_order"]),
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )