# ========== FILE MONITOR (System Layer) ==========
# Mehanizam za praćenje foldera (watchdog) i priključenih diskova (psutil).
# CORE je vlasnik mehanizma; domeni (npr. FILMIUM) ga KORISTE i čuvaju svoju
# konfiguraciju kod sebe. Ovaj sloj NE drži domensku bazu.
from core.system.file_monitor.auto_scan_coordinator import AutoScanCoordinator
from core.system.file_monitor.disk_monitor import DiskMonitorService
from core.system.file_monitor.disk_scan_service import DiskScanService
from core.system.file_monitor.disk_snapshot_models import (
    DiskIdentity,
    DiskSnapshot,
    FileEntry,
    PhantomPeek,
    ScanDiff,
    ScanReport,
    Sector,
    SectorKind,
)
from core.system.file_monitor.monitor_models import (
    DiskEvent,
    DiskEventType,
    DiskInfo,
    FileEvent,
    FileEventType,
    MonitoredFolder,
)
from core.system.file_monitor.monitor_service import FileMonitorService
from core.system.file_monitor.scan_notification import (
    CallbackNotifier,
    NullNotifier,
    OsToastNotifier,
    format_peek,
    format_report,
)

__all__ = [
    "AutoScanCoordinator",
    "CallbackNotifier",
    "DiskEvent",
    "DiskEventType",
    "DiskIdentity",
    "DiskInfo",
    "DiskMonitorService",
    "DiskScanService",
    "DiskSnapshot",
    "FileEntry",
    "FileEvent",
    "FileEventType",
    "FileMonitorService",
    "MonitoredFolder",
    "NullNotifier",
    "OsToastNotifier",
    "PhantomPeek",
    "ScanDiff",
    "ScanReport",
    "Sector",
    "SectorKind",
    "format_peek",
    "format_report",
]
