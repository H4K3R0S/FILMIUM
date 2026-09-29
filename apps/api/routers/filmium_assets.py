import re
from typing import Annotated

from fastapi import (
    APIRouter,
    Depends,
    File,
    HTTPException,
    UploadFile,
    status,
)
from fastapi.responses import FileResponse

from apps.api.dependencies import (
    get_episode_repository,
    get_filmium_service,
    get_library_root_repository,
    get_media_asset_service,
    get_media_source_repository,
    get_media_visual_service,
    get_season_repository,
)
from apps.api.schemas.filmium import (
    MediaItemResponse,
)
from core.domains.filmium.asset_service import (
    MediaAssetService,
    MediaAssetType,
    MediaAssetValidationError,
)
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
    MediaItemNotFoundError,
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




def parse_media_asset_type(
    asset_type: str,
) -> MediaAssetType:
    """
    Pretvara API vrednost tipa asseta u FILMIUM domenski enum.

    Eksplicitna konverzija izbegava problem automatskog razrešavanja
    StrEnum anotacija između Python 3.14, FastAPI-ja i Pydantic-a.
    """

    try:
        return MediaAssetType(asset_type)
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=(
                "Tip FILMIUM asseta mora biti "
                "'poster' ili 'backdrop'."
            ),
        ) from error

MediaAssetServiceDependency = Annotated[
    MediaAssetService,
    Depends(get_media_asset_service),
]

# ==========          FILMIUM VIZUELNI ASSETI          ==========

@router.post(
    "/media/{item_id}/assets/{asset_type}",
    response_model=MediaItemResponse,
)
async def upload_media_asset(
    item_id: int,
    asset_type: str,
    service: MediaVisualServiceDependency,
    file: UploadFile = File(...),
) -> MediaItemResponse:
    """
    Čuva poster ili backdrop sliku FILMIUM sadržaja.

    Format slike se proverava iz njenog binarnog sadržaja, a ne samo
    na osnovu naziva datoteke ili vrednosti Content-Type zaglavlja.
    """

    parsed_asset_type = parse_media_asset_type(asset_type)

    try:
        content = await file.read()

        item = service.save_media_asset(
            item_id=item_id,
            asset_type=parsed_asset_type,
            content=content,
        )
    except MediaAssetValidationError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(error),
        ) from error
    except MediaItemNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(error),
        ) from error
    finally:
        await file.close()

    return MediaItemResponse.from_domain(item)


@router.delete(
    "/media/{item_id}/assets/{asset_type}",
    response_model=MediaItemResponse,
)
def delete_media_asset(
    item_id: int,
    asset_type: str,
    service: MediaVisualServiceDependency,
) -> MediaItemResponse:
    """Uklanja poster ili backdrop sliku FILMIUM sadržaja."""

    parsed_asset_type = parse_media_asset_type(asset_type)

    try:
        item = service.delete_media_asset(
            item_id=item_id,
            asset_type=parsed_asset_type,
        )
    except MediaItemNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(error),
        ) from error

    return MediaItemResponse.from_domain(item)



# ==========          FILMIUM ASSET DATOTEKE          ==========

@router.get(
    "/assets/{asset_path:path}",
    response_class=FileResponse,
)
def serve_media_asset(
    asset_path: str,
    service: MediaAssetServiceDependency,
) -> FileResponse:
    """
    Vraća jednu kontrolisanu FILMIUM vizuelnu datoteku.

    API ne prihvata apsolutne filesystem putanje i ne dozvoljava
    pristup datotekama izvan FILMIUM assets direktorijuma.
    """

    try:
        resolved_path = service.get_asset_path(asset_path)
    except MediaAssetValidationError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="FILMIUM vizuelni asset nije pronađen.",
        ) from error

    if resolved_path is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="FILMIUM vizuelni asset nije pronađen.",
        )

    # Posteri/backdrops se retko menjaju, a URL je stabilan (po media id-u).
    # Keš u browseru/webview-u sprečava ponovno skidanje slika sa sporog diska
    # pri svakom skrolu/navigaciji — glavni uzrok sporog prikaza. Prozor pri
    # svakom otvaranju čisti keš, pa nema zastarelih slika između sesija.
    return FileResponse(
        resolved_path,
        headers={
            "Cache-Control": "public, max-age=604800",
            "X-Content-Type-Options": "nosniff",
        },
    )
