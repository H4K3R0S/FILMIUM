from dataclasses import dataclass
from datetime import datetime

from core.domains.filmium.models import MediaType

# ==========          IZMENA DATUMA BIBLIOTEKE          ==========

@dataclass(frozen=True)
class MediaLibraryDateUpdate:
    """Novi korisnicki datum ulaska sadrzaja u biblioteku."""

    media_id: int
    library_added_at: datetime


# ==========          ZAPIS DATUMA BIBLIOTEKE          ==========

@dataclass(frozen=True)
class MediaLibraryDateRecord:
    """Kratak zapis koji podrzava prikaz najnovije dodatih filmova."""

    media_id: int
    title: str
    media_type: MediaType
    release_year: int | None
    library_added_at: datetime