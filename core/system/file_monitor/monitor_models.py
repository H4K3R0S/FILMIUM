# ========== MODELI FILE MONITOR-a ==========
# Jednostavni, framework-nezavisni modeli za događaje praćenja.
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


# ========== DOGAĐAJI FAJLOVA ==========
class FileEventType(str, Enum):
    CREATED = "created"
    MODIFIED = "modified"
    DELETED = "deleted"
    MOVED = "moved"


@dataclass(frozen=True)
class FileEvent:
    # Događaj nad jednim fajlom/folderom unutar praćene putanje.
    event_type: FileEventType
    src_path: str
    is_directory: bool = False
    dest_path: str | None = None  # samo za MOVED
    at: datetime = field(default_factory=datetime.now)


@dataclass
class MonitoredFolder:
    # Aktivno praćena putanja (runtime stanje mehanizma).
    path: str
    recursive: bool = True
    active: bool = True
    started_at: datetime = field(default_factory=datetime.now)


# ========== DOGAĐAJI DISKOVA ==========
class DiskEventType(str, Enum):
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"


@dataclass(frozen=True)
class DiskInfo:
    # Snimak jednog priključenog diska/particije.
    device: str            # npr. "E:\\" ili "/media/usb"
    mountpoint: str
    label: str | None = None
    total_bytes: int | None = None
    free_bytes: int | None = None
    removable: bool = False


@dataclass(frozen=True)
class DiskEvent:
    event_type: DiskEventType
    disk: DiskInfo
    at: datetime = field(default_factory=datetime.now)
