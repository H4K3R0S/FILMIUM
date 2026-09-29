from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

# ==========          TIP VIZUELNOG MATERIJALA          ==========

class ArtworkType(StrEnum):
    """Podrzani tipovi FILMIUM vizuelnog materijala."""

    POSTER = "poster"
    BACKDROP = "backdrop"
    WALLPAPER = "wallpaper"
    FANART = "fanart"
    LOGO = "logo"
    EPISODE_STILL = "episode_still"


# ==========          MESTO CUVANJA          ==========

class ArtworkStorageKind(StrEnum):
    """Odredjuje da li je slika uz izvor ili u CORE skladistu."""

    SOURCE = "source"
    MANAGED = "managed"


# ==========          NOVI VIZUELNI MATERIJAL          ==========

@dataclass(frozen=True)
class MediaArtworkCreate:
    """Podaci potrebni za upis jedne FILMIUM slike."""

    media_id: int
    artwork_type: ArtworkType
    storage_kind: ArtworkStorageKind
    relative_path: str
    source_id: int | None = None
    label: str | None = None
    width_pixels: int | None = None
    height_pixels: int | None = None
    file_size_bytes: int = 0
    is_primary: bool = False
    sort_order: int = 0


# ==========          VIZUELNI MATERIJAL          ==========

@dataclass(frozen=True)
class MediaArtwork:
    """Jedna indeksirana slika povezana sa FILMIUM sadrzajem."""

    id: int
    media_id: int
    source_id: int | None
    artwork_type: ArtworkType
    storage_kind: ArtworkStorageKind
    relative_path: str
    label: str | None
    width_pixels: int | None
    height_pixels: int | None
    file_size_bytes: int
    is_primary: bool
    sort_order: int
    created_at: datetime
    updated_at: datetime