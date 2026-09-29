from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from apps.api.dependencies import get_localization_service
from apps.api.schemas.filmium_localization import (
    LanguageOptionResponse,
    MediaLocalizationSettingsRequest,
    MediaLocalizationSettingsResponse,
)
from core.domains.filmium.language_catalog import (
    FILMIUM_LANGUAGE_OPTIONS,
)
from core.domains.filmium.localization_service import (
    LocalizationService,
    MediaLocalizationConflictError,
    MediaLocalizationNotFoundError,
    MediaLocalizationSourceError,
    MediaLocalizationValidationError,
)

router = APIRouter(
    prefix="/api/v1/filmium/localization",
    tags=["FILMIUM Localization"],
)

LocalizationServiceDependency = Annotated[
    LocalizationService,
    Depends(get_localization_service),
]


# ==========          KATALOG JEZIKA          ==========

@router.get(
    "/languages",
    response_model=list[LanguageOptionResponse],
)
def list_language_options() -> list[LanguageOptionResponse]:
    """Vraca kontrolisane jezike koje GUI prikazuje korisniku."""

    return [
        LanguageOptionResponse.from_domain(item)
        for item in FILMIUM_LANGUAGE_OPTIONS
    ]


# ==========          PODESAVANJA FILMA          ==========

@router.get(
    "/media/{media_id}",
    response_model=MediaLocalizationSettingsResponse,
)
def get_media_localization(
    media_id: int,
    service: LocalizationServiceDependency,
) -> MediaLocalizationSettingsResponse:
    """Vraca poreklo, originalni jezik, titlove i sinhronizacije."""

    try:
        settings = service.get_settings(media_id)
    except MediaLocalizationNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(error),
        ) from error

    return MediaLocalizationSettingsResponse.from_domain(settings)


@router.put(
    "/media/{media_id}",
    response_model=MediaLocalizationSettingsResponse,
)
def replace_media_localization(
    media_id: int,
    request: MediaLocalizationSettingsRequest,
    service: LocalizationServiceDependency,
) -> MediaLocalizationSettingsResponse:
    """Atomski menja kompletna jezicka podesavanja filma."""

    try:
        settings = service.replace_settings(
            request.to_domain(media_id)
        )
    except MediaLocalizationNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(error),
        ) from error
    except (
        MediaLocalizationValidationError,
        MediaLocalizationSourceError,
    ) as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(error),
        ) from error
    except MediaLocalizationConflictError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(error),
        ) from error

    return MediaLocalizationSettingsResponse.from_domain(settings)