import json
import sqlite3
from datetime import datetime
from pathlib import Path

from core.database import core_database_connection
from core.domains.filmium.models import (
    MediaItem,
    MediaItemCreate,
    MediaType,
    WatchStatus,
)


def _parse_cast_names(value: object) -> tuple[str, ...]:
    """JSON lista imena glumaca → torka; tolerantno na loš/prazan sadržaj."""

    if not value:
        return ()
    try:
        data = json.loads(value)  # type: ignore[arg-type]
    except (ValueError, TypeError):
        return ()
    if not isinstance(data, list):
        return ()
    return tuple(name for name in data if isinstance(name, str) and name)


def _serialize_related(items: tuple) -> str:
    """Lista RelatedTitle → JSON tekst za bazu."""

    return json.dumps([
        {
            "tmdb_id": related.tmdb_id,
            "title": related.title,
            "year": related.year,
            "poster_path": related.poster_path,
            "media_type": related.media_type.value,
        }
        for related in items
    ])


def _parse_related(value: object) -> tuple:
    """JSON tekst → torka RelatedTitle; tolerantno na loš/prazan sadržaj."""

    from core.domains.filmium.models import MediaType, RelatedTitle

    if not value:
        return ()
    try:
        data = json.loads(value)  # type: ignore[arg-type]
    except (ValueError, TypeError):
        return ()
    if not isinstance(data, list):
        return ()

    result = []
    for entry in data:
        if not isinstance(entry, dict) or "tmdb_id" not in entry:
            continue
        try:
            result.append(RelatedTitle(
                tmdb_id=int(entry["tmdb_id"]),
                title=str(entry.get("title") or ""),
                year=entry.get("year"),
                poster_path=entry.get("poster_path"),
                media_type=MediaType(entry.get("media_type", "movie")),
            ))
        except (ValueError, TypeError):
            continue
    return tuple(result)


def _parse_editor_settings(value: object) -> dict:
    """JSON objekat sa dodatnim editor poljima → dict; tolerantno."""

    if not value:
        return {}
    try:
        data = json.loads(value)  # type: ignore[arg-type]
    except (ValueError, TypeError):
        return {}
    return data if isinstance(data, dict) else {}


# ==========          FILMIUM REPOSITORY          ==========

