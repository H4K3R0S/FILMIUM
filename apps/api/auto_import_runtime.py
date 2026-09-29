# ========== AUTO-IMPORT RUNTIME (deljeni servisi za API + startup) ==========
# Drži deljenu instancu AutoImportService (FILMIUM) sa CORE file_monitor-om i
# sopstvenim import_guard-om kao adapterom. Start/stop iz app lifespan-a.
from __future__ import annotations

from core.domains.filmium.auto_import import (
    AutoImportRepository,
    AutoImportService,
)
from core.domains.filmium.auto_import.auto_import_models import (
    SecurityStatus as FilmiumSecurityStatus,
)
from core.domains.filmium.import_guard import ImportGuard
from core.system.file_monitor import FileMonitorService

# ---------- deljene instance ----------
_repo = AutoImportRepository()
_monitor = FileMonitorService()
_guard = ImportGuard()


def _security_status(file_path: str) -> FilmiumSecurityStatus:
    """Adapter: import_guard SecurityStatus -> FILMIUM SecurityStatus (iste vrednosti)."""
    return FilmiumSecurityStatus(_guard.status_for(file_path).value)


_service = AutoImportService(
    _repo,
    file_monitor=_monitor,
    security_scanner=_security_status,
)


def get_service() -> AutoImportService:
    return _service


# ========== RUNTIME (start/stop iz lifespan-a) ==========
class AutoImportRuntime:
    """Pali praćenje za perzistirane foldere na startu; gasi ih na stop."""

    def __init__(self, service: AutoImportService, monitor: FileMonitorService) -> None:
        self.service = service
        self.monitor = monitor

    def start(self) -> int:
        return self.service.resume_persisted()

    def stop(self) -> None:
        for folder in list(self.monitor.get_monitored_folders()):
            self.monitor.stop_monitoring(folder.path)


def build_auto_import_runtime(
    *,
    service: AutoImportService | None = None,
    monitor: FileMonitorService | None = None,
) -> AutoImportRuntime:
    return AutoImportRuntime(service or _service, monitor or _monitor)
