from datetime import datetime

from pydantic import BaseModel, Field

from core.domains.filmium.language_catalog import LanguageOption
from core.domains.filmium.localization_models import (
    MediaLocalization,
    MediaLocalizationCreate,
    MediaLocalizationSettings,
    MediaLocalizationSettingsUpdate,
    MediaLocalizationType,
    MediaOriginScope,
)

# ==========          JEZICI          ==========

class LanguageOptionResponse(BaseModel):
    code: str
    name: str

    @classmethod
    def from_domain(
        cls,
        item: LanguageOption,
    ) -> "LanguageOptionResponse":
        return cls(code=item.code, name=item.name)


# ==========          ZAHTEV LOKALIZACIJE          ==========

class MediaLocalizationRequest(BaseModel):
    localization_type: MediaLocalizationType
    language_code: str = Field(min_length=2, max_length=35)
    source_id: int | None = Field(default=None, gt=0)
    label: str | None = Field(default=None, max_length=100)
    is_primary: bool = False

    def to_domain(self, media_id: int) -> MediaLocalizationCreate:
        """Pretvara jednu API stavku u domenski model."""

        return MediaLocalizationCreate(
            media_id=media_id,
            source_id=self.source_id,
            localization_type=self.localization_type,
            language_code=self.language_code,
            label=self.label,
            is_primary=self.is_primary,
        )


class MediaLocalizationSettingsRequest(BaseModel):
    origin_scope: MediaOriginScope = MediaOriginScope.UNKNOWN
    original_language_code: str | None = Field(
        default=None,
        max_length=35,
    )
    localizations: list[MediaLocalizationRequest] = Field(
        default_factory=list
    )

    def to_domain(
        self,
        media_id: int,
    ) -> MediaLocalizationSettingsUpdate:
        """Pravi kompletan domenski zahtev za film iz URL putanje."""

        return MediaLocalizationSettingsUpdate(
            media_id=media_id,
            origin_scope=self.origin_scope,
            original_language_code=self.original_language_code,
            localizations=tuple(
                item.to_domain(media_id)
                for item in self.localizations
            ),
        )


# ==========          ODGOVOR LOKALIZACIJE          ==========

class MediaLocalizationResponse(BaseModel):
    id: int
    media_id: int
    source_id: int | None
    localization_type: MediaLocalizationType
    language_code: str
    label: str | None
    is_primary: bool
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_domain(
        cls,
        item: MediaLocalization,
    ) -> "MediaLocalizationResponse":
        return cls(
            id=item.id,
            media_id=item.media_id,
            source_id=item.source_id,
            localization_type=item.localization_type,
            language_code=item.language_code,
            label=item.label,
            is_primary=item.is_primary,
            created_at=item.created_at,
            updated_at=item.updated_at,
        )


class MediaLocalizationSettingsResponse(BaseModel):
    media_id: int
    origin_scope: MediaOriginScope
    original_language_code: str | None
    subtitle_languages: list[str]
    dubbed_audio_languages: list[str]
    is_subtitled: bool
    is_dubbed: bool
    localizations: list[MediaLocalizationResponse]

    @classmethod
    def from_domain(
        cls,
        item: MediaLocalizationSettings,
    ) -> "MediaLocalizationSettingsResponse":
        return cls(
            media_id=item.media_id,
            origin_scope=item.origin_scope,
            original_language_code=item.original_language_code,
            subtitle_languages=list(item.subtitle_languages),
            dubbed_audio_languages=list(
                item.dubbed_audio_languages
            ),
            is_subtitled=item.is_subtitled,
            is_dubbed=item.is_dubbed,
            localizations=[
                MediaLocalizationResponse.from_domain(localization)
                for localization in item.localizations
            ],
        )