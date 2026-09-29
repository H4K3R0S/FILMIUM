from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING

from core.domains.filmium.library_models import (
    MediaFileRole,
    MediaOwnershipStatus,
)
from core.domains.filmium.models import MediaType

if TYPE_CHECKING:
    from core.domains.filmium.tmdb_client import MediaTitleEnrichment


# ==========          STATUS PODUDARANJA          ==========

class ImportMatchStatus(StrEnum):
    """Opisuje odnos kandidata prema postojecem FILMIUM katalogu."""

    NEW = "new"
    EXISTING = "existing"
    AMBIGUOUS = "ambiguous"


# ==========          DATOTEKA U PREVIEW-U          ==========

@dataclass(frozen=True)
class ImportPreviewFile:
    """Jedna datoteka prikazana pre potvrde uvoza."""

    relative_path: str
    role: MediaFileRole
    size_bytes: int
    language: str | None = None


# ==========          TEHNIČKE INFORMACIJE          ==========

@dataclass(frozen=True)
class MediaTechnicalInfo:
    """Tehnički podaci glavnog videa dobijeni media-probe alatom."""

    width: int | None = None
    height: int | None = None
    video_codec: str | None = None
    frame_rate: float | None = None
    audio_codec: str | None = None
    audio_channels: int | None = None
    duration_seconds: float | None = None
    bit_rate: int | None = None
    is_hdr: bool = False
    audio_language: str | None = None


# ==========          PLANIRANA AKCIJA          ==========

@dataclass(frozen=True)
class ImportPreviewAction:
    """Jedna filesystem akcija koja jos nije izvrsena."""

    action_type: str
    destination: str
    reason: str
    source: str | None = None


# ==========          PREGLED UVOZA          ==========

@dataclass(frozen=True)
class MediaImportPreview:
    """Kompletan nedestruktivni pregled jednog kandidata za uvoz."""

    library_root_id: int
    relative_directory: str
    title: str
    original_title: str | None
    media_type: MediaType
    release_year: int | None
    runtime_minutes: int | None
    description: str | None
    genres: tuple[str, ...]
    unrecognized_genres: tuple[str, ...]
    studio: str | None
    franchise: str | None
    franchise_order: int | None
    ownership_status: MediaOwnershipStatus
    match_status: ImportMatchStatus
    matching_media_ids: tuple[int, ...]
    planned_target_directory: str
    detected_files: tuple[ImportPreviewFile, ...] = ()
    actions: tuple[ImportPreviewAction, ...] = ()
    warnings: tuple[str, ...] = ()
    blocking_warnings: tuple[str, ...] = ()
    technical: MediaTechnicalInfo | None = None
    suggested_genres: tuple[str, ...] = ()
    # Puna TMDB dopuna (svi glumci, keywords, kolekcija, EN+SR opis…).
    # Popunjava se samo kada je zatražena (include_tmdb), inače None.
    tmdb: MediaTitleEnrichment | None = None

    @property
    def can_confirm(self) -> bool:
        """Vraca True kada preview nema problem koji zahteva ispravku."""

        return (
            not self.blocking_warnings
            and not self.unrecognized_genres
            and self.match_status is not ImportMatchStatus.AMBIGUOUS
        )

    @property
    def requires_organization(self) -> bool:
        """Vraca True kada potvrda zahteva bar jednu filesystem izmenu."""

        return bool(self.actions)