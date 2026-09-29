from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status

from apps.api.dependencies import get_library_date_service
from apps.api.schemas.filmium_library_date import (
    MediaLibraryDateRequest,
    MediaLibraryDateResponse,
)
from core.domains.filmium.library_date_service import (
    LibraryDateService,
    MediaLibraryDateNotFoundError,
    MediaLibraryDateValidationError,
)

router = APIRouter(
    prefix="/api/v1/filmium/library-dates",
    tags=["FILMIUM Library Dates"],
)

LibraryDateServiceDependency = Annotated[
    LibraryDateService,
    Depends(get_library_date_service),
]


# ==========          DATUM JEDNOG SADRZAJA          ==========

@router.get(
    "/media/{media_id}",
    response_model=MediaLibraryDateResponse,
)
def get_media_library_date(
    media_id: int,
    service: LibraryDateServiceDependency,
) -> MediaLibraryDateResponse:
    """Vraca korisnicki datum ulaska sadrzaja u biblioteku."""

    try:
        record = service.get_media_date(media_id)
    except MediaLibraryDateNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(error),
        ) from error

    return MediaLibraryDateResponse.from_domain(record)


@router.patch(
    "/media/{media_id}",
    response_model=MediaLibraryDateResponse,
)
def update_media_library_date(
    media_id: int,
    request: MediaLibraryDateRequest,
    service: LibraryDateServiceDependency,
) -> MediaLibraryDateResponse:
    """Menja datum bez menjanja tehnickog created_at polja."""

    try:
        record = service.update_media_date(
            request.to_domain(media_id)
        )
    except MediaLibraryDateNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(error),
        ) from error
    except MediaLibraryDateValidationError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(error),
        ) from error

    return MediaLibraryDateResponse.from_domain(record)


# ==========          NAJNOVIJE DODATO          ==========

@router.get(
    "/recent",
    response_model=list[MediaLibraryDateResponse],
)
def list_recent_media(
    service: LibraryDateServiceDependency,
    limit: int = Query(default=50, ge=1, le=500),
) -> list[MediaLibraryDateResponse]:
    """Vraca sadrzaje sortirane po korisnickom datumu dodavanja."""

    return [
        MediaLibraryDateResponse.from_domain(record)
        for record in service.list_recent(limit)
    ]