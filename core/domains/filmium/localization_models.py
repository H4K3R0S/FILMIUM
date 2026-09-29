from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

# ==========          POREKLO SADRZAJA          ==========

class MediaOriginScope(StrEnum):
    """Opisuje da li je sadrzaj domaci, strani ili jos neodredjen."""

    UNKNOWN = "unknown"
    DOMESTIC = "domestic"
    FOREIGN = "foreign"


# ==========          VRSTA LOKALIZACIJE          ==========

class MediaLocalizationType(StrEnum):
    """Podrzane vrste jezicke lokalizacije."""

    SUBTITLE = "subtitle"
    DUBBED_AUDIO = "dubbed_audio"


# ==========          NOVA LOKALIZACIJA          ==========

@dataclass(frozen=True)
class MediaLocalizationCreate:
    """Podaci za titl ili sinhronizovani audio jednog sadrzaja."""

    media_id: int
    localization_type: MediaLocalizationType
    language_code: str
    source_id: int | None = None
    label: str | None = None
    is_primary: bool = False


# ==========          SACUVANA LOKALIZACIJA          ==========

@dataclass(frozen=True)
class MediaLocalization:
    """Jedan registrovani titl ili sinhronizovani audio."""

    id: int
    media_id: int
    localization_type: MediaLocalizationType
    language_code: str
    source_id: int | None
    label: str | None
    is_primary: bool
    created_at: datetime
    updated_at: datetime


# ==========          PODESAVANJA LOKALIZACIJE          ==========

@dataclass(frozen=True)
class MediaLocalizationSettingsUpdate:
    """Kompletna jezicka podesavanja jednog FILMIUM sadrzaja."""

    media_id: int
    origin_scope: MediaOriginScope = MediaOriginScope.UNKNOWN
    original_language_code: str | None = None
    localizations: tuple[MediaLocalizationCreate, ...] = ()


@dataclass(frozen=True)
class MediaLocalizationSettings:
    """Sacuvano poreklo, originalni jezik i sve lokalizacije."""

    media_id: int
    origin_scope: MediaOriginScope
    original_language_code: str | None
    localizations: tuple[MediaLocalization, ...] = ()

    @property
    def subtitle_languages(self) -> tuple[str, ...]:
        """Vraca sortirane jedinstvene jezike titlova."""

        return self._languages_for(MediaLocalizationType.SUBTITLE)

    @property
    def dubbed_audio_languages(self) -> tuple[str, ...]:
        """Vraca sortirane jedinstvene jezike sinhronizacije."""

        return self._languages_for(
            MediaLocalizationType.DUBBED_AUDIO
        )

    @property
    def is_subtitled(self) -> bool:
        """Vraca True kada postoji bar jedan registrovani titl."""

        return bool(self.subtitle_languages)

    @property
    def is_dubbed(self) -> bool:
        """Vraca True kada postoji bar jedna sinhronizacija."""

        return bool(self.dubbed_audio_languages)

    def _languages_for(
        self,
        localization_type: MediaLocalizationType,
    ) -> tuple[str, ...]:
        values = {
            item.language_code
            for item in self.localizations
            if item.localization_type is localization_type
        }
        return tuple(sorted(values, key=str.casefold))


# ==========          JEZICKI PREGLED SADRZAJA          ==========

@dataclass(frozen=True)
class MediaLocalizationSummary:
    """Podaci koje GUI koristi za oznake i filtere."""

    media_id: int
    origin_scope: MediaOriginScope
    original_language_code: str | None
    subtitle_languages: tuple[str, ...] = ()
    dubbed_audio_languages: tuple[str, ...] = ()

    @property
    def is_subtitled(self) -> bool:
        """Vraca True kada postoji bar jedan registrovani titl."""

        return bool(self.subtitle_languages)

    @property
    def is_dubbed(self) -> bool:
        """Vraca True kada postoji bar jedna sinhronizacija."""

        return bool(self.dubbed_audio_languages)