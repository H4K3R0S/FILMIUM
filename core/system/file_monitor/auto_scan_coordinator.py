# ========== AUTO-SCAN COORDINATOR ==========
# Kači se na DiskMonitorService; pri CONNECTED SAMO čita fantom (peek) i
# notifikuje. Pun scan (walk+diff+upis) je isključivo ručni poziv scan().
from __future__ import annotations

from core.system.file_monitor.monitor_models import DiskEvent, DiskEventType
from core.system.file_monitor.scan_notification import NullNotifier, format_peek


class AutoScanCoordinator:
    def __init__(self, monitor, scan_service, notifier=None) -> None:
        self._monitor = monitor
        self._scan_service = scan_service
        self._notifier = notifier or NullNotifier()

    def start(self) -> None:
        self._monitor.register_callback(self._on_disk_event)

    def _on_disk_event(self, event: DiskEvent) -> None:
        if event.event_type is not DiskEventType.CONNECTED:
            return
        mount = event.disk.mountpoint or event.disk.device
        try:
            peek = self._scan_service.peek(mount)
        except Exception:  # noqa: BLE001
            return  # degradacija bez pada
        title, message = format_peek(peek)
        try:
            self._notifier.notify(title, message)
        except Exception:  # noqa: BLE001, S110
            pass
