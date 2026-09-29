# ========== TORRENT REPOZITORIJUM ==========
# CRUD za torrente i njihove fajlove (CORE SQLite baza).
from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path

from core.database import core_database_connection
from core.domains.filmium.torrents.torrent_models import (
    TorrentEntry,
    TorrentFileEntry,
    TorrentStatus,
)


def _to_datetime(raw: str | None) -> datetime | None:
    return datetime.fromisoformat(raw) if raw else None


# ========== REPOSITORY ==========
class TorrentRepository:
    """Perzistencija torrenta koje je FILMIUM dodao i njihovih fajlova."""

    def __init__(self, database_path: Path | None = None) -> None:
        self._database_path = database_path

    def _conn(self):
        return core_database_connection(self._database_path)

    # ---------- torrenti ----------
    def upsert(self, entry: TorrentEntry) -> TorrentEntry:
        with self._conn() as c:
            c.execute(
                """
                INSERT INTO filmium_torrents (
                    info_hash, name, source, source_kind, status,
                    save_path, total_bytes, added_at, completed_at,
                    error_message, archived_path
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(info_hash) DO UPDATE SET
                    name = excluded.name,
                    source = excluded.source,
                    source_kind = excluded.source_kind,
                    status = excluded.status,
                    save_path = excluded.save_path,
                    total_bytes = excluded.total_bytes,
                    completed_at = excluded.completed_at,
                    error_message = excluded.error_message,
                    archived_path = excluded.archived_path
                """,
                (
                    entry.info_hash,
                    entry.name,
                    entry.source,
                    entry.source_kind,
                    entry.status.value,
                    entry.save_path,
                    int(entry.total_bytes),
                    entry.added_at.isoformat(),
                    entry.completed_at.isoformat() if entry.completed_at else None,
                    entry.error_message,
                    entry.archived_path,
                ),
            )
        return entry

    def get(self, info_hash: str) -> TorrentEntry | None:
        with self._conn() as c:
            row = c.execute(
                "SELECT * FROM filmium_torrents WHERE info_hash = ?",
                (info_hash,),
            ).fetchone()
        return self._from_row(row) if row else None

    def list(self, status: TorrentStatus | None = None) -> list[TorrentEntry]:
        query = "SELECT * FROM filmium_torrents"
        params: tuple = ()
        if status is not None:
            query += " WHERE status = ?"
            params = (status.value,)
        query += " ORDER BY added_at DESC"

        with self._conn() as c:
            rows = c.execute(query, params).fetchall()
        return [self._from_row(row) for row in rows]

    def update_status(
        self,
        info_hash: str,
        status: TorrentStatus,
        *,
        error_message: str | None = None,
        completed_at: datetime | None = None,
    ) -> None:
        with self._conn() as c:
            c.execute(
                """
                UPDATE filmium_torrents
                SET status = ?, error_message = ?, completed_at = ?
                WHERE info_hash = ?
                """,
                (
                    status.value,
                    error_message,
                    completed_at.isoformat() if completed_at else None,
                    info_hash,
                ),
            )

    def delete(self, info_hash: str) -> None:
        with self._conn() as c:
            c.execute(
                "DELETE FROM filmium_torrent_files WHERE info_hash = ?",
                (info_hash,),
            )
            c.execute(
                "DELETE FROM filmium_torrents WHERE info_hash = ?",
                (info_hash,),
            )

    # ---------- fajlovi ----------
    def replace_files(
        self,
        info_hash: str,
        files: list[TorrentFileEntry],
    ) -> None:
        with self._conn() as c:
            c.execute(
                "DELETE FROM filmium_torrent_files WHERE info_hash = ?",
                (info_hash,),
            )
            c.executemany(
                """
                INSERT INTO filmium_torrent_files (
                    info_hash, file_index, path, size_bytes, selected
                ) VALUES (?, ?, ?, ?, ?)
                """,
                [
                    (
                        info_hash,
                        item.file_index,
                        item.path,
                        int(item.size_bytes),
                        int(item.selected),
                    )
                    for item in files
                ],
            )

    def list_files(self, info_hash: str) -> list[TorrentFileEntry]:
        with self._conn() as c:
            rows = c.execute(
                """
                SELECT file_index, path, size_bytes, selected
                FROM filmium_torrent_files
                WHERE info_hash = ?
                ORDER BY file_index
                """,
                (info_hash,),
            ).fetchall()
        return [
            TorrentFileEntry(
                file_index=int(row[0]),
                path=str(row[1]),
                size_bytes=int(row[2]),
                selected=bool(row[3]),
            )
            for row in rows
        ]

    def set_selected(self, info_hash: str, selected_indexes: list[int]) -> None:
        wanted = set(selected_indexes)
        with self._conn() as c:
            rows = c.execute(
                "SELECT file_index FROM filmium_torrent_files WHERE info_hash = ?",
                (info_hash,),
            ).fetchall()
            c.executemany(
                """
                UPDATE filmium_torrent_files
                SET selected = ?
                WHERE info_hash = ? AND file_index = ?
                """,
                [
                    (int(int(row[0]) in wanted), info_hash, int(row[0]))
                    for row in rows
                ],
            )

    # ---------- predaja uvozu ----------
    def mark_handoff(self, info_hash: str, moment: datetime) -> None:
        """Beleži da je torrent poslat ka ekranu uvoza u biblioteku."""

        with self._conn() as c:
            c.execute(
                """
                INSERT INTO filmium_torrent_handoffs (info_hash, handed_at)
                VALUES (?, ?)
                ON CONFLICT(info_hash) DO UPDATE SET handed_at = excluded.handed_at
                """,
                (info_hash, moment.isoformat()),
            )

    def is_handed_off(self, info_hash: str) -> bool:
        with self._conn() as c:
            row = c.execute(
                "SELECT 1 FROM filmium_torrent_handoffs WHERE info_hash = ?",
                (info_hash,),
            ).fetchone()
        return row is not None

    def handed_off_hashes(self) -> set[str]:
        with self._conn() as c:
            rows = c.execute(
                "SELECT info_hash FROM filmium_torrent_handoffs"
            ).fetchall()
        return {str(row[0]).lower() for row in rows}

    def clear_handoff(self, info_hash: str) -> None:
        with self._conn() as c:
            c.execute(
                "DELETE FROM filmium_torrent_handoffs WHERE info_hash = ?",
                (info_hash,),
            )

    # ---------- mapiranje ----------
    @staticmethod
    def _from_row(row: sqlite3.Row) -> TorrentEntry:
        return TorrentEntry(
            info_hash=str(row["info_hash"]),
            name=str(row["name"]),
            source=str(row["source"]),
            source_kind=str(row["source_kind"]),
            status=TorrentStatus(str(row["status"])),
            save_path=str(row["save_path"]),
            total_bytes=int(row["total_bytes"]),
            added_at=_to_datetime(row["added_at"]) or datetime.now(),  # noqa: DTZ005
            completed_at=_to_datetime(row["completed_at"]),
            error_message=row["error_message"],
            archived_path=str(row["archived_path"] or ""),
        )
