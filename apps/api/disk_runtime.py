# ========== DISK RUNTIME (deljeni servisi za API + startup) ==========
# Drži deljene instance DiskScanService/DiskMonitorService i wiring koordinatora.
from __future__ import annotations

import time

from core.system.file_monitor import (
    AutoScanCoordinator,
    DiskMonitorService,
    DiskScanService,
    OsToastNotifier,
    physical_disk,
)
from core.system.file_monitor.monitor_models import DiskInfo
from core.system.file_monitor.physical_disk import PhysicalDisk

_scan_service = DiskScanService()
_monitor = DiskMonitorService()

# Keš fizičke topologije (PowerShell upit je skup, lista se poll-uje često).
_PHYS_TTL = 15.0
_phys_cache: dict[str, PhysicalDisk] = {}
_phys_at: float = 0.0


def get_scan_service() -> DiskScanService:
    return _scan_service


def get_monitor() -> DiskMonitorService:
    return _monitor


def list_disks() -> list[DiskInfo]:
    return _monitor.list_disks()


def physical_map(*, now: float | None = None) -> dict[str, PhysicalDisk]:
    """Keširana mapa mount -> fizički disk (TTL ~15s)."""
    global _phys_cache, _phys_at
    t = now if now is not None else time.monotonic()
    if not _phys_cache or (t - _phys_at) > _PHYS_TTL:
        try:
            _phys_cache = physical_disk.physical_map()
        except Exception:  # noqa: BLE001
            _phys_cache = {}
        _phys_at = t
    return _phys_cache


class DiskRuntime:
    """Objedinjuje monitor + koordinator; start/stop iz app lifespan-a."""

    def __init__(self, monitor: DiskMonitorService, coordinator: AutoScanCoordinator) -> None:
        self.monitor = monitor
        self.coordinator = coordinator

    def start(self) -> None:
        self.coordinator.start()
        self.monitor.start()

    def stop(self) -> None:
        self.monitor.stop()


def build_disk_runtime(
    *,
    monitor: DiskMonitorService | None = None,
    scan_service: DiskScanService | None = None,
    notifier=None,
) -> DiskRuntime:
    """Napravi DiskRuntime (peek-on-connect + OS-toast). Ne pokreće petlju."""
    mon = monitor or _monitor
    scan = scan_service or _scan_service
    coordinator = AutoScanCoordinator(mon, scan, notifier=notifier or OsToastNotifier())
    return DiskRuntime(mon, coordinator)
