import sqlite3
from datetime import datetime
from pathlib import Path

from core.database import core_database_connection
from core.domains.filmium.subtitle_repair_queue_models import (
    SubtitleRepairQueueCreate,
    SubtitleRepairQueueItem,
    SubtitleRepairQueueStatus,
)

# ==========          REPOSITORY REDA POPRAVKE          ==========

class SubtitleRepairQueueRepository:
    """Cuva problematcne prevode i njihove odluke u SQLite bazi."""

    def __init__(self, database_path: Path | None = None) -> None:
        self._database_path = database_path

    def upsert(
        self,
        item: SubtitleRepairQueueCreate,
    ) -> SubtitleRepairQueueItem:
        """Dodaje nalaz ili osvezava postojecu putanju bez duplikata."""

        with core_database_connection(self._database_path) as connection:
            connection.execute(
                """
                INSERT INTO filmium_subtitle_repair_queue (
                    media_id,
                    source_id,
                    file_path,
                    file_name,
                    source_sha256,
                    detected_encoding,
                    detected_language_code,
                    language_confidence,
                    issue_count
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(file_path) DO UPDATE SET
                    media_id = COALESCE(
                        excluded.media_id,
                        filmium_subtitle_repair_queue.media_id
                    ),
                    source_id = COALESCE(
                        excluded.source_id,
                        filmium_subtitle_repair_queue.source_id
                    ),
                    file_name = excluded.file_name,
                    detected_encoding = excluded.detected_encoding,
                    detected_language_code =
                        excluded.detected_language_code,
                    language_confidence = excluded.language_confidence,
                    issue_count = excluded.issue_count,
                    status = CASE
                        WHEN filmium_subtitle_repair_queue.status = 'ignored'
                            THEN 'ignored'
                        WHEN filmium_subtitle_repair_queue.source_sha256
                            <> excluded.source_sha256
                            THEN 'pending'
                        ELSE filmium_subtitle_repair_queue.status
                    END,
                    discovered_at = CASE
                        WHEN filmium_subtitle_repair_queue.source_sha256
                            <> excluded.source_sha256
                            THEN CURRENT_TIMESTAMP
                        ELSE filmium_subtitle_repair_queue.discovered_at
                    END,
                    reviewed_at = CASE
                        WHEN filmium_subtitle_repair_queue.source_sha256
                            <> excluded.source_sha256
                            AND filmium_subtitle_repair_queue.status
                                <> 'ignored'
                            THEN NULL
                        ELSE filmium_subtitle_repair_queue.reviewed_at
                    END,
                    resolved_at = CASE
                        WHEN filmium_subtitle_repair_queue.source_sha256
                            <> excluded.source_sha256
                            AND filmium_subtitle_repair_queue.status
                                <> 'ignored'
                            THEN NULL
                        ELSE filmium_subtitle_repair_queue.resolved_at
                    END,
                    source_sha256 = excluded.source_sha256,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (
                    item.media_id,
                    item.source_id,
                    item.file_path,
                    item.file_name,
                    item.source_sha256,
                    item.detected_encoding,
                    item.detected_language_code,
                    item.language_confidence,
                    item.issue_count,
                ),
            )
            row = connection.execute(
                """
                SELECT *
                FROM filmium_subtitle_repair_queue
                WHERE file_path = ? COLLATE NOCASE
                """,
                (item.file_path,),
            ).fetchone()

        if row is None:
            raise RuntimeError(
                "Stavka reda nije pronadjena nakon upisa."
            )

        return self._row_to_item(row)

    def get(
        self,
        item_id: int,
    ) -> SubtitleRepairQueueItem | None:
        """Ucitava jednu stavku reda."""

        with core_database_connection(self._database_path) as connection:
            row = connection.execute(
                """
                SELECT *
                FROM filmium_subtitle_repair_queue
                WHERE id = ?
                """,
                (item_id,),
            ).fetchone()

        return None if row is None else self._row_to_item(row)


    def get_by_path(
        self,
        file_path: str,
    ) -> SubtitleRepairQueueItem | None:
        """Ucitava postojecu odluku za jednu punu putanju."""

        with core_database_connection(self._database_path) as connection:
            row = connection.execute(
                """
                SELECT *
                FROM filmium_subtitle_repair_queue
                WHERE file_path = ? COLLATE NOCASE
                """,
                (file_path,),
            ).fetchone()

        return None if row is None else self._row_to_item(row)

    
    def list_items(
        self,
        status: SubtitleRepairQueueStatus | None = None,
    ) -> tuple[SubtitleRepairQueueItem, ...]:
        """Vraca ceo red ili samo stavke jednog statusa."""

        query = """
            SELECT *
            FROM filmium_subtitle_repair_queue
        """
        parameters: tuple[object, ...] = ()

        if status is not None:
            query += " WHERE status = ?"
            parameters = (status.value,)

        query += " ORDER BY discovered_at DESC, id DESC"

        with core_database_connection(self._database_path) as connection:
            rows = connection.execute(query, parameters).fetchall()

        return tuple(self._row_to_item(row) for row in rows)

    def set_status(
        self,
        item_id: int,
        status: SubtitleRepairQueueStatus,
    ) -> SubtitleRepairQueueItem | None:
        """Menja odluku i odgovarajuce vremenske oznake."""

        reviewed_at_sql = (
            "CURRENT_TIMESTAMP"
            if status == SubtitleRepairQueueStatus.REVIEWED
            else "reviewed_at"
        )
        resolved_at_sql = (
            "CURRENT_TIMESTAMP"
            if status
            in {
                SubtitleRepairQueueStatus.REPAIRED,
                SubtitleRepairQueueStatus.DISMISSED,
                SubtitleRepairQueueStatus.IGNORED,
            }
            else "NULL"
        )

        with core_database_connection(self._database_path) as connection:
            cursor = connection.execute(
                f"""
                UPDATE filmium_subtitle_repair_queue
                SET
                    status = ?,
                    reviewed_at = {reviewed_at_sql},
                    resolved_at = {resolved_at_sql},
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (status.value, item_id),
            )

            if cursor.rowcount == 0:
                return None

            row = connection.execute(
                """
                SELECT *
                FROM filmium_subtitle_repair_queue
                WHERE id = ?
                """,
                (item_id,),
            ).fetchone()

        return None if row is None else self._row_to_item(row)

    def clear_scan_results(self) -> int:
        """Brise nalaze skeniranja, ali cuva ignorisane i popravljene stavke."""

        removable_statuses = (
            SubtitleRepairQueueStatus.PENDING.value,
            SubtitleRepairQueueStatus.REVIEWED.value,
            SubtitleRepairQueueStatus.DISMISSED.value,
        )

        with core_database_connection(self._database_path) as connection:
            cursor = connection.execute(
                """
                DELETE FROM filmium_subtitle_repair_queue
                WHERE status IN (?, ?, ?)
                """,
                removable_statuses,
            )

        return max(cursor.rowcount, 0)

    @staticmethod
    def _optional_datetime(value: object) -> datetime | None:
        return (
            None
            if value is None
            else datetime.fromisoformat(str(value))
        )

    @classmethod
    def _row_to_item(
        cls,
        row: sqlite3.Row,
    ) -> SubtitleRepairQueueItem:
        return SubtitleRepairQueueItem(
            id=int(row["id"]),
            media_id=(
                None
                if row["media_id"] is None
                else int(row["media_id"])
            ),
            source_id=(
                None
                if row["source_id"] is None
                else int(row["source_id"])
            ),
            file_path=str(row["file_path"]),
            file_name=str(row["file_name"]),
            source_sha256=str(row["source_sha256"]),
            detected_encoding=str(row["detected_encoding"]),
            detected_language_code=(
                None
                if row["detected_language_code"] is None
                else str(row["detected_language_code"])
            ),
            language_confidence=float(row["language_confidence"]),
            issue_count=int(row["issue_count"]),
            status=SubtitleRepairQueueStatus(row["status"]),
            discovered_at=datetime.fromisoformat(
                str(row["discovered_at"])
            ),
            updated_at=datetime.fromisoformat(str(row["updated_at"])),
            reviewed_at=cls._optional_datetime(row["reviewed_at"]),
            resolved_at=cls._optional_datetime(row["resolved_at"]),
        )
