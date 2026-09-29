from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status
from fastapi.responses import StreamingResponse

from apps.api.dependencies import (
    get_share_service,
    get_share_transfer_service,
)
from apps.api.schemas.filmium_share import (
    ShareProfileRequest,
    ShareProfileResponse,
    ShareQueueAddRequest,
    ShareQueueItemResponse,
    ShareTransferModeRequest,
    ShareTransferRequest,
    ShareTransferResponse,
)
from apps.api.streaming import import_progress_stream
from core.domains.filmium.share_service import (
    ShareConflictError,
    ShareMediaNotFoundError,
    ShareProfileDisabledError,
    ShareProfileNotFoundError,
    ShareQueueItemNotFoundError,
    ShareService,
    ShareValidationError,
)
from core.domains.filmium.share_transfer_service import (
    ShareTransferService,
)

router = APIRouter(
    prefix="/api/v1/filmium/share",
    tags=["FILMIUM Share"],
)

ShareServiceDependency = Annotated[
    ShareService,
    Depends(get_share_service),
]

ShareTransferServiceDependency = Annotated[
    ShareTransferService,
    Depends(get_share_transfer_service),
]


def _not_found(error: LookupError) -> HTTPException:
    """Pravi standardni 404 odgovor za Podeli resurse."""

    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=str(error),
    )


# ==========          PROFILI          ==========

@router.get(
    "/profiles",
    response_model=list[ShareProfileResponse],
)
def list_share_profiles(
    service: ShareServiceDependency,
) -> list[ShareProfileResponse]:
    """Vraca sve profile funkcije Podeli."""

    return [
        ShareProfileResponse.from_domain(profile)
        for profile in service.list_profiles()
    ]


@router.post(
    "/profiles",
    response_model=ShareProfileResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_share_profile(
    request: ShareProfileRequest,
    service: ShareServiceDependency,
) -> ShareProfileResponse:
    """Pravi novi profil, na primer Deki."""

    try:
        profile = service.create_profile(request.to_domain())
    except ShareValidationError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(error),
        ) from error
    except ShareConflictError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(error),
        ) from error

    return ShareProfileResponse.from_domain(profile)


@router.get(
    "/profiles/{profile_id}",
    response_model=ShareProfileResponse,
)
def get_share_profile(
    profile_id: int,
    service: ShareServiceDependency,
) -> ShareProfileResponse:
    """Vraca jedan profil."""

    try:
        profile = service.get_profile(profile_id)
    except ShareProfileNotFoundError as error:
        raise _not_found(error) from error

    return ShareProfileResponse.from_domain(profile)


@router.put(
    "/profiles/{profile_id}",
    response_model=ShareProfileResponse,
)
def update_share_profile(
    profile_id: int,
    request: ShareProfileRequest,
    service: ShareServiceDependency,
) -> ShareProfileResponse:
    """Menja profil i njegov podrazumevani odredisni folder."""

    try:
        profile = service.update_profile(
            profile_id,
            request.to_domain(),
        )
    except ShareValidationError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(error),
        ) from error
    except ShareConflictError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(error),
        ) from error
    except ShareProfileNotFoundError as error:
        raise _not_found(error) from error

    return ShareProfileResponse.from_domain(profile)


@router.delete(
    "/profiles/{profile_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_share_profile(
    profile_id: int,
    service: ShareServiceDependency,
) -> Response:
    """Brise profil i njegov red, ali ne i filmove."""

    try:
        service.delete_profile(profile_id)
    except ShareProfileNotFoundError as error:
        raise _not_found(error) from error

    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ==========          RED PROFILA          ==========

@router.get(
    "/profiles/{profile_id}/queue",
    response_model=list[ShareQueueItemResponse],
)
def list_share_queue(
    profile_id: int,
    service: ShareServiceDependency,
) -> list[ShareQueueItemResponse]:
    """Vraca filmove pripremljene za izabrani profil."""

    try:
        queue = service.list_queue(profile_id)
    except ShareProfileNotFoundError as error:
        raise _not_found(error) from error

    return [
        ShareQueueItemResponse.from_domain(item)
        for item in queue
    ]


@router.post(
    "/profiles/{profile_id}/queue",
    response_model=ShareQueueItemResponse,
    status_code=status.HTTP_201_CREATED,
)
def add_to_share_queue(
    profile_id: int,
    request: ShareQueueAddRequest,
    service: ShareServiceDependency,
) -> ShareQueueItemResponse:
    """Dodaje film u red sa izabranim obimom kopiranja."""

    try:
        item = service.add_to_queue(request.to_domain(profile_id))
    except (
        ShareProfileNotFoundError,
        ShareMediaNotFoundError,
    ) as error:
        raise _not_found(error) from error
    except (
        ShareConflictError,
        ShareProfileDisabledError,
    ) as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(error),
        ) from error

    return ShareQueueItemResponse.from_domain(item)


@router.patch(
    "/queue/{queue_item_id}/mode",
    response_model=ShareQueueItemResponse,
)
def change_share_transfer_mode(
    queue_item_id: int,
    request: ShareTransferModeRequest,
    service: ShareServiceDependency,
) -> ShareQueueItemResponse:
    """Menja Za gledanje ili Kompletno za postojecu stavku."""

    try:
        item = service.change_transfer_mode(
            queue_item_id,
            request.transfer_mode,
        )
    except ShareQueueItemNotFoundError as error:
        raise _not_found(error) from error

    return ShareQueueItemResponse.from_domain(item)


@router.delete(
    "/queue/{queue_item_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def remove_from_share_queue(
    queue_item_id: int,
    service: ShareServiceDependency,
) -> Response:
    """Uklanja stavku iz reda bez promene FILMIUM kataloga."""

    try:
        service.remove_from_queue(queue_item_id)
    except ShareQueueItemNotFoundError as error:
        raise _not_found(error) from error

    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ==========          PRENOS (KOPIRANJE, SSE PROGRES)          ==========

@router.post("/transfer/stream")
def transfer_share_stream(
    request: ShareTransferRequest,
    service: ShareTransferServiceDependency,
) -> StreamingResponse:
    """Kopira izabrane kataloške stavke na lokaciju uz per-fajl progres.

    Emituje ``event: progress`` po fajlu (globalno preko svih stavki),
    pa ``event: done`` sa sažetkom prenosa ili ``event: error``.
    """

    def run(on_progress):
        return service.execute_transfer(
            tuple(request.media_ids),
            request.destination_path,
            on_progress=on_progress,
        )

    return import_progress_stream(
        run,
        lambda summary: ShareTransferResponse.from_domain(
            summary
        ).model_dump(mode="json"),
    )