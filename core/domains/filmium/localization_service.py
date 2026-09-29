import re
import sqlite3

from core.domains.filmium.localization_models import (
    MediaLocalizationCreate,
    MediaLocalizationSettings,
    MediaLocalizationSettingsUpdate,
    MediaLocalizationType,
    MediaOriginScope,
)
from core.domains.filmium.localization_repository import (
    LocalizationRepository,
)

# ==========          GRESKE LOKALIZACIJE          ==========

class MediaLocalizationNotFoundError(LookupError):
    """Oznacava da trazeni FILMIUM sadrzaj ne postoji."""


class MediaLocalizationValidationError(ValueError):
    """Oznacava neispravna jezicka podesavanja."""


class MediaLocalizationSourceError(ValueError):
    """Oznacava izvor koji ne pripada trazenom filmu."""


class MediaLocalizationConflictError(ValueError):
    """Oznacava dupliranu lokalizaciju."""


# ==========          LOCALIZATION SERVICE          ==========

class LocalizationService:
    """Validira poreklo, jezike, titlove i sinhronizacije."""

    _LANGUAGE_PATTERN = re.compile(
        r"^[A-Za-z]{2,3}"
        r"(?:-[A-Za-z]{4})?"
        r"(?:-(?:[A-Za-z]{2}|[0-9]{3}))?$"
    )

    def __init__(self, repository: LocalizationRepository) -> None:
        self._repository = repository

    def get_settings(
        self,
        media_id: int,
    ) -> MediaLocalizationSettings:
        """Vraca lokalizacije ili prijavljuje da film ne postoji."""

        settings = self._repository.get_settings(media_id)

        if settings is None:
            raise MediaLocalizationNotFoundError(
                f"FILMIUM sadrzaj sa ID-em {media_id} ne postoji."
            )

        return settings

    def replace_settings(
        self,
        item: MediaLocalizationSettingsUpdate,
    ) -> MediaLocalizationSettings:
        """Normalizuje i atomski menja sva jezicka podesavanja."""

        normalized = self._normalize_settings(item)

        for localization in normalized.localizations:
            if (
                localization.source_id is not None
                and not self._repository.source_belongs_to_media(
                    localization.source_id,
                    normalized.media_id,
                )
            ):
                raise MediaLocalizationSourceError(
                    "Izabrani fizicki izvor ne pripada ovom sadrzaju."
                )

        try:
            updated = self._repository.replace_settings(normalized)
        except sqlite3.IntegrityError as error:
            raise MediaLocalizationConflictError(
                "Ista lokalizacija je navedena vise puta."
            ) from error

        if updated is None:
            raise MediaLocalizationNotFoundError(
                f"FILMIUM sadrzaj sa ID-em {item.media_id} ne postoji."
            )

        return updated

    @classmethod
    def _normalize_settings(
        cls,
        item: MediaLocalizationSettingsUpdate,
    ) -> MediaLocalizationSettingsUpdate:
        original_language = cls._optional_language_code(
            item.original_language_code
        )
        normalized_localizations = tuple(
            cls._normalize_localization(
                localization,
                item.media_id,
            )
            for localization in item.localizations
        )
        identities: set[
            tuple[int | None, MediaLocalizationType, str, str]
        ] = set()

        for localization in normalized_localizations:
            identity = (
                localization.source_id,
                localization.localization_type,
                localization.language_code.casefold(),
                (localization.label or "").casefold(),
            )

            if identity in identities:
                raise MediaLocalizationConflictError(
                    "Ista lokalizacija je navedena vise puta."
                )

            identities.add(identity)

        return MediaLocalizationSettingsUpdate(
            media_id=item.media_id,
            origin_scope=MediaOriginScope(item.origin_scope),
            original_language_code=original_language,
            localizations=normalized_localizations,
        )

    @classmethod
    def _normalize_localization(
        cls,
        item: MediaLocalizationCreate,
        media_id: int,
    ) -> MediaLocalizationCreate:
        return MediaLocalizationCreate(
            media_id=media_id,
            source_id=item.source_id,
            localization_type=MediaLocalizationType(
                item.localization_type
            ),
            language_code=cls._language_code(item.language_code),
            label=cls._optional_text(item.label),
            is_primary=bool(item.is_primary),
        )

    @classmethod
    def _optional_language_code(
        cls,
        value: str | None,
    ) -> str | None:
        if value is None or not value.strip():
            return None

        return cls._language_code(value)

    @classmethod
    def _language_code(cls, value: str) -> str:
        stripped = value.strip()

        if not cls._LANGUAGE_PATTERN.fullmatch(stripped):
            raise MediaLocalizationValidationError(
                f"Neispravan jezicki kod: {value!r}."
            )

        parts = stripped.split("-")
        normalized = [parts[0].lower()]

        for part in parts[1:]:
            if len(part) == 4 and part.isalpha():
                normalized.append(part.title())
            elif len(part) == 2 and part.isalpha():
                normalized.append(part.upper())
            else:
                normalized.append(part)

        return "-".join(normalized)

    @staticmethod
    def _optional_text(value: str | None) -> str | None:
        if value is None:
            return None

        normalized = value.strip()

        if len(normalized) > 100:
            raise MediaLocalizationValidationError(
                "Oznaka lokalizacije ne sme biti duza od 100 znakova."
            )

        return normalized or None