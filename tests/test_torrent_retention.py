"""Auto-uklanjanje ZAVRŠENIH torrenta 24h posle završetka.

Kartica i qBittorrent zapis odlaze, preuzeti fajlovi OSTAJU na disku
(`delete_files=False`).
"""

from __future__ import annotations

from datetime import datetime, timedelta

from core.domains.filmium.torrents.torrent_archive import TorrentArchive
from core.domains.filmium.torrents.torrent_models import (
    TorrentEntry,
    TorrentSettings,
    TorrentStatus,
)
from core.domains.filmium.torrents.torrent_reconcile import (
    COMPLETED_RETENTION_SECONDS,
)
from core.domains.filmium.torrents.torrent_service import TorrentService


# ========== FAKE-OVI ==========
class _FakeRepository:
    def __init__(self, entries: list[TorrentEntry]) -> None:
        self._entries = {entry.info_hash: entry for entry in entries}

    def list(self, status: TorrentStatus | None = None) -> list[TorrentEntry]:
        rows = list(self._entries.values())
        if status is None:
            return rows
        return [row for row in rows if row.status is status]

    def get(self, info_hash: str) -> TorrentEntry | None:
        return self._entries.get(info_hash)

    def delete(self, info_hash: str) -> None:
        self._entries.pop(info_hash, None)


class _FakeEngine:
    def __init__(self) -> None:
        self.removed: list[tuple[str, bool]] = []

    def poll_status(self):
        return []

    def remove(self, info_hash: str, *, delete_files: bool) -> None:
        self.removed.append((info_hash, delete_files))


class _FakeSettingsStore:
    def load(self) -> TorrentSettings:
        return TorrentSettings()


def _service(entries: list[TorrentEntry], tmp_path) -> tuple[TorrentService, _FakeEngine, _FakeRepository]:
    repo = _FakeRepository(entries)
    engine = _FakeEngine()
    service = TorrentService(
        repo,
        engine,
        _FakeSettingsStore(),
        archive=TorrentArchive(folder=tmp_path),
    )
    return service, engine, repo


def _completed(info_hash: str, completed_at: datetime | None) -> TorrentEntry:
    return TorrentEntry(
        info_hash=info_hash,
        name=info_hash,
        source=f"magnet:?xt=urn:btih:{info_hash}",
        status=TorrentStatus.COMPLETED,
        completed_at=completed_at,
    )


# ========== TESTOVI ==========
def test_retention_is_24_hours() -> None:
    assert COMPLETED_RETENTION_SECONDS == 24 * 3600


def test_completed_older_than_24h_is_removed_keeping_files(tmp_path) -> None:
    now = datetime(2026, 1, 2, 12, 0, 0)  # noqa: DTZ001 — poklapa naive datetime.now() iz koda
    old = now - timedelta(hours=24, minutes=1)
    service, engine, repo = _service([_completed("aa", old)], tmp_path)

    service.poll(now=now)

    assert engine.removed == [("aa", False)]  # fajlovi se ČUVAJU
    assert repo.get("aa") is None  # kartica sklonjena


def test_completed_within_24h_is_kept(tmp_path) -> None:
    now = datetime(2026, 1, 2, 12, 0, 0)  # noqa: DTZ001 — poklapa naive datetime.now() iz koda
    fresh = now - timedelta(hours=1)
    service, engine, repo = _service([_completed("bb", fresh)], tmp_path)

    service.poll(now=now)

    assert engine.removed == []
    assert repo.get("bb") is not None


def test_completed_without_timestamp_is_kept(tmp_path) -> None:
    now = datetime(2026, 1, 2, 12, 0, 0)  # noqa: DTZ001 — poklapa naive datetime.now() iz koda
    service, engine, repo = _service([_completed("cc", None)], tmp_path)

    service.poll(now=now)

    assert engine.removed == []
    assert repo.get("cc") is not None
