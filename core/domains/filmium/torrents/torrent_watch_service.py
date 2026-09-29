# ========== NADZOR FOLDERA ZA .torrent FAJLOVE ==========
# Nov .torrent u nekom od nadziranih foldera se SAMO javlja korisniku.
# Ništa ne odlazi u qBittorrent: fajl se na stranici Torrenti pojavljuje
# kao pronađena kartica, a skidanje kreće tek kad korisnik izabere fajlove.
from __future__ import annotations

import os
import time
from collections.abc import Callable

from core.domains.filmium.torrents.torrent_file_reader import (
    TORRENT_EXTENSION,
    read_torrent_file,
)
from core.domains.filmium.torrents.torrent_service import TorrentService
from core.system.file_monitor import FileMonitorService
from core.system.file_monitor.monitor_models import FileEvent, FileEventType

# `CREATED` stiže čim fajl nastane, a ne kad je kopiranje gotovo. Na
# delimično upisanom .torrent fajlu čitanje bencode zapisa pada, pa se čeka
# da se veličina ustali kroz dve uzastopne provere.
STABILITY_CHECKS = 20
STABILITY_DELAY_SECONDS = 0.2


# ========== WATCH SERVIS ==========
class TorrentWatchService:
    """Prati foldere iz podešavanja i javlja nove .torrent fajlove."""

    def __init__(
        self,
        service: TorrentService,
        file_monitor: FileMonitorService,
        *,
        notify: Callable[[str, str], None] | None = None,
        stability_delay: float = STABILITY_DELAY_SECONDS,
        stability_checks: int = STABILITY_CHECKS,
    ) -> None:
        self._service = service
        self._monitor = file_monitor
        self._notify = notify or (lambda _title, _message: None)
        self._folders: tuple[str, ...] = ()
        self._registered = False
        self._stability_delay = float(stability_delay)
        self._stability_checks = int(stability_checks)

    def start(self) -> bool:
        wanted = tuple(
            str(os.path.abspath(folder.strip()))
            for folder in self._service.settings().watch_folders
            if folder.strip() and os.path.isdir(folder.strip())
        )

        # Prethodni skup se UVEK prvo uredno zaustavi — inače bi izbacivanje
        # foldera iz podešavanja ostavilo staru putanju nadziranu zauvek.
        if self._folders and self._folders != wanted:
            self.stop()

        if not wanted:
            self.stop()
            return False

        if not self._registered:
            self._monitor.register_callback(
                FileEventType.CREATED,
                self.handle_event,
            )
            self._registered = True

        for folder in wanted:
            self._monitor.start_monitoring(folder, recursive=False)

        self._folders = wanted
        return True

    def restart(self) -> bool:
        """Ponovo pali nadzor nad putanjama iz (možda izmenjenih) podešavanja."""

        self.stop()
        return self.start()

    def stop(self) -> None:
        for folder in self._folders:
            self._monitor.stop_monitoring(folder)
        self._folders = ()

    @property
    def folders(self) -> tuple[str, ...]:
        return self._folders

    def handle_event(self, event: FileEvent) -> None:
        # Nijedan izuzetak ne sme da izađe: ovo se izvršava u niti
        # file monitor-a, gde bi je oborio.
        try:
            if event.is_directory:
                return
            if not event.src_path.lower().endswith(TORRENT_EXTENSION):
                return
            if not self._wait_until_stable(event.src_path):
                return

            found = read_torrent_file(event.src_path)
            if found is None:
                return

            self._notify(
                "FILMIUM torrenti",
                f'Nov torrent je pronađen: „{found.name}". '
                "Izaberi fajlove na stranici Torrenti.",
            )
        except Exception as error:  # noqa: BLE001 — nadzor ne sme da padne
            print(f"CORE upozorenje: FILMIUM nadzor torrenta: {error}")

    def _wait_until_stable(self, path: str) -> bool:
        """Čeka da veličina fajla bude ista u dve uzastopne provere."""

        previous = -1
        for attempt in range(self._stability_checks):
            try:
                size = os.path.getsize(path)
            except OSError:
                return False

            if size > 0 and size == previous:
                return True

            previous = size
            if attempt + 1 < self._stability_checks and self._stability_delay > 0:
                time.sleep(self._stability_delay)

        return False
