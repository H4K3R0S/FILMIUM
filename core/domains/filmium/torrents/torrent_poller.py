# ========== POZADINSKA ANKETA TORRENTA ==========
# Jedna daemon nit koja zove `TorrentService.poll()`. Ona je JEDINI vlasnik
# prelaza stanja i notifikacija — SSE rute samo čitaju `latest_progress()`.
#
# Bez ove niti torrent spušten u nadzirani folder dok je GUI zatvoren zauvek
# ostaje u `metadata_fetching`, a završetak preuzimanja se ne primeti.
from __future__ import annotations

import threading
from collections.abc import Callable

from core.domains.filmium.torrents.torrent_service import TorrentService

# Razmak dok ima torrenta u toku, i dok ih nema.
ACTIVE_INTERVAL_SECONDS = 1.0
IDLE_INTERVAL_SECONDS = 5.0


# ========== POLLER ==========
class TorrentPoller:
    """Daemon nit sa anketom; izuzetak nikada ne obara petlju."""

    def __init__(
        self,
        service: TorrentService,
        *,
        active_interval: float = ACTIVE_INTERVAL_SECONDS,
        idle_interval: float = IDLE_INTERVAL_SECONDS,
        on_error: Callable[[BaseException], None] | None = None,
    ) -> None:
        self._service = service
        self._active_interval = float(active_interval)
        self._idle_interval = float(idle_interval)
        self._on_error = on_error or self._report
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    @staticmethod
    def _report(error: BaseException) -> None:
        print(f"CORE upozorenje: FILMIUM torrent anketa: {error}")

    # ---------- životni ciklus ----------
    def start(self) -> bool:
        if self._thread is not None and self._thread.is_alive():
            return False

        self._stop.clear()
        self._thread = threading.Thread(
            target=self._run,
            name="filmium-torrent-poller",
            daemon=True,
        )
        self._thread.start()
        return True

    def stop(self, *, timeout: float = 5.0) -> None:
        self._stop.set()
        thread = self._thread
        if thread is not None and thread.is_alive():
            thread.join(timeout=timeout)
        self._thread = None

    @property
    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    # ---------- petlja ----------
    def _run(self) -> None:
        # `Event.wait` je izlaz iz petlje: nema `while True` bez prekida.
        while not self._stop.is_set():
            self._stop.wait(self.run_once())

    def run_once(self) -> float:
        """Jedan krug ankete; vraća koliko se spava do sledećeg.

        Odvojeno od niti da testovi mogu da ga pozovu bez paljenja niti.
        """

        try:
            self._service.poll()
        except Exception as error:  # noqa: BLE001 — nit mora da preživi sve
            self._on_error(error)
            return self._idle_interval

        try:
            active = self._service.has_active()
        except Exception as error:  # noqa: BLE001
            self._on_error(error)
            return self._idle_interval

        return self._active_interval if active else self._idle_interval
