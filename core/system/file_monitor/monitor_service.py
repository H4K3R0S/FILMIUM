# ========== FILE MONITOR SERVICE ==========
# Tanak wrapper oko watchdog-a. watchdog se uvozi LENJO (opciona zavisnost),
# a fabrika observera je injektabilna radi testiranja bez instalacije/mreže.
from __future__ import annotations

import os
from collections.abc import Callable
from typing import Any

from core.system.file_monitor.monitor_models import (
    FileEvent,
    FileEventType,
    MonitoredFolder,
)

Callback = Callable[[FileEvent], None]


# ========== SERVIS ==========
class FileMonitorService:
    """Prati foldere i emituje FileEvent ka registrovanim callback-ovima.

    Dizajn: mehanizam, bez baze. Konfiguraciju/persistenciju drži domen koji
    ovo koristi (npr. FILMIUM auto_import).
    """

    def __init__(self, observer_factory: Callable[[], Any] | None = None) -> None:
        # observer_factory() -> objekat sa schedule(handler, path, recursive), start(), stop(), join()
        self._observer_factory = observer_factory
        self._callbacks: dict[FileEventType, list[Callback]] = {
            t: [] for t in FileEventType
        }
        self._folders: dict[str, MonitoredFolder] = {}
        self._observers: dict[str, Any] = {}

    # ---------- registracija callback-ova ----------
    def register_callback(self, event_type: FileEventType | str, callback: Callback) -> None:
        et = FileEventType(event_type) if not isinstance(event_type, FileEventType) else event_type
        self._callbacks[et].append(callback)

    # ---------- praćenje ----------
    def start_monitoring(self, folder_path: str, recursive: bool = True) -> MonitoredFolder:
        path = os.path.abspath(folder_path)
        if path in self._folders and self._folders[path].active:
            return self._folders[path]

        folder = MonitoredFolder(path=path, recursive=recursive, active=False)
        observer = self._build_observer()
        if observer is not None:
            handler = self._build_handler()
            observer.schedule(handler, path, recursive=recursive)
            observer.start()
            self._observers[path] = observer
            folder.active = True
        # Ako watchdog nije dostupan, folder se pamti kao neaktivan (degradacija bez pada).
        self._folders[path] = folder
        return folder

    def stop_monitoring(self, folder_path: str) -> None:
        path = os.path.abspath(folder_path)
        observer = self._observers.pop(path, None)
        if observer is not None:
            observer.stop()
            observer.join(timeout=2)
        if path in self._folders:
            self._folders[path].active = False
            del self._folders[path]

    def get_monitored_folders(self) -> list[MonitoredFolder]:
        return list(self._folders.values())

    @staticmethod
    def is_disk_connected(drive_or_path: str) -> bool:
        # Prisutnost diska/putanje (za USB). Portabilno.
        return os.path.exists(drive_or_path)

    # ---------- interna dispečer logika (testabilno) ----------
    def _emit(self, event_type: FileEventType | str, src_path: str,
              is_directory: bool = False, dest_path: str | None = None) -> None:
        et = FileEventType(event_type) if not isinstance(event_type, FileEventType) else event_type
        event = FileEvent(event_type=et, src_path=src_path,
                          is_directory=is_directory, dest_path=dest_path)
        for cb in self._callbacks.get(et, []):
            cb(event)

    # ---------- watchdog integracija (lenjo) ----------
    def _build_observer(self):
        if self._observer_factory is not None:
            return self._observer_factory()
        try:
            from watchdog.observers import Observer  # lenjo, opciona zavisnost
        except ImportError:
            return None
        return Observer()

    def _build_handler(self):
        # Vrati watchdog handler koji prevodi događaje u _emit.
        try:
            from watchdog.events import FileSystemEventHandler
        except ImportError:
            return None

        service = self

        class _Handler(FileSystemEventHandler):
            def on_created(self, event):
                service._emit(FileEventType.CREATED, event.src_path, event.is_directory)

            def on_modified(self, event):
                service._emit(FileEventType.MODIFIED, event.src_path, event.is_directory)

            def on_deleted(self, event):
                service._emit(FileEventType.DELETED, event.src_path, event.is_directory)

            def on_moved(self, event):
                service._emit(FileEventType.MOVED, event.src_path, event.is_directory,
                              getattr(event, "dest_path", None))

        return _Handler()
