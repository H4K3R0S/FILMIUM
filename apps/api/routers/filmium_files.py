import re
from pathlib import Path
from typing import Annotated

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    status,
)
from fastapi.responses import StreamingResponse

from apps.api.dependencies import (
    get_episode_repository,
    get_filmium_service,
    get_library_root_repository,
    get_media_source_repository,
    get_media_visual_service,
    get_season_repository,
)
from apps.api.schemas.filmium import (
    BrowseResponse,
    DirectoryEntryResponse,
    DiskResponse,
    MediaFileTreeItemResponse,
    MediaTransferRequest,
    MediaTransferResponse,
)
from apps.api.streaming import import_progress_stream
from core.domains.filmium import media_transfer
from core.domains.filmium.episode_repository import EpisodeRepository
from core.domains.filmium.library_root_repository import (
    LibraryRootRepository,
)
from core.domains.filmium.media_source_repository import (
    MediaSourceRepository,
)
from core.domains.filmium.season_repository import SeasonRepository
from core.domains.filmium.service import (
    FilmiumService,
)
from core.domains.filmium.visual_service import MediaVisualService

# ==========          FILMIUM ROUTER          ==========

router = APIRouter()

FilmiumServiceDependency = Annotated[
    FilmiumService,
    Depends(get_filmium_service),
]


MediaVisualServiceDependency = Annotated[
    MediaVisualService,
    Depends(get_media_visual_service),
]

SeasonRepositoryDependency = Annotated[
    SeasonRepository,
    Depends(get_season_repository),
]

EpisodeRepositoryDependency = Annotated[
    EpisodeRepository,
    Depends(get_episode_repository),
]

MediaSourceRepositoryDependency = Annotated[
    MediaSourceRepository,
    Depends(get_media_source_repository),
]

LibraryRootRepositoryDependency = Annotated[
    LibraryRootRepository,
    Depends(get_library_root_repository),
]


_SEASON_RE = re.compile(r"Sezona\s*(\d+)", re.IGNORECASE)
_EPISODE_RE = re.compile(r"E(\d+)", re.IGNORECASE)




@router.get("/disks", response_model=list[DiskResponse])
def list_disks() -> list[DiskResponse]:
    """Vraća dostupne diskove/particije sa slobodnim prostorom."""

    return [
        DiskResponse(
            path=disk.path,
            label=disk.label,
            total_bytes=disk.total_bytes,
            free_bytes=disk.free_bytes,
        )
        for disk in media_transfer.list_available_disks()
    ]


@router.get("/filesystem/browse", response_model=BrowseResponse)
def browse_filesystem(path: str | None = None) -> BrowseResponse:
    """Navigacija foldera za izbor odredišta prenosa."""

    parent, entries = media_transfer.browse_directory(path)
    return BrowseResponse(
        path=path,
        parent=parent,
        directories=[
            DirectoryEntryResponse(name=entry.name, path=entry.path)
            for entry in entries
        ],
    )


@router.get(
    "/media/{item_id}/file-tree",
    response_model=list[MediaFileTreeItemResponse],
)
def get_media_file_tree(
    item_id: int,
    media_sources: MediaSourceRepositoryDependency,
) -> list[MediaFileTreeItemResponse]:
    """Vraća listu fajlova sadržaja (za stablo izbora pri prenosu).

    Kada je izvorni folder dostupan na disku, nabraja SVE fajlove (video,
    prevodi, slike, ostalo) i klasifikuje ih po tipu. Ako folder nije
    dostupan, vraća indeksirane fajlove iz baze (fallback).
    """

    sources = media_sources.list_for_media(item_id)

    for source in sources:
        source_directory = (
            Path(source.root_path_snapshot)
            if source.relative_directory in {"", "."}
            else Path(source.root_path_snapshot).joinpath(
                *Path(source.relative_directory).parts
            )
        )

        if not source_directory.is_dir():
            continue

        disk_items: list[MediaFileTreeItemResponse] = []
        for relative in media_transfer.enumerate_relative_files(
            source_directory
        ):
            file_path = source_directory.joinpath(
                *Path(relative).parts
            )
            try:
                size_bytes = file_path.stat().st_size
            except OSError:
                size_bytes = 0
            disk_items.append(
                MediaFileTreeItemResponse(
                    relative_path=relative,
                    role=media_transfer.classify_transfer_role(relative),
                    size_bytes=size_bytes,
                )
            )
        return disk_items

    # Fallback: izvor nije na disku → indeksirani fajlovi iz baze.
    items: list[MediaFileTreeItemResponse] = []
    for source in sources:
        for file in source.files:
            items.append(
                MediaFileTreeItemResponse(
                    relative_path=file.relative_path.replace("\\", "/"),
                    role=file.role.value,
                    size_bytes=file.size_bytes,
                )
            )
    return items


