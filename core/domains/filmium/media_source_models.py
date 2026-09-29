from dataclasses import dataclass
from datetime import datetime

from core.domains.filmium.library_models import (
    MediaFileRole,
    MediaFileStatus,
)

# ==========          NOVA DATOTEKA IZVORA          ==========

@dataclass(frozen=True)
class MediaFileCreate:
    """Podaci jedne datoteke koja pripada fizickom izvoru."""

    role: MediaFileRole
    relative_path: str
    language: str | None = None
    size_bytes: int = 0
    modified_at: datetime | None = None
    file_status: MediaFileStatus = MediaFileStatus.AVAILABLE


# ==========          SACUVANA DATOTEKA IZVORA          ==========

@dataclass(frozen=True)
class MediaFile:
    """Indeksirana datoteka jednog fizickog FILMIUM izvora."""

    id: int
    source_id: int
    role: MediaFileRole
    relative_path: str
    language: str | None
    size_bytes: int
    modified_at: datetime | None
    file_status: MediaFileStatus
    created_at: datetime
    updated_at: datetime


# ==========          NOVI FIZICKI IZVOR          ==========

@dataclass(frozen=True)
class MediaSourceCreate:
    """Podaci potrebni za povezivanje kataloga sa lokalnim folderom."""

    media_id: int
    library_root_id: int
    root_path_snapshot: str
    relative_directory: str
    manifest_path: str = "filmium_info.json"
    availability_status: MediaFileStatus = MediaFileStatus.AVAILABLE
    files: tuple[MediaFileCreate, ...] = ()


# ==========          FIZICKI IZVOR SADRZAJA          ==========

@dataclass(frozen=True)
class MediaSource:
    """Veza FILMIUM sadrzaja sa jednim fizickim direktorijumom."""

    id: int
    media_id: int
    library_root_id: int | None
    root_path_snapshot: str
    relative_directory: str
    manifest_path: str
    availability_status: MediaFileStatus
    last_verified_at: datetime | None
    created_at: datetime
    updated_at: datetime
    files: tuple[MediaFile, ...] = ()