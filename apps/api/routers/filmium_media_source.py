from typing import Annotated

from fastapi import (
    APIRouter,
    Depends,
    File,
    HTTPException,
    Response,
    UploadFile,
    status,
)
from pydantic import BaseModel

from apps.api.dependencies import get_media_source_service
from apps.api.schemas.filmium_media_source import (
    MediaFilesReplaceRequest,
    MediaSourceAvailabilityRequest,
    MediaSourceRequest,
    MediaSourceResponse,
)
from core.domains.filmium.media_source_service import (
    MediaSourceConflictError,
    MediaSourceLibraryNotFoundError,
    MediaSourceMediaNotFoundError,
    MediaSourceNotFoundError,
    MediaSourceRescanError,
    MediaSourceService,
    MediaSourceValidationError,
)

router = APIRouter(tags=["FILMIUM Media Sources"])

MediaSourceServiceDependency = Annotated[
    MediaSourceService,
    Depends(get_media_source_service),
]


# ==========          API GRESKE          ==========

def _not_found(error: LookupError) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=str(error),
    )


def _validation_error(error: ValueError) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        detail=str(error),
    )


# ==========          IZVORI JEDNOG SADRZAJA          ==========

@router.get(
    "/api/v1/filmium/media/{media_id}/sources",
    response_model=list[MediaSourceResponse],
)
def list_media_sources(
    media_id: int,
    service: MediaSourceServiceDependency,
) -> list[MediaSourceResponse]:
    try:
        sources = service.list_media_sources(media_id)
    except MediaSourceMediaNotFoundError as error:
        raise _not_found(error) from error

    return [
        MediaSourceResponse.from_domain(source)
        for source in sources
    ]


@router.post(
    "/api/v1/filmium/media/{media_id}/sources",
    response_model=MediaSourceResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_media_source(
    media_id: int,
    request: MediaSourceRequest,
    service: MediaSourceServiceDependency,
) -> MediaSourceResponse:
    try:
        source = service.create_media_source(
            request.to_domain(media_id)
        )
    except MediaSourceValidationError as error:
        raise _validation_error(error) from error
    except MediaSourceConflictError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(error),
        ) from error
    except (
        MediaSourceMediaNotFoundError,
        MediaSourceLibraryNotFoundError,
    ) as error:
        raise _not_found(error) from error

    return MediaSourceResponse.from_domain(source)


# ==========          POJEDINACNI IZVOR          ==========

@router.get(
    "/api/v1/filmium/media-sources/{source_id}",
    response_model=MediaSourceResponse,
)
def get_media_source(
    source_id: int,
    service: MediaSourceServiceDependency,
) -> MediaSourceResponse:
    try:
        source = service.get_media_source(source_id)
    except MediaSourceNotFoundError as error:
        raise _not_found(error) from error

    return MediaSourceResponse.from_domain(source)


@router.delete(
    "/api/v1/filmium/media-sources/{source_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_media_source(
    source_id: int,
    service: MediaSourceServiceDependency,
) -> Response:
    try:
        service.delete_media_source(source_id)
    except MediaSourceNotFoundError as error:
        raise _not_found(error) from error

    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ==========          DATOTEKE I DOSTUPNOST          ==========

@router.put(
    "/api/v1/filmium/media-sources/{source_id}/files",
    response_model=MediaSourceResponse,
)
def replace_media_source_files(
    source_id: int,
    request: MediaFilesReplaceRequest,
    service: MediaSourceServiceDependency,
) -> MediaSourceResponse:
    try:
        source = service.replace_media_files(
            source_id,
            request.to_domain(),
        )
    except MediaSourceValidationError as error:
        raise _validation_error(error) from error
    except MediaSourceConflictError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(error),
        ) from error
    except (
        MediaSourceNotFoundError,
        MediaSourceMediaNotFoundError,
    ) as error:
        raise _not_found(error) from error

    return MediaSourceResponse.from_domain(source)


@router.patch(
    "/api/v1/filmium/media-sources/{source_id}/availability",
    response_model=MediaSourceResponse,
)
def set_media_source_availability(
    source_id: int,
    request: MediaSourceAvailabilityRequest,
    service: MediaSourceServiceDependency,
) -> MediaSourceResponse:
    try:
        source = service.set_media_source_availability(
            source_id,
            request.availability_status,
        )
    except MediaSourceNotFoundError as error:
        raise _not_found(error) from error

    return MediaSourceResponse.from_domain(source)


@router.post(
    "/api/v1/filmium/media-sources/{source_id}/rescan",
    response_model=MediaSourceResponse,
)
def rescan_media_source(
    source_id: int,
    service: MediaSourceServiceDependency,
) -> MediaSourceResponse:
    try:
        source = service.rescan_media_source(source_id)
    except MediaSourceRescanError as error:
        raise _validation_error(error) from error
    except (
        MediaSourceNotFoundError,
        MediaSourceMediaNotFoundError,
    ) as error:
        raise _not_found(error) from error

    return MediaSourceResponse.from_domain(source)


# ==========          TITLOVI (upload / brisanje / preuzimanje)          =====

class FileDownloadResponse(BaseModel):
    """Odredišna putanja kopirane datoteke."""

    path: str


@router.post(
    "/api/v1/filmium/media-sources/{source_id}/subtitles",
    response_model=MediaSourceResponse,
)
async def add_subtitle_to_source(
    source_id: int,
    service: MediaSourceServiceDependency,
    file: UploadFile = File(...),
) -> MediaSourceResponse:
    """Dodaje titl fajl u folder izvora i ponovo skenira izvor."""

    try:
        content = await file.read()
        source = service.add_subtitle_file(
            source_id,
            file.filename or "",
            content,
        )
    except MediaSourceValidationError as error:
        raise _validation_error(error) from error
    except MediaSourceRescanError as error:
        raise _validation_error(error) from error
    except MediaSourceNotFoundError as error:
        raise _not_found(error) from error
    finally:
        await file.close()

    return MediaSourceResponse.from_domain(source)


@router.delete(
    "/api/v1/filmium/media-sources/{source_id}/files/{file_id}",
    response_model=MediaSourceResponse,
)
def delete_source_file(
    source_id: int,
    file_id: int,
    service: MediaSourceServiceDependency,
) -> MediaSourceResponse:
    """Briše fizičku datoteku izvora (npr. titl) sa diska."""

    try:
        source = service.delete_source_file(source_id, file_id)
    except MediaSourceRescanError as error:
        raise _validation_error(error) from error
    except MediaSourceNotFoundError as error:
        raise _not_found(error) from error

    return MediaSourceResponse.from_domain(source)


@router.post(
    "/api/v1/filmium/media-sources/{source_id}/files/{file_id}/download",
    response_model=FileDownloadResponse,
)
def copy_source_file_to_desktop(
    source_id: int,
    file_id: int,
    service: MediaSourceServiceDependency,
) -> FileDownloadResponse:
    """Kopira datoteku izvora na Desktop korisnika."""

    try:
        destination = service.copy_source_file_to_desktop(
            source_id,
            file_id,
        )
    except MediaSourceRescanError as error:
        raise _validation_error(error) from error
    except MediaSourceNotFoundError as error:
        raise _not_found(error) from error

    return FileDownloadResponse(path=destination)