@router.post(
    "/media/{item_id}/transfer",
    response_model=MediaTransferResponse,
)
def transfer_media(
    item_id: int,
    request: MediaTransferRequest,
    media_sources: MediaSourceRepositoryDependency,
) -> MediaTransferResponse:
    """Kopira ceo direktorijum ili izabrane fajlove sadržaja na odredište."""

    sources = media_sources.list_for_media(item_id)
    if not sources:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Sadržaj nema registrovan izvor za prenos.",
        )

    source = sources[0]
    source_directory = (
        Path(source.root_path_snapshot)
        if source.relative_directory in {"", "."}
        else Path(source.root_path_snapshot).joinpath(
            *Path(source.relative_directory).parts
        )
    )

    if not source_directory.is_dir():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Izvorni folder sadržaja nije dostupan na disku.",
        )

    # Prazna lista → svi fajlovi (ceo direktorijum).
    if request.relative_paths:
        relative_paths = tuple(request.relative_paths)
    else:
        relative_paths = tuple(
            file.relative_path for file in source.files
        )

    # Sadržaj ide u <odredište>/<ime foldera sadržaja>.
    folder_name = (
        Path(source.relative_directory).name
        if source.relative_directory not in {"", "."}
        else Path(source.root_path_snapshot).name
    )
    destination_directory = Path(request.destination) / folder_name

    result = media_transfer.copy_media_files(
        source_directory,
        relative_paths,
        destination_directory,
    )

    return MediaTransferResponse(
        copied_files=result.copied_files,
        total_bytes=result.total_bytes,
        destination=result.destination,
    )


def _resolve_transfer_plan(
    sources,
    request: MediaTransferRequest,
) -> tuple[Path, tuple[str, ...], Path]:
    """Vraća (izvorni folder, relativne putanje, odredišni folder)."""

    source = sources[0]
    source_directory = (
        Path(source.root_path_snapshot)
        if source.relative_directory in {"", "."}
        else Path(source.root_path_snapshot).joinpath(
            *Path(source.relative_directory).parts
        )
    )

    if request.relative_paths:
        relative_paths = tuple(request.relative_paths)
    else:
        relative_paths = tuple(file.relative_path for file in source.files)

    folder_name = (
        Path(source.relative_directory).name
        if source.relative_directory not in {"", "."}
        else Path(source.root_path_snapshot).name
    )
    destination_directory = Path(request.destination) / folder_name

    return source_directory, relative_paths, destination_directory


@router.post("/media/{item_id}/transfer/stream")
def transfer_media_stream(
    item_id: int,
    request: MediaTransferRequest,
    media_sources: MediaSourceRepositoryDependency,
) -> StreamingResponse:
    """Kao transfer, ali strimuje per-fajl progres (SSE)."""

    sources = media_sources.list_for_media(item_id)
    if not sources:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Sadržaj nema registrovan izvor za prenos.",
        )

    source_directory, relative_paths, destination_directory = (
        _resolve_transfer_plan(sources, request)
    )

    if not source_directory.is_dir():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Izvorni folder sadržaja nije dostupan na disku.",
        )

    def run(on_progress):
        return media_transfer.copy_media_files(
            source_directory,
            relative_paths,
            destination_directory,
            on_progress=on_progress,
        )

    return import_progress_stream(
        run,
        lambda result: {
            "copied_files": result.copied_files,
            "total_bytes": result.total_bytes,
            "destination": result.destination,
        },
    )
