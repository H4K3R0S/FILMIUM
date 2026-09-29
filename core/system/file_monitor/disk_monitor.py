# ========== DISK MONITOR SERVICE ==========
# Detekcija priključivanja/isključivanja diskova (USB). psutil se uvozi LENJO;
# enumerator diskova je injektabilan radi testiranja. Osnova je poll() koji
# poredi trenutni snimak sa prethodnim i emituje DiskEvent.
from __future__ import annotations

import os
import shutil
import threading
from collections.abc import Callable

from core.system.file_monitor.monitor_models import (
    DiskEvent,
    DiskEventType,
    DiskInfo,
)

DiskCallback = Callable[[DiskEvent], None]


# ========== SERVIS ==========
class DiskMonitorService:
    """Prati priključene diskove; emituje CONNECTED/DISCONNECTED događaje."""

    def __init__(self, list_disks: Callable[[], list[DiskInfo]] | None = None,
                 interval_seconds: float = 2.0) -> None:
        self._list_disks = list_disks or self._default_list_disks
        self._interval = interval_seconds
        self._callbacks: list[DiskCallback] = []
        self._known: dict[str, DiskInfo] = {}
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        self._seeded = False

    def register_callback(self, callback: DiskCallback) -> None:
        self._callbacks.append(callback)

    def is_disk_connected(self, device_or_mount: str) -> bool:
        disks = self._list_disks()
        return any(d.device == device_or_mount or d.mountpoint == device_or_mount
                   for d in disks)

    def list_disks(self) -> list[DiskInfo]:
        return self._list_disks()

    # ---------- jezgro: poll + diff ----------
    def poll(self) -> list[DiskEvent]:
        # Prvi poziv samo "seed"-uje poznato stanje (bez lažnih CONNECTED).
        current = {d.device: d for d in self._list_disks()}
        if not self._seeded:
            self._known = current
            self._seeded = True
            return []

        events: list[DiskEvent] = []
        for dev, info in current.items():
            if dev not in self._known:
                events.append(DiskEvent(DiskEventType.CONNECTED, info))
        for dev, info in self._known.items():
            if dev not in current:
                events.append(DiskEvent(DiskEventType.DISCONNECTED, info))

        self._known = current
        for ev in events:
            for cb in self._callbacks:
                cb(ev)
        return events

    # ---------- pozadinska petlja (opciono) ----------
    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=2)

    def _loop(self) -> None:
        while not self._stop.is_set():
            try:
                self.poll()
            except Exception:  # noqa: BLE001, S110
                pass  # petlja ne sme da padne zbog jednog neuspelog poll-a
            self._stop.wait(self._interval)

    # ---------- podrazumevani enumerator (psutil, lenjo) ----------
    @staticmethod
    def _default_list_disks() -> list[DiskInfo]:
        try:
            import psutil  # lenjo, opciona zavisnost
        except ImportError:
            return []
        disks: list[DiskInfo] = []
        for part in psutil.disk_partitions(all=False):
            removable = "removable" in (part.opts or "") or "cdrom" in (part.opts or "")
            total = free = None
            try:
                usage = shutil.disk_usage(part.mountpoint)
                total, free = usage.total, usage.free
            except OSError:
                pass
            disks.append(DiskInfo(
                device=part.device, mountpoint=part.mountpoint,
                label=_volume_label(part.mountpoint),
                total_bytes=total, free_bytes=free, removable=removable,
            ))
        return disks


def _volume_label(mountpoint: str) -> str | None:
    """Čita naziv (Label) volumena preko Win API-ja; degradira na None."""
    if os.name != "nt":
        return None
    try:
        import ctypes

        root = mountpoint if mountpoint.endswith("\\") else mountpoint + "\\"
        name = ctypes.create_unicode_buffer(261)
        fs = ctypes.create_unicode_buffer(261)
        ok = ctypes.windll.kernel32.GetVolumeInformationW(
            ctypes.c_wchar_p(root),
            name, ctypes.sizeof(name),
            None, None, None,
            fs, ctypes.sizeof(fs),
        )
        if ok and name.value:
            return name.value
    except Exception:  # noqa: BLE001
        return None
    return None
