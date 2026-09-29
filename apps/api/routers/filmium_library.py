from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from fastapi.responses import FileResponse

from apps.api.dependencies import get_library_root_service
from apps.api.schemas.filmium_library import (
    LibraryIgnoredDirectoriesResponse,
    LibraryIgnoreDirectoryRequest,
    LibraryRootRequest,
    LibraryRootResponse,
    LibraryRootScanResponse,
)
from core.domains.filmium.library_root_service import (
    LibraryArtworkNotFoundError,
    LibraryRootConflictError,
    LibraryRootNotFoundError,
    LibraryRootService,
    LibraryRootValidationError,
)

router = APIRouter(
    prefix="/api/v1/filmium/libraries",
    tags=["FILMIUM Library"],
)

LibraryRootServiceDependency = Annotated[
    LibraryRootService,
    Depends(get_library_root_service),
]


def _not_found(error: LibraryRootNotFoundError) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=str(error),
    )


# ==========          CRUD BIBLIOTEKE          ==========

@router.get("", response_model=list[LibraryRootResponse])
def list_library_roots(
    service: LibraryRootServiceDependency,
) -> list[LibraryRootResponse]:
    return [
        LibraryRootResponse.from_domain(root)
        for root in service.list_library_roots()
    ]


@router.post(
    "",
    response_model=LibraryRootResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_library_root(
    request: LibraryRootRequest,
    service: LibraryRootServiceDependency,
) -> LibraryRootResponse:
    try:
        root = service.create_library_root(request.to_domain())
    except LibraryRootValidationError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(error),
        ) from error
    except LibraryRootConflictError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(error),
        ) from error

    return LibraryRootResponse.from_domain(root)


@router.get("/{root_id}", response_model=LibraryRootResponse)
def get_library_root(
    root_id: int,
    service: LibraryRootServiceDependency,
) -> LibraryRootResponse:
    try:
        root = service.get_library_root(root_id)
    except LibraryRootNotFoundError as error:
        raise _not_found(error) from error

    return LibraryRootResponse.from_domain(root)


@router.put("/{root_id}", response_model=LibraryRootResponse)
def update_library_root(
    root_id: int,
    request: LibraryRootRequest,
    service: LibraryRootServiceDependency,
) -> LibraryRootResponse:
    try:
        root = service.update_library_root(
            root_id,
            request.to_domain(),
        )
    except LibraryRootValidationError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(error),
        ) from error
    except LibraryRootConflictError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(error),
        ) from error
    except LibraryRootNotFoundError as error:
        raise _not_found(error) from error

    return LibraryRootResponse.from_domain(root)


@router.post("/{root_id}/main", response_model=LibraryRootResponse)
def set_main_library_root(
    root_id: int,
    service: LibraryRootServiceDependency,
) -> LibraryRootResponse:
    """Označava disk kao glavni (podrazumevano odredište uvoza)."""

    try:
        root = service.set_main_library(root_id)
    except LibraryRootNotFoundError as error:
        raise _not_found(error) from error

    return LibraryRootResponse.from_domain(root)


@router.delete("/{root_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_library_root(
    root_id: int,
    service: LibraryRootServiceDependency,
) -> Response:
    try:
        service.delete_library_root(root_id)
    except LibraryRootNotFoundError as error:
        raise _not_found(error) from error

    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ==========          SKENIRANJE          ==========

@router.get(
    "/{root_id}/entries/artwork",
    response_class=FileResponse,
)
def get_discovered_media_artwork(
    root_id: int,
    service: LibraryRootServiceDependency,
    directory: str = Query(min_length=1),
    file: str | None = Query(default=None),
) -> FileResponse:
    """Bezbedno prikazuje sliku otkrivene kartice iz registrovanog root-a.

    Bez ``file`` vraća najbolju (poster/backdrop) sliku foldera; sa
    ``file`` vraća tačno tu sliku po relativnoj putanji.
    """

    try:
        if file is not None:
            artwork = service.get_entry_artwork_file(
                root_id,
                directory,
                file,
            )
        else:
            artwork = service.get_discovery_artwork(root_id, directory)
    except LibraryRootNotFoundError as error:
        raise _not_found(error) from error
    except LibraryArtworkNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(error),
        ) from error

    return FileResponse(
        artwork,
        headers={
            "Cache-Control": "private, max-age=60",
            "X-Content-Type-Options": "nosniff",
        },
    )

@router.post(
    "/{root_id}/scan",
    response_model=LibraryRootScanResponse,
)
def scan_registered_library_root(
    root_id: int,
    service: LibraryRootServiceDependency,
    scan_subtitles: bool = True,
    only_new: bool = False,
) -> LibraryRootScanResponse:
    try:
        result = service.scan_library_root(
            root_id,
            scan_subtitles=scan_subtitles,
            only_new=only_new,
        )
    except LibraryRootNotFoundError as error:
        raise _not_found(error) from error

    return LibraryRootScanResponse.from_domain(result)


# ==========          IGNORISANI FOLDERI          ==========

@router.get(
    "/{root_id}/ignored",
    response_model=LibraryIgnoredDirectoriesResponse,
)
def list_ignored_directories(
    root_id: int,
    service: LibraryRootServiceDependency,
) -> LibraryIgnoredDirectoriesResponse:
    try:
        directories = service.list_ignored_directories(root_id)
    except LibraryRootNotFoundError as error:
        raise _not_found(error) from error

    return LibraryIgnoredDirectoriesResponse(
        directories=list(directories),
    )


@router.post(
    "/{root_id}/ignored",
    status_code=status.HTTP_204_NO_CONTENT,
)
def ignore_directory(
    root_id: int,
    request: LibraryIgnoreDirectoryRequest,
    service: LibraryRootServiceDependency,
) -> Response:
    try:
        service.ignore_directory(root_id, request.relative_directory)
    except LibraryRootNotFoundError as error:
        raise _not_found(error) from error

    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete(
    "/{root_id}/ignored",
    status_code=status.HTTP_204_NO_CONTENT,
)
def unignore_directory(
    root_id: int,
    service: LibraryRootServiceDependency,
    directory: str = Query(min_length=1),
) -> Response:
    try:
        service.unignore_directory(root_id, directory)
    except LibraryRootNotFoundError as error:
        raise _not_found(error) from error

    return Response(status_code=status.HTTP_204_NO_CONTENT)
