import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

from core.database import core_database_connection
from core.domains.filmium.activity_models import (
    ActivityCreate,
    ActivityEntityType,
    ActivityEventType,
    ActivityItem,
)

# ==========          FILMIUM ACTIVITY REPOSITORY          ==========

class ActivityRepository:
    """Čuva i učitava FILMIUM istoriju aktivnosti iz SQLite baze."""

    def __init__(self, database_path: Path | None = None) -> None:
        """
        Inicijalizuje activity repository.

        Args:
            database_path: Opciona putanja baze, prvenstveno za testiranje.
        """

        self._database_path = database_path

    def create(self, activity: ActivityCreate) -> ActivityItem:
        """
        Trajno beleži novi FILMIUM događaj.

        Args:
            activity: Događaj koji treba sačuvati.

        Returns:
            Sačuvani activity zapis.
        """

        metadata_json = json.dumps(
            activity.metadata,
            ensure_ascii=False,
            separators=(",", ":"),
        )

        with core_database_connection(self._database_path) as connection:
            cursor = connection.execute(
                """
                INSERT INTO filmium_activity (
                    event_type,
                    entity_type,
                    entity_id,
                    title,
                    metadata_json
                )
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    activity.event_type.value,
                    activity.entity_type.value,
                    activity.entity_id,
                    activity.title,
                    metadata_json,
                ),
            )

            if cursor.lastrowid is None:
                raise RuntimeError(
                    "SQLite nije vratio ID FILMIUM activity zapisa."
                )

            row = connection.execute(
                """
                SELECT *
                FROM filmium_activity
                WHERE id = ?
                """,
                (cursor.lastrowid,),
            ).fetchone()

        if row is None:
            raise RuntimeError(
                "FILMIUM activity zapis nije pronađen nakon upisa."
            )

        return self._row_to_activity_item(row)

    def list_recent(self, limit: int = 100) -> list[ActivityItem]:
        """
        Vraća najnovije FILMIUM događaje.

        Args:
            limit: Najveći broj zapisa koji treba vratiti.

        Returns:
            Activity zapisi poređani od najnovijeg ka najstarijem.
        """

        with core_database_connection(self._database_path) as connection:
            rows = connection.execute(
                """
                SELECT *
                FROM filmium_activity
                ORDER BY created_at DESC, id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()

        return [
            self._row_to_activity_item(row)
            for row in rows
        ]

    # ==========          ACTIVITY MODEL MAPIRANJE          ==========

    @staticmethod
    def _row_to_activity_item(
        row: sqlite3.Row,
    ) -> ActivityItem:
        """Pretvara SQLite red u FILMIUM activity model."""

        metadata: Any = json.loads(row["metadata_json"])

        if not isinstance(metadata, dict):
            raise RuntimeError(  # noqa: TRY004
                "FILMIUM activity metadata mora biti JSON objekat."
            )

        return ActivityItem(
            id=row["id"],
            event_type=ActivityEventType(row["event_type"]),
            entity_type=ActivityEntityType(row["entity_type"]),
            entity_id=row["entity_id"],
            title=row["title"],
            metadata=metadata,
            created_at=datetime.fromisoformat(row["created_at"]),
        )