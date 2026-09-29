import sqlite3
from datetime import datetime
from pathlib import Path

from core.database import core_database_connection
from core.domains.filmium.models import (
    CollectionCreate,
    MediaCollection,
)

# ==========          COLLECTION REPOSITORY          ==========

class CollectionRepository:
    """Čuva FILMIUM kolekcije i veze sa sadržajima."""

    def __init__(self, database_path: Path | None = None) -> None:
        """
        Inicijalizuje repository kolekcija.

        Args:
            database_path: Opciona putanja baze, prvenstveno za testiranje.
        """
        self._database_path = database_path

    def create(self, collection: CollectionCreate) -> MediaCollection:
        """Kreira novu FILMIUM kolekciju."""

        with core_database_connection(self._database_path) as connection:
            cursor = connection.execute(
                """
                INSERT INTO filmium_collections (
                    name,
                    description
                )
                VALUES (?, ?)
                """,
                (
                    collection.name,
                    collection.description,
                ),
            )

            if cursor.lastrowid is None:
                raise RuntimeError(
                    "SQLite nije vratio ID nove FILMIUM kolekcije."
                )

            collection_id = cursor.lastrowid

            row = connection.execute(
                """
                SELECT *
                FROM filmium_collections
                WHERE id = ?
                """,
                (collection_id,),
            ).fetchone()

        if row is None:
            raise RuntimeError(
                "Nova FILMIUM kolekcija nije pronađena nakon upisa."
            )

        return self._row_to_collection(row, ())

    def list_all(self) -> list[MediaCollection]:
        """Vraća sve FILMIUM kolekcije."""

        with core_database_connection(self._database_path) as connection:
            rows = connection.execute(
                """
                SELECT *
                FROM filmium_collections
                ORDER BY name COLLATE NOCASE
                """
            ).fetchall()

            collection_ids = tuple(row["id"] for row in rows)
            items_by_collection = self._load_item_ids(
                connection,
                collection_ids,
            )

        return [
            self._row_to_collection(
                row,
                items_by_collection.get(row["id"], ()),
            )
            for row in rows
        ]

    def get_by_id(
        self,
        collection_id: int,
    ) -> MediaCollection | None:
        """Pronalazi FILMIUM kolekciju po ID-u."""

        with core_database_connection(self._database_path) as connection:
            row = connection.execute(
                """
                SELECT *
                FROM filmium_collections
                WHERE id = ?
                """,
                (collection_id,),
            ).fetchone()

            item_ids = self._load_item_ids(
                connection,
                (collection_id,),
            ).get(collection_id, ())

        if row is None:
            return None

        return self._row_to_collection(row, item_ids)

    def delete(self, collection_id: int) -> bool:
        """Briše FILMIUM kolekciju."""

        with core_database_connection(self._database_path) as connection:
            cursor = connection.execute(
                """
                DELETE FROM filmium_collections
                WHERE id = ?
                """,
                (collection_id,),
            )

        return cursor.rowcount > 0

    # ==========          ČLANSTVO KOLEKCIJE          ==========

    def add_item(
        self,
        collection_id: int,
        item_id: int,
    ) -> bool:
        """
        Dodaje FILMIUM sadržaj u kolekciju.

        Returns:
            True ako je nova veza kreirana, inače False.
        """
        with core_database_connection(self._database_path) as connection:
            next_position = connection.execute(
                """
                SELECT COALESCE(MAX(position), -1) + 1
                FROM filmium_collection_items
                WHERE collection_id = ?
                """,
                (collection_id,),
            ).fetchone()[0]

            cursor = connection.execute(
                """
                INSERT OR IGNORE INTO filmium_collection_items (
                    collection_id,
                    media_id,
                    position
                )
                VALUES (?, ?, ?)
                """,
                (
                    collection_id,
                    item_id,
                    next_position,
                ),
            )

        return cursor.rowcount > 0

    def remove_item(
        self,
        collection_id: int,
        item_id: int,
    ) -> bool:
        """
        Uklanja FILMIUM sadržaj iz kolekcije.

        Returns:
            True ako je veza obrisana, inače False.
        """
        with core_database_connection(self._database_path) as connection:
            cursor = connection.execute(
                """
                DELETE FROM filmium_collection_items
                WHERE collection_id = ? AND media_id = ?
                """,
                (collection_id, item_id),
            )

        return cursor.rowcount > 0

    # ==========          POMOĆNE METODE          ==========

    @staticmethod
    def _load_item_ids(
        connection: sqlite3.Connection,
        collection_ids: tuple[int, ...],
    ) -> dict[int, tuple[int, ...]]:
        """Učitava ID-eve sadržaja za više kolekcija jednim upitom."""

        if not collection_ids:
            return {}

        placeholders = ", ".join("?" for _ in collection_ids)

        rows = connection.execute(
            f"""
            SELECT
                collection_id,
                media_id
            FROM filmium_collection_items
            WHERE collection_id IN ({placeholders})
            ORDER BY collection_id, position, added_at
            """,
            collection_ids,
        ).fetchall()

        items_by_collection: dict[int, list[int]] = {
            collection_id: []
            for collection_id in collection_ids
        }

        for row in rows:
            items_by_collection[row["collection_id"]].append(
                row["media_id"]
            )

        return {
            collection_id: tuple(item_ids)
            for collection_id, item_ids in items_by_collection.items()
        }

    @staticmethod
    def _row_to_collection(
        row: sqlite3.Row,
        item_ids: tuple[int, ...],
    ) -> MediaCollection:
        """Pretvara SQLite red u FILMIUM kolekciju."""

        return MediaCollection(
            id=row["id"],
            name=row["name"],
            description=row["description"],
            item_ids=item_ids,
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )