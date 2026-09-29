from datetime import datetime, timedelta, timezone

from core.domains.filmium.library_date_models import (
    MediaLibraryDateRecord,
    MediaLibraryDateUpdate,
)
from core.domains.filmium.library_date_repository import (
    LibraryDateRepository,
)

# ==========          GRESKE DATUMA BIBLIOTEKE          ==========

class MediaLibraryDateNotFoundError(LookupError):
    """Oznacava da trazeni FILMIUM sadrzaj ne postoji."""


class MediaLibraryDateValidationError(ValueError):
    """Oznacava datum koji ne moze predstavljati unos u biblioteku."""


# ==========          LIBRARY DATE SERVICE          ==========

class LibraryDateService:
    """Upravlja korisnickim datumom i prikazom najnovijih unosa."""

    _EARLIEST_ALLOWED = datetime(1900, 1, 1)  # noqa: DTZ001
    _FUTURE_TOLERANCE = timedelta(minutes=5)

    def __init__(self, repository: LibraryDateRepository) -> None:
        self._repository = repository

    def get_media_date(
        self,
        media_id: int,
    ) -> MediaLibraryDateRecord:
        """Vraca datum ili prijavljuje da sadrzaj ne postoji."""

        record = self._repository.get(media_id)

        if record is None:
            raise MediaLibraryDateNotFoundError(
                f"FILMIUM sadrzaj sa ID-em {media_id} ne postoji."
            )

        return record

    def update_media_date(
        self,
        item: MediaLibraryDateUpdate,
    ) -> MediaLibraryDateRecord:
        """Validira i menja datum bez menjanja tehnickog created_at."""

        normalized = self._normalize_datetime(item.library_added_at)
        now = datetime.now(timezone.utc).replace(tzinfo=None)

        if normalized < self._EARLIEST_ALLOWED:
            raise MediaLibraryDateValidationError(
                "Datum ulaska u biblioteku ne moze biti pre 1900. godine."
            )

        if normalized > now + self._FUTURE_TOLERANCE:
            raise MediaLibraryDateValidationError(
                "Datum ulaska u biblioteku ne moze biti u buducnosti."
            )

        updated = self._repository.update(
            item.media_id,
            normalized,
        )

        if updated is None:
            raise MediaLibraryDateNotFoundError(
                f"FILMIUM sadrzaj sa ID-em {item.media_id} ne postoji."
            )

        return updated

    def list_recent(
        self,
        limit: int = 50,
    ) -> tuple[MediaLibraryDateRecord, ...]:
        """Vraca ogranicenu listu najnovije dodatih sadrzaja."""

        if not 1 <= limit <= 500:
            raise MediaLibraryDateValidationError(
                "Broj rezultata mora biti izmedju 1 i 500."
            )

        return self._repository.list_recent(limit)

    @staticmethod
    def _normalize_datetime(value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(microsecond=0)

        return (
            value.astimezone(timezone.utc)
            .replace(tzinfo=None, microsecond=0)
        )