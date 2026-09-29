# ========== PODEŠAVANJA TORRENT MODULA ==========
# Jedan red u bazi (id = 1). Backend ih čita i kada GUI nije otvoren.
from __future__ import annotations

from pathlib import Path

from core.database import core_database_connection
from core.domains.filmium.torrents.torrent_models import (
    TorrentSettings,
)


def _split_extensions(raw: str) -> tuple[str, ...]:
    parts = [part.strip() for part in raw.split(",")]
    return tuple(part for part in parts if part)


def _split_folders(raw: str) -> tuple[str, ...]:
    """Putanje razdvojene novim redom; zarez se NE koristi jer sme u imenu."""

    parts = [part.strip() for part in raw.splitlines()]
    return tuple(part for part in parts if part)


# ========== STORE ==========
class TorrentSettingsStore:
    """Čita i upisuje podešavanja torrent modula."""

    def __init__(self, database_path: Path | None = None) -> None:
        self._database_path = database_path

    def _conn(self):
        return core_database_connection(self._database_path)

    def load(self) -> TorrentSettings:
        with self._conn() as c:
            row = c.execute(
                "SELECT * FROM filmium_torrent_settings WHERE id = 1"
            ).fetchone()

        if row is None:
            return TorrentSettings()

        return TorrentSettings(
            host=str(row["host"]),
            port=int(row["port"]),
            username=str(row["username"]),
            password=str(row["password"]),
            watch_folders=_split_folders(str(row["watch_folders"])),
            download_path=str(row["download_path"]),
            max_download_kbs=int(row["max_download_kbs"]),
            max_upload_kbs=int(row["max_upload_kbs"]),
            max_active=int(row["max_active"]),
            auto_start=bool(row["auto_start"]),
            seed_after_complete=bool(row["seed_after_complete"]),
            delete_source_torrent=bool(row["delete_source_torrent"]),
            unselected_extensions=_split_extensions(
                str(row["unselected_extensions"])
            ),
        )

    def save(self, settings: TorrentSettings) -> TorrentSettings:
        with self._conn() as c:
            c.execute(
                """
                UPDATE filmium_torrent_settings SET
                    host = ?, port = ?, username = ?, password = ?,
                    watch_folders = ?, download_path = ?,
                    max_download_kbs = ?, max_upload_kbs = ?, max_active = ?,
                    auto_start = ?, seed_after_complete = ?,
                    delete_source_torrent = ?, unselected_extensions = ?
                WHERE id = 1
                """,
                (
                    settings.host,
                    int(settings.port),
                    settings.username,
                    settings.password,
                    "\n".join(settings.watch_folders),
                    settings.download_path,
                    int(settings.max_download_kbs),
                    int(settings.max_upload_kbs),
                    int(settings.max_active),
                    int(settings.auto_start),
                    int(settings.seed_after_complete),
                    int(settings.delete_source_torrent),
                    ",".join(settings.unselected_extensions),
                ),
            )
        return self.load()
