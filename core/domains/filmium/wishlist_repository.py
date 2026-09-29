import json
import sqlite3
from datetime import datetime
from pathlib import Path

from core.database import core_database_connection
from core.domains.filmium.wishlist_models import (
    WishlistEntry,
    WishlistEntryCreate,
)

# ==========          WISHLIST REPOSITORY          ==========

class WishlistRepository:
    """Čuva FILMIUM listu „za preuzeti" (zasebno od kataloga)."""

    def __init__(self, database_path: Path | None = None) -> None:
        """
        Inicijalizuje repository liste za preuzimanje.

        Args:
            database_path: Opciona putanja baze, prvenstveno za testiranje.
        """
        self._database_path = database_path

    def create(self, entry: WishlistEntryCreate) -> WishlistEntry:
        """Kreira novu stavku liste za preuzimanje."""

        with core_database_connection(self._database_path) as connection:
            cursor = connection.execute(
                """
                INSERT INTO filmium_wishlist (
                    title,
                    release_year,
                    media_type,
                    content_category,
                    is_subtitled,
                    is_synchronized,
                    tmdb_id,
                    english_overview,
                    local_overview,
                    original_title,
                    local_title
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    entry.title,
                    entry.release_year,
                    entry.media_type,
                    entry.content_category,
                    1 if entry.is_subtitled else 0,
                    1 if entry.is_synchronized else 0,
                    entry.tmdb_id,
                    entry.english_overview,
                    entry.local_overview,
                    entry.original_title,
                    entry.local_title,
                ),
            )

            if cursor.lastrowid is None:
                raise RuntimeError(
                    "SQLite nije vratio ID nove stavke liste za preuzimanje."
                )

            row = connection.execute(
                """
                SELECT *
                FROM filmium_wishlist
                WHERE id = ?
                """,
                (cursor.lastrowid,),
            ).fetchone()

        if row is None:
            raise RuntimeError(
                "Nova stavka liste za preuzimanje nije pronađena nakon upisa."
            )

        return self._row_to_entry(row)

    def list_all(self) -> list[WishlistEntry]:
        """Vraća sve stavke liste za preuzimanje (najnovije prve)."""

        with core_database_connection(self._database_path) as connection:
            rows = connection.execute(
                """
                SELECT *
                FROM filmium_wishlist
                ORDER BY created_at DESC, id DESC
                """
            ).fetchall()

        return [self._row_to_entry(row) for row in rows]

    def get_by_id(self, entry_id: int) -> WishlistEntry | None:
        """Pronalazi stavku liste za preuzimanje po ID-u."""

        with core_database_connection(self._database_path) as connection:
            row = connection.execute(
                """
                SELECT *
                FROM filmium_wishlist
                WHERE id = ?
                """,
                (entry_id,),
            ).fetchone()

        if row is None:
            return None

        return self._row_to_entry(row)

    def set_asset_path(
        self,
        entry_id: int,
        column: str,
        relative_path: str,
    ) -> WishlistEntry | None:
        """Upisuje putanju jednog asseta (poster/backdrop/prevod...)."""

        if column not in _ASSET_COLUMNS:
            raise ValueError(
                f"Nedozvoljena asset kolona: {column}"
            )

        with core_database_connection(self._database_path) as connection:
            connection.execute(
                f"""
                UPDATE filmium_wishlist
                SET {column} = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (relative_path, entry_id),
            )

        return self.get_by_id(entry_id)

    def append_extra_asset(
        self,
        entry_id: int,
        relative_path: str,
    ) -> WishlistEntry | None:
        """Dodaje putanju u JSON listu dodatnih sadržaja."""

        entry = self.get_by_id(entry_id)
        if entry is None:
            return None

        updated = [*entry.extra_assets, relative_path]

        with core_database_connection(self._database_path) as connection:
            connection.execute(
                """
                UPDATE filmium_wishlist
                SET extra_assets = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (json.dumps(updated), entry_id),
            )

        return self.get_by_id(entry_id)

    def delete(self, entry_id: int) -> bool:
        """Briše stavku liste za preuzimanje."""

        with core_database_connection(self._database_path) as connection:
            cursor = connection.execute(
                """
                DELETE FROM filmium_wishlist
                WHERE id = ?
                """,
                (entry_id,),
            )

        return cursor.rowcount > 0

    # ==========          POMOĆNE METODE          ==========

    @staticmethod
    def _row_to_entry(row: sqlite3.Row) -> WishlistEntry:
        """Pretvara SQLite red u stavku liste za preuzimanje."""

        raw_extra = row["extra_assets"] or "[]"
        try:
            extra = tuple(json.loads(raw_extra))
        except (TypeError, ValueError):
            extra = ()

        return WishlistEntry(
            id=row["id"],
            title=row["title"],
            release_year=row["release_year"],
            media_type=row["media_type"],
            content_category=row["content_category"],
            is_subtitled=bool(row["is_subtitled"]),
            is_synchronized=bool(row["is_synchronized"]),
            tmdb_id=row["tmdb_id"],
            english_overview=row["english_overview"],
            local_overview=row["local_overview"],
            original_title=row["original_title"],
            local_title=row["local_title"],
            poster_path=row["poster_path"],
            backdrop_path=row["backdrop_path"],
            wallpaper_path=row["wallpaper_path"],
            original_subtitle_path=row["original_subtitle_path"],
            domestic_subtitle_path=row["domestic_subtitle_path"],
            english_subtitle_path=row["english_subtitle_path"],
            extra_assets=extra,
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )


# Kolone u koje smemo upisati asset putanju (whitelist za set_asset_path).
_ASSET_COLUMNS = frozenset(
    {
        "poster_path",
        "backdrop_path",
        "wallpaper_path",
        "original_subtitle_path",
        "domestic_subtitle_path",
        "english_subtitle_path",
    }
)
