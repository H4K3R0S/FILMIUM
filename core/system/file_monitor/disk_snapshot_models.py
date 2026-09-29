# ========== MODELI DISK SNAPSHOT-a / FANTOMA ==========
# Framework-nezavisne dataclasses za skeniranje diska, sektore i diff.
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class SectorKind(str, Enum):
    BOOT = "boot"
    SOFTWARE = "software"
    SHARING = "sharing"
    PRINT = "print"
    VIDEO = "video"
    FILMOTEKA = "filmoteka"
    OTHER = "other"


@dataclass(frozen=True)
class FileEntry:
    relpath: str          # relativno na mount, POSIX separatori
    size: int
    mtime: float          # epoch sekunde
    is_dir: bool


@dataclass(frozen=True)
class DiskSnapshot:
    mount: str
    taken_at: datetime
    entries: tuple[FileEntry, ...]


@dataclass(frozen=True)
class ScanDiff:
    added: tuple[FileEntry, ...]
    removed: tuple[FileEntry, ...]
    changed: tuple[FileEntry, ...]

    @property
    def is_empty(self) -> bool:
        return not (self.added or self.removed or self.changed)


@dataclass(frozen=True)
class Sector:
    name: str
    kind: SectorKind
    root_relpath: str
    entry_count: int
    detail: dict = field(default_factory=dict)


@dataclass(frozen=True)
class RelatedPartition:
    # Sestrinska particija istog fizičkog diska (npr. E:\ pored G:\).
    mount: str
    size_bytes: int | None = None


@dataclass(frozen=True)
class DiskIdentity:
    disk_id: str
    signed_id: str
    created_at: datetime
    last_scan_at: datetime
    owner: str = "CORE"
    disk_type: str = ""
    purpose: str = ""
    general_use: str = ""
    serial: str = ""
    # --- fizički uređaj (jedan USB može imati više particija) ---
    physical_disk_number: int | None = None
    physical_model: str = ""
    physical_serial: str = ""
    bus_type: str = ""
    related_partitions: tuple[RelatedPartition, ...] = ()
    phantom_location: str = ""   # gde je fantom stvarno upisan


@dataclass(frozen=True)
class ScanReport:
    identity: DiskIdentity
    sectors: tuple[Sector, ...]
    diff: ScanDiff
    is_first_scan: bool
    phantom_written: bool = True   # False kad je medij write-protected i sl.


@dataclass(frozen=True)
class PhantomPeek:
    # Lagani uvid u fantom bez dubokog skena: šta CORE već zna o disku.
    is_known: bool
    identity: DiskIdentity | None
    sectors: tuple[Sector, ...]
