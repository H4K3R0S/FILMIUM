import sqlite3
from datetime import datetime
from pathlib import Path

from core.database import core_database_connection
from core.domains.filmium.series_models import Season, SeasonCreate

# ==========          REPOZITORIJUM SEZONA          ==========

class SeasonRepository:
    """Čuva sezone serija u CORE bazi."""

    def __init__(self, database_path: Path | None = None) -> None:
        self._database_path = database_path

    def create(self, item: SeasonCreate) -> Season:
        with core_database_connection(self._database_path) as connection:
            cursor = connection.execute(
                """
                INSERT INTO filmium_seasons (
                    media_id, season_number, name
                )
                VALUES (?, ?, ?)
                """,
                (item.media_id, item.season_number, item.name),
            )

            if cursor.lastrowid is None:
                raise RuntimeError("SQLite nije vratio ID nove sezone.")

            row = connection.execute(
                "SELECT * FROM filmium_seasons WHERE id = ?",
                (cursor.lastrowid,),
            ).fetchone()

        if row is None:
            raise RuntimeError("Nova sezona nije pronađena nakon upisa.")

        return self._row_to_season(row)

    def ensure(
        self,
        media_id: int,
        season_number: int,
        name: str | None = None,
    ) -> Season:
        """Vraća postojeću sezonu ili je kreira ako ne postoji."""

        existing = self.get_by_number(media_id, season_number)

        if existing is not None:
            return existing

        return self.create(
            SeasonCreate(
                media_id=media_id,
                season_number=season_number,
                name=name,
            )
        )

    def get(self, season_id: int) -> Season | None:
        with core_database_connection(self._database_path) as connection:
            row = connection.execute(
                "SELECT * FROM filmium_seasons WHERE id = ?",
                (season_id,),
            ).fetchone()

        return None if row is None else self._row_to_season(row)

    def get_by_number(
        self,
        media_id: int,
        season_number: int,
    ) -> Season | None:
        with core_database_connection(self._database_path) as connection:
            row = connection.execute(
                """
                SELECT *
                FROM filmium_seasons
                WHERE media_id = ? AND season_number = ?
                """,
                (media_id, season_number),
            ).fetchone()

        return None if row is None else self._row_to_season(row)

    def list_for_media(self, media_id: int) -> tuple[Season, ...]:
        with core_database_connection(self._database_path) as connection:
            rows = connection.execute(
                """
                SELECT *
                FROM filmium_seasons
                WHERE media_id = ?
                ORDER BY season_number
                """,
                (media_id,),
            ).fetchall()

        return tuple(self._row_to_season(row) for row in rows)

    def set_visual_assets(
        self,
        season_id: int,
        *,
        poster_path: str | None = None,
        backdrop_path: str | None = None,
    ) -> Season | None:
        """Postavlja poster/backdrop sezone (samo prosleđene vrednosti)."""

        assignments: list[str] = []
        params: list[object] = []

        if poster_path is not None:
            assignments.append("poster_path = ?")
            params.append(poster_path)

        if backdrop_path is not None:
            assignments.append("backdrop_path = ?")
            params.append(backdrop_path)

        if not assignments:
            return self.get(season_id)

        assignments.append("updated_at = CURRENT_TIMESTAMP")
        params.append(season_id)

        with core_database_connection(self._database_path) as connection:
            connection.execute(
                f"""
                UPDATE filmium_seasons
                SET {", ".join(assignments)}
                WHERE id = ?
                """,
                tuple(params),
            )

        return self.get(season_id)

    def delete(self, season_id: int) -> bool:
        with core_database_connection(self._database_path) as connection:
            cursor = connection.execute(
                "DELETE FROM filmium_seasons WHERE id = ?",
                (season_id,),
            )

        return cursor.rowcount > 0

    @classmethod
    def _row_to_season(cls, row: sqlite3.Row) -> Season:
        keys = row.keys()
        return Season(
            id=int(row["id"]),
            media_id=int(row["media_id"]),
            season_number=int(row["season_number"]),
            name=row["name"],
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
            poster_path=(
                row["poster_path"] if "poster_path" in keys else None
            ),
            backdrop_path=(
                row["backdrop_path"] if "backdrop_path" in keys else None
            ),
        )