class MediaRepository:
    """Čuva i učitava FILMIUM sadržaj iz CORE SQLite baze."""

    def __init__(self, database_path: Path | None = None) -> None:
        """
        Inicijalizuje repository.

        Args:
            database_path: Opciona putanja baze, prvenstveno za testiranje.
        """
        self._database_path = database_path

    def create(self, item: MediaItemCreate) -> MediaItem:
        """Dodaje novi sadržaj u FILMIUM katalog."""

        with core_database_connection(self._database_path) as connection:
            cursor = connection.execute(
                """
                INSERT INTO filmium_media_items (
                    title,
                    original_title,
                    english_title,
                    media_type,
                    release_year,
                    runtime_minutes,
                    watch_status,
                    rating,
                    notes,
                    english_description,
                    content_category,
                    cast_names,
                    studio,
                    director,
                    keywords,
                    collection,
                    is_synchronized,
                    editor_settings,
                    tmdb_id,
                    is_favorite,
                    related_tmdb
                )
                VALUES (
                    ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                    ?
                )
                """,
                (
                    item.title,
                    item.original_title,
                    item.english_title,
                    item.media_type.value,
                    item.release_year,
                    item.runtime_minutes,
                    item.watch_status.value,
                    item.rating,
                    item.notes,
                    item.english_description,
                    item.content_category,
                    json.dumps(list(item.cast_names)),
                    item.studio,
                    item.director,
                    json.dumps(list(item.keywords)),
                    item.collection,
                    int(item.is_synchronized),
                    json.dumps(item.editor_settings or {}),
                    item.tmdb_id,
                    int(item.is_favorite),
                    _serialize_related(item.related_tmdb),
                ),
            )

            if cursor.lastrowid is None:
                raise RuntimeError(
                    "SQLite nije vratio ID novog FILMIUM sadržaja."
                )

            item_id = cursor.lastrowid

            self._replace_genres(
                connection,
                item_id,
                item.genres,
            )

            row = connection.execute(
                """
                SELECT *
                FROM filmium_media_items
                WHERE id = ?
                """,
                (item_id,),
            ).fetchone()

            genres = self._load_genres(
                connection,
                (item_id,),
            ).get(item_id, ())

        if row is None:
            raise RuntimeError(
                "Novi FILMIUM sadržaj nije pronađen nakon upisa."
            )

        return self._row_to_media_item(row, genres)
    

    def update(
        self,
        item_id: int,
        item: MediaItemCreate,
    ) -> MediaItem | None:
        """Menja postojeći FILMIUM sadržaj."""

        with core_database_connection(self._database_path) as connection:
            cursor = connection.execute(
                """
                UPDATE filmium_media_items
                SET
                    title = ?,
                    original_title = ?,
                    english_title = ?,
                    media_type = ?,
                    release_year = ?,
                    runtime_minutes = ?,
                    watch_status = ?,
                    rating = ?,
                    notes = ?,
                    english_description = ?,
                    content_category = ?,
                    cast_names = ?,
                    studio = ?,
                    director = ?,
                    keywords = ?,
                    collection = ?,
                    is_synchronized = ?,
                    editor_settings = ?,
                    tmdb_id = ?,
                    is_favorite = ?,
                    related_tmdb = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (
                    item.title,
                    item.original_title,
                    item.english_title,
                    item.media_type.value,
                    item.release_year,
                    item.runtime_minutes,
                    item.watch_status.value,
                    item.rating,
                    item.notes,
                    item.english_description,
                    item.content_category,
                    json.dumps(list(item.cast_names)),
                    item.studio,
                    item.director,
                    json.dumps(list(item.keywords)),
                    item.collection,
                    int(item.is_synchronized),
                    json.dumps(item.editor_settings or {}),
                    item.tmdb_id,
                    int(item.is_favorite),
                    _serialize_related(item.related_tmdb),
                    item_id,
                ),
            )

            if cursor.rowcount == 0:
                return None

            self._replace_genres(
                connection,
                item_id,
                item.genres,
            )

            row = connection.execute(
                """
                SELECT *
                FROM filmium_media_items
                WHERE id = ?
                """,
                (item_id,),
            ).fetchone()

            genres = self._load_genres(
                connection,
                (item_id,),
            ).get(item_id, ())

        if row is None:
            return None

        return self._row_to_media_item(row, genres)



    def set_favorite_status(
        self,
        item_id: int,
        is_favorite: bool,
    ) -> MediaItem | None:
        """
        Menja samo favorite status FILMIUM sadržaja.

        Args:
            item_id: ID sadržaja koji se menja.
            is_favorite: Novi favorite status.

        Returns:
            Ažurirani sadržaj ako postoji, inače None.
        """

        with core_database_connection(self._database_path) as connection:
            cursor = connection.execute(
                """
                UPDATE filmium_media_items
                SET
                    is_favorite = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (
                    int(is_favorite),
                    item_id,
                ),
            )

            if cursor.rowcount == 0:
                return None

            row = connection.execute(
                """
                SELECT *
                FROM filmium_media_items
                WHERE id = ?
                """,
                (item_id,),
            ).fetchone()

            genres = self._load_genres(
                connection,
                (item_id,),
            ).get(item_id, ())

        if row is None:
            return None

        return self._row_to_media_item(row, genres)


    def update_keywords(
        self,
        item_id: int,
        keywords: tuple[str, ...],
        editor_settings: dict,
    ) -> MediaItem | None:
        """Menja SAMO ključne reči i editor_settings (ne dira ostala polja).

        Koristi se za dodavanje korisničkih ključnih reči sa stranice detalja
        bez rizika da se prepišu drugi podaci (kao kod punog update-a).
        """

        with core_database_connection(self._database_path) as connection:
            cursor = connection.execute(
                """
                UPDATE filmium_media_items
                SET
                    keywords = ?,
                    editor_settings = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (
                    json.dumps(list(keywords)),
                    json.dumps(editor_settings or {}),
                    item_id,
                ),
            )

            if cursor.rowcount == 0:
                return None

            row = connection.execute(
                "SELECT * FROM filmium_media_items WHERE id = ?",
                (item_id,),
            ).fetchone()

            genres = self._load_genres(
                connection,
                (item_id,),
            ).get(item_id, ())

        if row is None:
            return None

        return self._row_to_media_item(row, genres)


    def set_visual_assets(
        self,
        item_id: int,
        poster_path: str | None,
        backdrop_path: str | None,
    ) -> MediaItem | None:
        """
        Povezuje poster i backdrop sa FILMIUM sadržajem.

        Args:
            item_id: ID sadržaja koji dobija vizuelne assete.
            poster_path: Relativna putanja sačuvanog postera.
            backdrop_path: Relativna putanja sačuvanog backdropa.

        Returns:
            Ažurirani sadržaj ako postoji, inače None.
        """

        with core_database_connection(self._database_path) as connection:
            cursor = connection.execute(
                """
                UPDATE filmium_media_items
                SET
                    poster_path = ?,
                    backdrop_path = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (
                    poster_path,
                    backdrop_path,
                    item_id,
                ),
            )

            if cursor.rowcount == 0:
                return None

            row = connection.execute(
                """
                SELECT *
                FROM filmium_media_items
                WHERE id = ?
                """,
                (item_id,),
            ).fetchone()

            genres = self._load_genres(
                connection,
                (item_id,),
            ).get(item_id, ())

        if row is None:
            return None

        return self._row_to_media_item(row, genres)





    def delete(self, item_id: int) -> bool:
        """Briše FILMIUM sadržaj po ID-u."""

        with core_database_connection(self._database_path) as connection:
            cursor = connection.execute(
                """
                DELETE FROM filmium_media_items
                WHERE id = ?
                """,
                (item_id,),
            )

        return cursor.rowcount > 0

    def list_all(self) -> list[MediaItem]:
        """Vraća sve sadržaje iz FILMIUM kataloga."""

        with core_database_connection(self._database_path) as connection:
            rows = connection.execute(
                """
                SELECT *
                FROM filmium_media_items
                ORDER BY created_at DESC, id DESC
                """
            ).fetchall()

            item_ids = tuple(row["id"] for row in rows)
            genres_by_item = self._load_genres(
                connection,
                item_ids,
            )

        return [
            self._row_to_media_item(
                row,
                genres_by_item.get(row["id"], ()),
            )
            for row in rows
        ]

    def get_by_id(self, item_id: int) -> MediaItem | None:
        """Pronalazi FILMIUM sadržaj po ID-u."""

        with core_database_connection(self._database_path) as connection:
            row = connection.execute(
                """
                SELECT *
                FROM filmium_media_items
                WHERE id = ?
                """,
                (item_id,),
            ).fetchone()

            genres = self._load_genres(
                connection,
                (item_id,),
            ).get(item_id, ())

        if row is None:
            return None

        return self._row_to_media_item(row, genres)

    # ==========          ŽANROVI          ==========

    def list_active_genres(self) -> tuple[str, ...]:
        """
        Vraća aktivne FILMIUM žanrove dozvoljene za izbor.

        Žanrovi se vraćaju prema definisanom redosledu, a zatim
        abecedno ako imaju isti redni broj.
        """

        with core_database_connection(self._database_path) as connection:
            rows = connection.execute(
                """
                SELECT name
                FROM filmium_genres
                WHERE is_active = 1
                ORDER BY
                    sort_order,
                    name COLLATE NOCASE
                """
            ).fetchall()

        return tuple(row["name"] for row in rows)

    @staticmethod
    def _replace_genres(
        connection: sqlite3.Connection,
        item_id: int,
        genres: tuple[str, ...],
    ) -> None:
        """Zamenjuje veze koristeći samo aktivne FILMIUM žanrove."""

        connection.execute(
            """
            DELETE FROM filmium_media_genres
            WHERE media_id = ?
            """,
            (item_id,),
        )

        for genre in genres:
            genre_row = connection.execute(
                """
                SELECT id
                FROM filmium_genres
                WHERE
                    name = ? COLLATE NOCASE
                    AND is_active = 1
                """,
                (genre,),
            ).fetchone()

            if genre_row is None:
                raise RuntimeError(
                    f"Aktivan FILMIUM žanr nije pronađen: {genre}"
                )

            connection.execute(
                """
                INSERT INTO filmium_media_genres (
                    media_id,
                    genre_id
                )
                VALUES (?, ?)
                """,
                (
                    item_id,
                    genre_row["id"],
                ),
            )

    @staticmethod
    def _load_genres(
        connection: sqlite3.Connection,
        item_ids: tuple[int, ...],
    ) -> dict[int, tuple[str, ...]]:
        """Učitava žanrove za više FILMIUM sadržaja jednim upitom."""

        if not item_ids:
            return {}

        placeholders = ", ".join("?" for _ in item_ids)

        rows = connection.execute(
            f"""
            SELECT
                media_genres.media_id,
                genres.name
            FROM filmium_media_genres AS media_genres
            JOIN filmium_genres AS genres
                ON genres.id = media_genres.genre_id
            WHERE media_genres.media_id IN ({placeholders})
            ORDER BY
                media_genres.media_id,
                genres.name COLLATE NOCASE
            """,
            item_ids,
        ).fetchall()

        genres_by_item: dict[int, list[str]] = {
            item_id: []
            for item_id in item_ids
        }

        for row in rows:
            genres_by_item[row["media_id"]].append(row["name"])

        return {
            item_id: tuple(genres)
            for item_id, genres in genres_by_item.items()
        }

    # ==========          MODEL MAPIRANJE          ==========

    @staticmethod
    def _row_to_media_item(
        row: sqlite3.Row,
        genres: tuple[str, ...],
    ) -> MediaItem:
        """Pretvara SQLite red u FILMIUM domenski model."""

        return MediaItem(
            id=row["id"],
            title=row["title"],
            original_title=row["original_title"],
            media_type=MediaType(row["media_type"]),
            release_year=row["release_year"],
            runtime_minutes=row["runtime_minutes"],
            watch_status=WatchStatus(row["watch_status"]),
            rating=row["rating"],
            notes=row["notes"],
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
            genres=genres,
            is_favorite=bool(row["is_favorite"]),
            poster_path=row["poster_path"],
            backdrop_path=row["backdrop_path"],
            english_title=row["english_title"],
            english_description=row["english_description"],
            content_category=row["content_category"],
            cast_names=_parse_cast_names(row["cast_names"]),
            studio=row["studio"],
            director=row["director"],
            keywords=_parse_cast_names(row["keywords"]),
            collection=row["collection"],
            is_synchronized=bool(row["is_synchronized"]),
            editor_settings=_parse_editor_settings(row["editor_settings"]),
            tmdb_id=row["tmdb_id"],
            related_tmdb=_parse_related(row["related_tmdb"]),
        )