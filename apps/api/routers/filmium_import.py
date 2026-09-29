from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse

from apps.api.dependencies import (
    get_library_import_commit_service,
    get_library_import_service,
)
from apps.api.schemas.filmium_import import (
    DuplicateComparisonResponse,
    LibraryImportCommitRequest,
    LibraryImportCommitResponse,
    LibraryImportPreviewRequest,
    LibraryImportPreviewResponse,
)
from apps.api.streaming import import_progress_stream
from core.domains.filmium.library_import_commit_service import (
    LibraryImportCommitError,
    LibraryImportCommitService,
)
from core.domains.filmium.library_import_service import (
    LibraryImportPreviewError,
    LibraryImportRootNotFoundError,
    LibraryImportService,
)

router = APIRouter(
    prefix="/api/v1/filmium/libraries",
    tags=["FILMIUM Import"],
)

LibraryImportServiceDependency = Annotated[
    LibraryImportService,
    Depends(get_library_import_service),
]

LibraryImportCommitServiceDependency = Annotated[
    LibraryImportCommitService,
    Depends(get_library_import_commit_service),
]


# ==========          IMPORT PREVIEW          ==========

@router.post(
    "/{root_id}/imports/preview",
    response_model=LibraryImportPreviewResponse,
)
def preview_library_import(
    root_id: int,
    request: LibraryImportPreviewRequest,
    service: LibraryImportServiceDependency,
) -> LibraryImportPreviewResponse:
    """Priprema pregled uvoza bez promene baze ili filesystema."""

    try:
        preview = service.preview_import(
            root_id,
            request.relative_directory,
            include_tmdb=request.include_tmdb,
        )
    except LibraryImportRootNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(error),
        ) from error
    except LibraryImportPreviewError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(error),
        ) from error

    return LibraryImportPreviewResponse.from_domain(preview)


# ==========          POTVRDA UVOZA          ==========

@router.post(
    "/{root_id}/imports/confirm",
    response_model=LibraryImportCommitResponse,
)
def confirm_library_import(
    root_id: int,
    request: LibraryImportCommitRequest,
    service: LibraryImportCommitServiceDependency,
) -> LibraryImportCommitResponse:
    """Organizuje i registruje kandidat koji je korisnik potvrdio."""

    try:
        result = service.confirm_import(
            root_id,
            request.relative_directory,
            confirmed=request.confirmed,
            target_media_id=request.target_media_id,
            target_library_root_id=request.target_library_root_id,
            override_title=request.title,
            override_release_year=request.release_year,
            override_genres=(
                tuple(request.genres)
                if request.genres is not None
                else None
            ),
            conflict_mode=request.conflict_mode,
            content_mode=request.content_mode,
            synchronized=request.synchronized,
        )
    except LibraryImportCommitError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(error),
        ) from error

    return LibraryImportCommitResponse.from_domain(result)


# ==========          POTVRDA UVOZA (SSE PROGRES)          ==========

@router.post("/{root_id}/imports/confirm/stream")
def confirm_library_import_stream(
    root_id: int,
    request: LibraryImportCommitRequest,
    service: LibraryImportCommitServiceDependency,
) -> StreamingResponse:
    """Kao ``confirm``, ali strimuje per-fajl progres (SSE).

    Emituje ``event: progress`` po fajlu, pa ``event: done`` sa istim
    telom kao obični confirm, ili ``event: error`` sa porukom.
    """

    def run(on_progress):
        return service.confirm_import(
            root_id,
            request.relative_directory,
            confirmed=request.confirmed,
            target_media_id=request.target_media_id,
            target_library_root_id=request.target_library_root_id,
            override_title=request.title,
            override_release_year=request.release_year,
            override_genres=(
                tuple(request.genres)
                if request.genres is not None
                else None
            ),
            on_progress=on_progress,
            conflict_mode=request.conflict_mode,
            content_mode=request.content_mode,
            synchronized=request.synchronized,
        )

    return import_progress_stream(
        run,
        lambda result: LibraryImportCommitResponse.from_domain(
            result
        ).model_dump(mode="json"),
    )


# ==========          DUPLIKAT POREĐENJE          ==========

@router.post(
    "/{root_id}/imports/duplicates",
    response_model=DuplicateComparisonResponse,
)
def compare_import_duplicates(
    root_id: int,
    request: LibraryImportPreviewRequest,
    service: LibraryImportServiceDependency,
) -> DuplicateComparisonResponse:
    """Poredi skenirani folder sa postojećim (identično/slično/novo)."""

    try:
        comparison = service.compare_duplicate(
            root_id,
            request.relative_directory,
        )
    except LibraryImportRootNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(error),
        ) from error
    except LibraryImportPreviewError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(error),
        ) from error

    return DuplicateComparisonResponse.from_domain(comparison)


# ==========          UNIŠTI SKENIRANI FOLDER          ==========

@router.post(
    "/{root_id}/imports/destroy",
    status_code=status.HTTP_204_NO_CONTENT,
)
def destroy_scanned_directory(
    root_id: int,
    request: LibraryImportPreviewRequest,
    service: LibraryImportServiceDependency,
) -> None:
    """Trajno briše skenirani izvorni folder sa diska („Uništi")."""

    try:
        service.delete_source_directory(
            root_id,
            request.relative_directory,
        )
    except LibraryImportRootNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(error),
        ) from error
    except LibraryImportPreviewError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(error),
        ) from error