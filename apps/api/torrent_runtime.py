# ========== TORRENT RUNTIME (deljeni servis za API + startup) ==========
# Drži deljenu instancu TorrentService-a sa qBittorrent engine-om, CORE
# file_monitor-om za nadzor foldera, pozadinskom anketom i OS toast
# notifikacijama.
from __future__ import annotations

from core.domains.filmium.torrents.torrent_engine import QbittorrentEngine
from core.domains.filmium.torrents.torrent_models import (
    TorrentEntry,
    TorrentSettings,
)
from core.domains.filmium.torrents.torrent_poller import TorrentPoller
from core.domains.filmium.torrents.torrent_repository import TorrentRepository
from core.domains.filmium.torrents.torrent_service import TorrentService
from core.domains.filmium.torrents.torrent_settings import TorrentSettingsStore
from core.domains.filmium.torrents.torrent_watch_service import TorrentWatchService
from core.system.file_monitor import FileMonitorService, OsToastNotifier

# ---------- deljene instance ----------
_repository = TorrentRepository()
_settings_store = TorrentSettingsStore()
_engine = QbittorrentEngine(_settings_store.load)
_monitor = FileMonitorService()
_notifier = OsToastNotifier()


def _on_completed(entry: TorrentEntry) -> None:
    """Javlja korisniku da je sadržaj spreman i gde je.

    Uvoz se NE pokreće sam: korisnik ga startuje sa ekrana uvoza
    (`/filmium/uploads`), do kojeg vodi radnja u tabu „Završeni".
    Automatska predaja redu uvoza je svesno van obima (spec, odeljak 8).
    """

    _notifier.notify(
        "FILMIUM torrenti",
        f'„{entry.name}" je spreman za uvoz. Putanja: {entry.save_path}',
    )


def _on_settings_saved(_settings: TorrentSettings) -> None:
    """Upis podešavanja ponovo pali nadzor nad (možda novim) folderima."""

    _watch.restart()


_service = TorrentService(
    _repository,
    _engine,
    _settings_store,
    on_completed=_on_completed,
    notify=_notifier.notify,
    on_settings_saved=_on_settings_saved,
)

_watch = TorrentWatchService(_service, _monitor, notify=_notifier.notify)
_poller = TorrentPoller(_service)


def get_service() -> TorrentService:
    return _service


# ========== RUNTIME (start/stop iz lifespan-a) ==========
class TorrentRuntime:
    """Usklađuje bazu, pali nadzor foldera i pozadinsku anketu."""

    def __init__(
        self,
        service: TorrentService,
        watch: TorrentWatchService,
        poller: TorrentPoller,
    ) -> None:
        self.service = service
        self.watch = watch
        self.poller = poller

    def start(self) -> bool:
        # Restart CORE-a: qBittorrent je nastavio sam, pa se baza usklađuje
        # sa onim što klijent prijavljuje za kategoriju FILMIUM.
        self.service.reconcile()

        # Anketa je jedini vlasnik prelaza stanja i notifikacija; pali se
        # i kada nadzirani folder nije podešen.
        self.poller.start()
        return self.watch.start()

    def stop(self) -> None:
        self.poller.stop()
        self.watch.stop()


def build_torrent_runtime(
    *,
    service: TorrentService | None = None,
    watch: TorrentWatchService | None = None,
    poller: TorrentPoller | None = None,
) -> TorrentRuntime:
    return TorrentRuntime(
        service or _service,
        watch or _watch,
        poller or _poller,
    )
