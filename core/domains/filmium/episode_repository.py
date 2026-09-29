import sqlite3
from datetime import datetime
from pathlib import Path

from core.database import core_database_connection
from core.domains.filmium.models import WatchStatus
from core.domains.filmium.series_models import Episode, EpisodeCreate

# ==========          REPOZITORIJUM EPIZODA          ==========

class EpisodeRepository:
    """Čuva epizode sezona u CORE bazi."""

    def __init__(self, database_path: Path | None = None) -> None:
        self._database_path = database_path

    def create(self, item: EpisodeCreate) -> Episode:
        with core_database_connection(self._database_path) as connection:
            cursor = connection.execute(
                """
                INSERT INTO filmium_episodes (
                    season_id,
                    episode_number,
                    title,
                    runtime_minutes,
                    watch_status
                )
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    item.season_id,
                    item.episode_number,
                    item.title,
                    item.runtime_minutes,
                    item.watch_status.value,
                ),
            )

            if cursor.lastrowid is None:
                raise RuntimeError("SQLite nije vratio ID nove epizode.")

            row = connection.execute(
                "SELECT * FROM filmium_episodes WHERE id = ?",
                (cursor.lastrowid,),
            ).fetchone()

        if row is None:
            raise RuntimeError(
                "Nova epizoda nije pronađena nakon upisa."
            )

        return self._row_to_episode(row)

    def ensure(
        self,
        season_id: int,
        episode_number: int,
        title: str | None = None,
    ) -> Episode:
        """Vraća postojeću epizodu ili je kreira ako ne postoji."""

        existing = self.get_by_number(season_id, episode_number)

        if existing is not None:
            return existing

        return self.create(
            EpisodeCreate(
                season_id=season_id,
                episode_number=episode_number,
                title=title,
            )
        )

    def get(self, episode_id: int) -> Episode | None:
        with core_database_connection(self._database_path) as connection:
            row = connection.execute(
                "SELECT * FROM filmium_episodes WHERE id = ?",
                (episode_id,),
            ).fetchone()

        return None if row is None else self._row_to_episode(row)

    def get_by_number(
        self,
        season_id: int,
        episode_number: int,
    ) -> Episode | None:
        with core_database_connection(self._database_path) as connection:
            row = connection.execute(
                """
                SELECT *
                FROM filmium_episodes
                WHERE season_id = ? AND episode_number = ?
                """,
                (season_id, episode_number),
            ).fetchone()

        return None if row is None else self._row_to_episode(row)

    def list_for_season(self, season_id: int) -> tuple[Episode, ...]:
        with core_database_connection(self._database_path) as connection:
            rows = connection.execute(
                """
                SELECT *
                FROM filmium_episodes
                WHERE season_id = ?
                ORDER BY episode_number
                """,
                (season_id,),
            ).fetchall()

        return tuple(self._row_to_episode(row) for row in rows)

    def update(
        self,
        episode_id: int,
        *,
        title: str | None = None,
        runtime_minutes: int | None = None,
        watch_status: str | None = None,
    ) -> "Episode | None":
        """Menja polja epizode koja su prosleđena (parcijalni update)."""

        assignments: list[str] = []
        values: list[object] = []

        if title is not None:
            assignments.append("title = ?")
            values.append(title or None)
        if runtime_minutes is not None:
            assignments.append("runtime_minutes = ?")
            values.append(runtime_minutes)
        if watch_status is not None:
            assignments.append("watch_status = ?")
            values.append(watch_status)

        if not assignments:
            return self.get(episode_id)

        assignments.append("updated_at = CURRENT_TIMESTAMP")
        values.append(episode_id)

        with core_database_connection(self._database_path) as connection:
            cursor = connection.execute(
                f"""
                UPDATE filmium_episodes
                SET {", ".join(assignments)}
                WHERE id = ?
                """,
                tuple(values),
            )

            if cursor.rowcount == 0:
                return None

            row = connection.execute(
                "SELECT * FROM filmium_episodes WHERE id = ?",
                (episode_id,),
            ).fetchone()

        return None if row is None else self._row_to_episode(row)

    def delete(self, episode_id: int) -> bool:
        with core_database_connection(self._database_path) as connection:
            cursor = connection.execute(
                "DELETE FROM filmium_episodes WHERE id = ?",
                (episode_id,),
            )

        return cursor.rowcount > 0

    @classmethod
    def _row_to_episode(cls, row: sqlite3.Row) -> Episode:
        return Episode(
            id=int(row["id"]),
            season_id=int(row["season_id"]),
            episode_number=int(row["episode_number"]),
            title=row["title"],
            runtime_minutes=(
                None
                if row["runtime_minutes"] is None
                else int(row["runtime_minutes"])
            ),
            watch_status=WatchStatus(row["watch_status"]),
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )
