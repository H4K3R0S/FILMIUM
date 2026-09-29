# ========== AUTO-IMPORT REPOSITORY ==========
# CRUD za pravila, praćene foldere i detektovane fajlove (CORE SQLite baza).
from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path

from core.database import core_database_connection
from core.domains.filmium.auto_import.auto_import_models import (
    AutoImportRule,
    AutoImportRuleCreate,
    DetectedFile,
    DetectedFileStatus,
    SecurityStatus,
)


# ========== REPOSITORY ==========
class AutoImportRepository:
    """Perzistencija auto-import konfiguracije i detektovanih fajlova."""

    def __init__(self, database_path: Path | None = None) -> None:
        self._database_path = database_path

    def _conn(self):
        return core_database_connection(self._database_path)

    # ---------- pravila ----------
    def create_rule(self, item: AutoImportRuleCreate) -> AutoImportRule:
        with self._conn() as c:
            cur = c.execute(
                """
                INSERT INTO filmium_auto_import_rules (
                    folder_path, file_types, min_size_mb, auto_scan,
                    auto_import, target_library_id, security_scan
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    item.folder_path,
                    json.dumps(list(item.file_types)),
                    int(item.min_size_mb),
                    int(item.auto_scan),
                    int(item.auto_import),
                    item.target_library_id,
                    int(item.security_scan),
                ),
            )
            return self._rule_from_row(self._rule_row(c, int(cur.lastrowid)))

    def get_rule(self, rule_id: int) -> AutoImportRule | None:
        with self._conn() as c:
            row = self._rule_row(c, rule_id)
            return self._rule_from_row(row) if row else None

    def list_rules(self) -> list[AutoImportRule]:
        with self._conn() as c:
            rows = c.execute(
                "SELECT * FROM filmium_auto_import_rules ORDER BY id"
            ).fetchall()
            return [self._rule_from_row(r) for r in rows]

    def delete_rule(self, rule_id: int) -> None:
        with self._conn() as c:
            c.execute("DELETE FROM filmium_auto_import_rules WHERE id = ?", (rule_id,))

    # ---------- praćeni folderi (status) ----------
    def add_monitored_folder(self, folder_path: str, rule_id: int | None) -> None:
        with self._conn() as c:
            c.execute(
                """
                INSERT INTO filmium_monitored_folders (folder_path, is_active, rule_id, last_check)
                VALUES (?, 1, ?, ?)
                ON CONFLICT(folder_path) DO UPDATE SET is_active = 1, rule_id = excluded.rule_id
                """,
                (folder_path, rule_id, datetime.now().isoformat(timespec="seconds")),  # noqa: DTZ005
            )

    def remove_monitored_folder(self, folder_path: str) -> None:
        with self._conn() as c:
            c.execute("DELETE FROM filmium_monitored_folders WHERE folder_path = ?", (folder_path,))

    def list_monitored_folders(self) -> list[dict]:
        with self._conn() as c:
            rows = c.execute(
                "SELECT folder_path, is_active, rule_id, last_check FROM filmium_monitored_folders ORDER BY id"
            ).fetchall()
            return [
                {"folder_path": r["folder_path"], "is_active": bool(r["is_active"]),
                 "rule_id": r["rule_id"], "last_check": r["last_check"]}
                for r in rows
            ]

    # ---------- detektovani fajlovi ----------
    def upsert_detected(self, item: DetectedFile) -> DetectedFile:
        with self._conn() as c:
            cur = c.execute(
                """
                INSERT INTO filmium_detected_files (
                    file_path, file_size, status, security_status, scan_result, rule_id
                ) VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(file_path) DO UPDATE SET
                    file_size = excluded.file_size,
                    status = excluded.status,
                    security_status = excluded.security_status,
                    scan_result = excluded.scan_result,
                    rule_id = excluded.rule_id
                """,
                (
                    item.file_path, int(item.file_size), item.status.value,
                    item.security_status.value,
                    json.dumps(item.scan_result) if item.scan_result is not None else None,
                    item.rule_id,
                ),
            )
            rid = int(cur.lastrowid) if cur.lastrowid else self._detected_id(c, item.file_path)
            return self._detected_from_row(self._detected_row(c, rid))

    def get_detected(self, file_id: int) -> DetectedFile | None:
        with self._conn() as c:
            row = self._detected_row(c, file_id)
            return self._detected_from_row(row) if row else None

    def list_detected(self, status: DetectedFileStatus | None = None) -> list[DetectedFile]:
        with self._conn() as c:
            if status:
                rows = c.execute(
                    "SELECT * FROM filmium_detected_files WHERE status = ? ORDER BY id DESC",
                    (status.value,),
                ).fetchall()
            else:
                rows = c.execute(
                    "SELECT * FROM filmium_detected_files ORDER BY id DESC"
                ).fetchall()
            return [self._detected_from_row(r) for r in rows]

    def update_detected_status(self, file_id: int, status: DetectedFileStatus,
                               security_status: SecurityStatus | None = None,
                               scan_result: dict | None = None) -> DetectedFile | None:
        with self._conn() as c:
            row = self._detected_row(c, file_id)
            if not row:
                return None
            sec = security_status.value if security_status else row["security_status"]
            scan = json.dumps(scan_result) if scan_result is not None else row["scan_result"]
            c.execute(
                "UPDATE filmium_detected_files SET status = ?, security_status = ?, scan_result = ? WHERE id = ?",
                (status.value, sec, scan, file_id),
            )
            return self._detected_from_row(self._detected_row(c, file_id))

    # ---------- helpers ----------
    @staticmethod
    def _rule_row(c: sqlite3.Connection, rule_id: int):
        return c.execute("SELECT * FROM filmium_auto_import_rules WHERE id = ?", (rule_id,)).fetchone()

    @staticmethod
    def _detected_row(c: sqlite3.Connection, file_id: int):
        return c.execute("SELECT * FROM filmium_detected_files WHERE id = ?", (file_id,)).fetchone()

    @staticmethod
    def _detected_id(c: sqlite3.Connection, file_path: str) -> int:
        r = c.execute("SELECT id FROM filmium_detected_files WHERE file_path = ?", (file_path,)).fetchone()
        return int(r["id"]) if r else 0

    @staticmethod
    def _rule_from_row(row) -> AutoImportRule:
        return AutoImportRule(
            id=int(row["id"]),
            folder_path=row["folder_path"],
            file_types=json.loads(row["file_types"]) if row["file_types"] else [],
            min_size_mb=int(row["min_size_mb"]),
            auto_scan=bool(row["auto_scan"]),
            auto_import=bool(row["auto_import"]),
            target_library_id=row["target_library_id"],
            security_scan=bool(row["security_scan"]),
            created_at=_parse_dt(row["created_at"]),
        )

    @staticmethod
    def _detected_from_row(row) -> DetectedFile:
        return DetectedFile(
            id=int(row["id"]),
            file_path=row["file_path"],
            file_size=int(row["file_size"]),
            rule_id=row["rule_id"],
            status=DetectedFileStatus(row["status"]),
            security_status=SecurityStatus(row["security_status"]),
            scan_result=json.loads(row["scan_result"]) if row["scan_result"] else None,
            detected_at=_parse_dt(row["detected_at"]),
        )


def _parse_dt(value) -> datetime:
    if isinstance(value, datetime):
        return value
    try:
        return datetime.fromisoformat(str(value).replace(" ", "T"))
    except (ValueError, TypeError):
        return datetime.now()  # noqa: DTZ005
