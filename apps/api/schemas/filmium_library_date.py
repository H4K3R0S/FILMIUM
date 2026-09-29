from datetime import datetime

from pydantic import BaseModel

from core.domains.filmium.library_date_models import (
    MediaLibraryDateRecord,
    MediaLibraryDateUpdate,
)
from core.domains.filmium.models import MediaType

# ==========          ZAHTEV DATUMA BIBLIOTEKE          ==========

class MediaLibraryDateRequest(BaseModel):
    """Datum koji korisnik zeli da postavi za jedan sadrzaj."""

    library_added_at: datetime

    def to_domain(
        self,
        media_id: int,
    ) -> MediaLibraryDateUpdate:
        return MediaLibraryDateUpdate(
            media_id=media_id,
            library_added_at=self.library_added_at,
        )


# ==========          ODGOVOR DATUMA BIBLIOTEKE          ==========

class MediaLibraryDateResponse(BaseModel):
    """API prikaz datuma ulaska jednog sadrzaja u biblioteku."""

    media_id: int
    title: str
    media_type: MediaType
    release_year: int | None
    library_added_at: datetime

    @classmethod
    def from_domain(
        cls,
        item: MediaLibraryDateRecord,
    ) -> "MediaLibraryDateResponse":
        return cls(
            media_id=item.media_id,
            title=item.title,
            media_type=item.media_type,
            release_year=item.release_year,
            library_added_at=item.library_added_at,
        )