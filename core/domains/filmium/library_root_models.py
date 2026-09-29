from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

# ==========          STATUS POSLEDNJEG SKENIRANJA          ==========

class LibraryRootScanStatus(StrEnum):
    """Status poslednjeg pokusaja skeniranja biblioteke."""

    NEVER_SCANNED = "never_scanned"
    AVAILABLE = "available"
    OFFLINE = "offline"
    DISABLED = "disabled"


# ==========          NOVA BIBLIOTEKA          ==========

@dataclass(frozen=True)
class LibraryRootCreate:
    """Podaci potrebni za registraciju jedne FILMIUM biblioteke."""

    name: str
    path: str
    volume_id: str | None = None
    volume_label: str | None = None
    is_enabled: bool = True
    is_persistent: bool = True


# ==========          REGISTROVANA BIBLIOTEKA          ==========

@dataclass(frozen=True)
class LibraryRoot:
    """Trajno sacuvana lokacija lokalne FILMIUM biblioteke."""

    id: int
    name: str
    path: str
    volume_id: str | None
    volume_label: str | None
    is_enabled: bool
    is_persistent: bool
    is_main: bool
    last_scan_status: LibraryRootScanStatus
    last_scanned_at: datetime | None
    last_seen_at: datetime | None
    created_at: datetime
    updated_at: datetime
