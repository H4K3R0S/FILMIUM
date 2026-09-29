from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

# ==========          STATUS REDA          ==========

class SubtitleRepairQueueStatus(StrEnum):
    """Zivotni ciklus problematcnog prevoda."""

    PENDING = "pending"
    REVIEWED = "reviewed"
    REPAIRED = "repaired"
    DISMISSED = "dismissed"
    IGNORED = "ignored"


# ==========          NOVA STAVKA REDA          ==========

@dataclass(frozen=True)
class SubtitleRepairQueueCreate:
    """Podaci dobijeni automatskom analizom prevoda."""

    file_path: str
    file_name: str
    source_sha256: str
    detected_encoding: str
    detected_language_code: str | None
    language_confidence: float
    issue_count: int
    media_id: int | None = None
    source_id: int | None = None


# ==========          STAVKA REDA          ==========

@dataclass(frozen=True)
class SubtitleRepairQueueItem:
    """Trajna stavka odeljka Popravi prevod."""

    id: int
    media_id: int | None
    source_id: int | None
    file_path: str
    file_name: str
    source_sha256: str
    detected_encoding: str
    detected_language_code: str | None
    language_confidence: float
    issue_count: int
    status: SubtitleRepairQueueStatus
    discovered_at: datetime
    updated_at: datetime
    reviewed_at: datetime | None
    resolved_at: datetime | None
