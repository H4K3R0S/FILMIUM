from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

# ==========          REZIM PRENOSA          ==========

class ShareTransferMode(StrEnum):
    """Odredjuje koji deo filmskog direktorijuma se kopira."""

    PLAYBACK = "playback"
    COMPLETE = "complete"


# ==========          STATUS REDA ZA DELJENJE          ==========

class ShareQueueStatus(StrEnum):
    """Opisuje trenutno stanje jedne stavke za deljenje."""

    PENDING = "pending"
    TRANSFERRING = "transferring"
    COMPLETED = "completed"
    UNAVAILABLE = "unavailable"
    INSUFFICIENT_SPACE = "insufficient_space"
    FAILED = "failed"


# ==========          NOVI PROFIL ZA DELJENJE          ==========

@dataclass(frozen=True)
class ShareProfileCreate:
    """Podaci potrebni za pravljenje profila u funkciji Podeli."""

    name: str
    description: str | None = None
    default_destination_folder: str = "VIDEOS"
    is_active: bool = True


# ==========          PROFIL ZA DELJENJE          ==========

@dataclass(frozen=True)
class ShareProfile:
    """Jedan imenovani primalac ili scenario deljenja."""

    id: int
    name: str
    description: str | None
    default_destination_folder: str
    is_active: bool
    created_at: datetime
    updated_at: datetime


# ==========          NOVA STAVKA ZA DELJENJE          ==========

@dataclass(frozen=True)
class ShareQueueItemCreate:
    """Film i rezim kopiranja koji se dodaju izabranom profilu."""

    profile_id: int
    media_id: int
    transfer_mode: ShareTransferMode = ShareTransferMode.PLAYBACK


# ==========          STAVKA REDA ZA DELJENJE          ==========

@dataclass(frozen=True)
class ShareQueueItem:
    """Sacuvana stavka reda koja ce biti kopirana na odredisni medij."""

    id: int
    profile_id: int
    media_id: int
    transfer_mode: ShareTransferMode
    status: ShareQueueStatus
    error_message: str | None
    added_at: datetime
    updated_at: datetime
    completed_at: datetime | None