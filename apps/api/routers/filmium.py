import re
from pathlib import Path
from typing import Annotated

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Response,
    status,
)
from pydantic import BaseModel, Field

from apps.api.dependencies import (
    get_episode_repository,
    get_filmium_service,
    get_library_root_repository,
    get_media_source_repository,
    get_media_visual_service,
    get_season_repository,
)
from apps.api.schemas.filmium import (
    AutoUpdateRequest,
    AutoUpdateResponse,
    EpisodeMetadataResponse,
    EpisodeUpdateRequest,
    MediaEnrichmentResponse,
    MediaItemCreateRequest,
    MediaItemFavoriteRequest,
    MediaItemResponse,
    MediaTechnicalResponse,
    SeriesEpisodeResponse,
    SeriesSeasonResponse,
)
from core.domains.filmium import media_probe, tmdb_client
from core.domains.filmium.asset_service import (
    MediaAssetType,
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
    FilmiumValidationError,
    MediaItemNotFoundError,
)
from core.domains.filmium.visual_service import MediaVisualService

# ==========          FILMIUM ROUTER          ==========

router = APIRouter(
    prefix="/api/v1/filmium",
    tags=["FILMIUM"],
)

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


def _build_episode_video_index(
    sources,
) -> dict[tuple[int, int], tuple[int | None, str]]:
    """
    Mapira (broj_sezone, broj_epizode) → (root_id, putanja videa relativno
    korenu). Prati organizacioni obrazac „Sezona N/E01 - Naslov.ext".
    """

    index: dict[tuple[int, int], tuple[int | None, str]] = {}
    for source in sources:
        base = source.relative_directory
        for file in source.files:
            if file.role.value != "video":
                continue
            relative = file.relative_path.replace("\\", "/")
            season_match = _SEASON_RE.search(relative)
            name = relative.rsplit("/", 1)[-1]
            episode_match = _EPISODE_RE.match(name)
            if season_match is None or episode_match is None:
                continue
            key = (int(season_match.group(1)), int(episode_match.group(1)))
            root_relative = (
                relative
                if base in {"", "."}
                else f"{base}/{relative}"
            )
            index.setdefault(key, (source.library_root_id, root_relative))

    return index


# ==========          SEZONE I EPIZODE SERIJE          ==========

@router.get(
    "/media/{item_id}/seasons",
    response_model=list[SeriesSeasonResponse],
)
def get_media_seasons(
    item_id: int,
    seasons: SeasonRepositoryDependency,
    episodes: EpisodeRepositoryDependency,
    media_sources: MediaSourceRepositoryDependency,
) -> list[SeriesSeasonResponse]:
    """Vraća sezone serije sa epizodama i putanjom videa (za sličice)."""

    video_index = _build_episode_video_index(
        media_sources.list_for_media(item_id)
    )

    result: list[SeriesSeasonResponse] = []
    for season in seasons.list_for_media(item_id):
        episode_responses = []
        for episode in episodes.list_for_season(season.id):
            root_id, video_source = video_index.get(
                (season.season_number, episode.episode_number),
                (None, None),
            )
            episode_responses.append(
                SeriesEpisodeResponse.from_domain(
                    episode, root_id, video_source
                )
            )
        result.append(
            SeriesSeasonResponse(
                id=season.id,
                season_number=season.season_number,
                name=season.name,
                poster_path=getattr(season, "poster_path", None),
                backdrop_path=getattr(season, "backdrop_path", None),
                episodes=episode_responses,
            )
        )

    return result


class EpisodeTechnicalRequest(BaseModel):
    """Zahtev za ffprobe podatke jedne epizode."""

    root_id: int
    video_source: str


class EpisodeMetadataRequest(BaseModel):
    """Zahtev za TMDB metapodatke epizoda jedne sezone."""

    tmdb_id: int
    season_number: int


@router.post(
    "/media/{item_id}/episode-metadata",
    response_model=list[EpisodeMetadataResponse],
)
def get_episode_metadata(
    item_id: int,
    request: EpisodeMetadataRequest,
) -> list[EpisodeMetadataResponse]:
    """Vraća TMDB opise epizoda (engleski + lokalni) za jednu sezonu."""

    episodes = tmdb_client.season_episode_metadata(
        request.tmdb_id,
        request.season_number,
    )

    return [
        EpisodeMetadataResponse(
            episode_number=episode.episode_number,
            name=episode.name,
            overview_en=episode.overview_en,
            overview_local=episode.overview_local,
            air_date=episode.air_date,
            rating=episode.rating,
            still_url=episode.still_url,
        )
        for episode in episodes
    ]


@router.post(
    "/media/{item_id}/episode-technical",
    response_model=MediaTechnicalResponse,
)
def get_episode_technical(
    item_id: int,
    request: EpisodeTechnicalRequest,
    library_roots: LibraryRootRepositoryDependency,
) -> MediaTechnicalResponse:
    """Vraća ffprobe podatke jedne epizode (rezolucija, codec, veličina…)."""

    available = media_probe.is_probe_available()
    root = library_roots.get(request.root_id)

    if root is None or not available:
        return MediaTechnicalResponse(available=available, found=False)

    path = Path(root.path).joinpath(
        *Path(request.video_source).parts
    )

    if not path.is_file():
        return MediaTechnicalResponse(available=True, found=False)

    info = media_probe.probe_video_file(path)
    if info is None:
        return MediaTechnicalResponse(available=True, found=False)

    return MediaTechnicalResponse(
        available=True,
        found=True,
        width=info.width,
        height=info.height,
        video_codec=info.video_codec,
        frame_rate=info.frame_rate,
        audio_codec=info.audio_codec,
        audio_channels=info.audio_channels,
        duration_seconds=info.duration_seconds,
        bit_rate=info.bit_rate,
        is_hdr=info.is_hdr,
        audio_language=info.audio_language,
    )


@router.patch(
    "/media/{item_id}/episodes/{episode_id}",
    response_model=SeriesEpisodeResponse,
)
def update_episode(
    item_id: int,
    episode_id: int,
    request: EpisodeUpdateRequest,
    episodes: EpisodeRepositoryDependency,
) -> SeriesEpisodeResponse:
    """Menja naslov / trajanje / status gledanja jedne epizode."""

    updated = episodes.update(
        episode_id,
        title=request.title,
        runtime_minutes=request.runtime_minutes,
        watch_status=(
            request.watch_status.value
            if request.watch_status is not None
            else None
        ),
    )

    if updated is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Epizoda {episode_id} ne postoji.",
        )

    return SeriesEpisodeResponse.from_domain(updated)


@router.delete(
    "/media/{item_id}/episodes/{episode_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_episode(
    item_id: int,
    episode_id: int,
    episodes: EpisodeRepositoryDependency,
) -> Response:
    """Briše jednu epizodu iz kataloga."""

    if not episodes.delete(episode_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Epizoda {episode_id} ne postoji.",
        )

    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ==========          FILMIUM ŽANROVI          ==========

@router.get(
    "/genres",
    response_model=list[str],
)
def list_active_genres(
    service: FilmiumServiceDependency,
) -> list[str]:
    """Vraća aktivne FILMIUM žanrove dostupne za izbor."""

    return list(service.list_active_genres())


# ==========          FILMIUM KATALOG          ==========

@router.post(
    "/media",
    response_model=MediaItemResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_media_item(
    request: MediaItemCreateRequest,
    service: FilmiumServiceDependency,
) -> MediaItemResponse:
    """Dodaje novi film ili seriju u FILMIUM katalog."""

    try:
        item = service.create_media_item(request.to_domain())
    except FilmiumValidationError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(error),
        ) from error

    return MediaItemResponse.from_domain(item)


@router.put(
    "/media/{item_id}",
    response_model=MediaItemResponse,
)
def update_media_item(
    item_id: int,
    request: MediaItemCreateRequest,
    service: FilmiumServiceDependency,
) -> MediaItemResponse:
    """Menja postojeći FILMIUM sadržaj."""

    try:
        item = service.update_media_item(
            item_id,
            request.to_domain(),
        )
    except FilmiumValidationError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(error),
        ) from error
    except MediaItemNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(error),
        ) from error

    return MediaItemResponse.from_domain(item)



class MediaKeywordsRequest(BaseModel):
    """Parcijalni update: samo ključne reči + editor_settings."""

    keywords: tuple[str, ...] = Field(default_factory=tuple, max_length=200)
    editor_settings: dict = Field(default_factory=dict)


@router.patch(
    "/media/{item_id}/keywords",
    response_model=MediaItemResponse,
)
def update_media_item_keywords(
    item_id: int,
    request: MediaKeywordsRequest,
    service: FilmiumServiceDependency,
) -> MediaItemResponse:
    """Menja samo ključne reči i editor_settings (bez diranja ostalih polja)."""

    try:
        item = service.update_keywords(
            item_id,
            request.keywords,
            request.editor_settings,
        )
    except MediaItemNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(error),
        ) from error

    return MediaItemResponse.from_domain(item)


@router.patch(
    "/media/{item_id}/favorite",
    response_model=MediaItemResponse,
)
def set_media_item_favorite_status(
    item_id: int,
    request: MediaItemFavoriteRequest,
    service: FilmiumServiceDependency,
) -> MediaItemResponse:
    """Menja samo favorite status FILMIUM sadržaja."""

    try:
        item = service.set_favorite_status(
            item_id,
            request.is_favorite,
        )
    except MediaItemNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(error),
        ) from error

    return MediaItemResponse.from_domain(item)

@router.delete(
    "/media/{item_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_media_item(
    item_id: int,
    service: FilmiumServiceDependency,
) -> Response:
    """Briše postojeći FILMIUM sadržaj."""

    try:
        service.delete_media_item(item_id)
    except MediaItemNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(error),
        ) from error

    return Response(status_code=status.HTTP_204_NO_CONTENT)

@router.get(
    "/media",
    response_model=list[MediaItemResponse],
)
def list_media_items(
    service: FilmiumServiceDependency,
) -> list[MediaItemResponse]:
    """Vraća sve filmove i serije iz FILMIUM kataloga."""

    return [
        MediaItemResponse.from_domain(item)
        for item in service.list_media_items()
    ]


@router.get(
    "/media/{item_id}",
    response_model=MediaItemResponse,
)
def get_media_item(
    item_id: int,
    service: FilmiumServiceDependency,
) -> MediaItemResponse:
    """Vraća jedan FILMIUM sadržaj po ID-u."""

    try:
        item = service.get_media_item(item_id)
    except MediaItemNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(error),
        ) from error

    return MediaItemResponse.from_domain(item)



# ==========          PRENOS (PREBACI)          ==========


# ==========          TEHNIČKI PODACI VIDEA          ==========

@router.get(
    "/media/{item_id}/technical",
    response_model=MediaTechnicalResponse,
)
def get_media_technical(
    item_id: int,
    media_sources: MediaSourceRepositoryDependency,
) -> MediaTechnicalResponse:
    """Vraća tehničke podatke glavnog video fajla preko ffprobe-a."""

    available = media_probe.is_probe_available()

    video_path: Path | None = None
    for source in media_sources.list_for_media(item_id):
        for file in source.files:
            if file.role.value == "video":
                video_path = (
                    Path(source.root_path_snapshot)
                    / source.relative_directory
                    / file.relative_path
                )
                break
        if video_path is not None:
            break

    if video_path is None or not available:
        return MediaTechnicalResponse(available=available, found=False)

    info = media_probe.probe_video_file(video_path)
    if info is None:
        return MediaTechnicalResponse(available=available, found=False)

    return MediaTechnicalResponse(
        available=True,
        found=True,
        width=info.width,
        height=info.height,
        video_codec=info.video_codec,
        frame_rate=info.frame_rate,
        audio_codec=info.audio_codec,
        audio_channels=info.audio_channels,
        duration_seconds=info.duration_seconds,
        bit_rate=info.bit_rate,
        is_hdr=info.is_hdr,
        audio_language=info.audio_language,
    )


# ==========          TMDB DOPUNA SADRŽAJA          ==========

def _persist_tmdb_visuals(
    visual_service: MediaVisualService,
    item: object,
    enrichment: object,
) -> None:
    """Preuzima i čuva TMDB poster/backdrop ako sadržaj još nema svoj."""

    targets = (
        (
            MediaAssetType.POSTER,
            getattr(item, "poster_path", None),
            getattr(enrichment, "poster_url", None),
        ),
        (
            MediaAssetType.BACKDROP,
            getattr(item, "backdrop_path", None),
            getattr(enrichment, "backdrop_url", None),
        ),
    )

    for asset_type, current_path, image_url in targets:
        if current_path or not image_url:
            continue
        content = tmdb_client.download_image(image_url)
        if not content:
            continue
        try:
            visual_service.save_media_asset(
                item_id=item.id,
                asset_type=asset_type,
                content=content,
            )
        except Exception:  # noqa: BLE001, S110
            # Vizuelni asseti su pomoćni; ne rušimo dopunu zbog njih.
            pass


@router.post(
    "/media/{item_id}/tmdb-enrich",
    response_model=MediaEnrichmentResponse,
)
def enrich_media_from_tmdb(
    item_id: int,
    service: FilmiumServiceDependency,
    visual_service: MediaVisualService = Depends(get_media_visual_service),
) -> MediaEnrichmentResponse:
    """Traži sadržaj na TMDB-u i vraća podatke za dopunu editora."""

    try:
        item = service.get_media_item(item_id)
    except MediaItemNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(error),
        ) from error

    if not tmdb_client.is_tmdb_available():
        return MediaEnrichmentResponse(available=False, matched=False)

    query_title = item.original_title or item.title
    enrichment = (
        tmdb_client.enrich_series(query_title, item.release_year)
        if item.media_type.value == "series"
        else tmdb_client.enrich_movie(query_title, item.release_year)
    )

    if enrichment is None:
        return MediaEnrichmentResponse(available=True, matched=False)

    # Backfill poster/backdrop za sadržaj koji ih još nema (npr. serije
    # uvezene pre nego što je uvoz počeo da ih čuva). Best-effort.
    _persist_tmdb_visuals(visual_service, item, enrichment)

    # SR: POSLE TMDB dopune, dopuni i iz spoljnih izvora (IMDb / Rotten Tomatoes
    #     / TVmaze / Jikan). Best-effort: greška ovde NE sme da obori zahtev.
    #     Piše u DB sa busy_timeout (živa ćelija, NTFS) i vraća ocene editoru
    #     kroz `external_ratings`. EN: after TMDB enrichment, also enrich from the
    #     external providers; best-effort, never fails the request; persists to
    #     the DB (busy_timeout) and returns ratings to the editor.
    external_ratings = None
    try:
        from core.domains.filmium.media_external import (
            apply_external_enrichment,
            open_connection,
        )

        _con = open_connection()
        try:
            _summary = apply_external_enrichment(_con, item_id)
            _con.commit()
        finally:
            _con.close()
        if _summary.get("ratings_external") or _summary.get("ratings_votes"):
            external_ratings = {
                "external": _summary.get("ratings_external") or {},
                "votes": _summary.get("ratings_votes") or {},
            }
    except Exception:  # noqa: BLE001
        external_ratings = None

    return MediaEnrichmentResponse(
        available=True,
        matched=True,
        tmdb_id=enrichment.tmdb_id,
        original_title=enrichment.original_title,
        english_title=enrichment.english_title,
        english_overview=enrichment.english_overview,
        local_title=enrichment.local_title,
        local_overview=enrichment.local_overview,
        year=enrichment.year,
        genres=enrichment.genres,
        rating=enrichment.rating,
        cast_names=enrichment.cast_names,
        studio=enrichment.studio,
        director=enrichment.director,
        vote_count=enrichment.vote_count,
        original_language=enrichment.original_language,
        country=enrichment.country,
        keywords=enrichment.keywords,
        collection=enrichment.collection,
        external_ratings=external_ratings,
    )


# ==========          AUTO UPDATE (UPDATUJ DUGME)          ==========

@router.post("/media/{item_id}/auto-update", response_model=AutoUpdateResponse)
def auto_update_media(
    item_id: int,
    service: FilmiumServiceDependency,
    request: AutoUpdateRequest | None = None,
) -> AutoUpdateResponse:
    """Kompletno dopuni jedan naslov iz TMDB-a (naslov/opis na latinici,
    ključne reči) i snimi u bazu. Vraća osveženi zapis."""

    from core.domains.filmium.auto_update_service import auto_update_item
    from integrations.translator.service import TranslatorService

    payload = request or AutoUpdateRequest()

    try:
        result = auto_update_item(
            item_id,
            service,
            TranslatorService(),
            tmdb_id=payload.tmdb_id,
            override_title=payload.override_title,
        )
    except MediaItemNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(error),
        ) from error

    item = service.get_media_item(item_id)
    return AutoUpdateResponse(
        matched=result.matched,
        changed_fields=result.changed_fields,
        message=result.message,
        item=MediaItemResponse.from_domain(item),
    )


# ==========          ASSET PARAMETRI          ==========


# ==========          POD-ROUTERI (izdvojeno radi veličine)          ==========

from apps.api.routers import filmium_assets, filmium_files

router.include_router(filmium_files.router)
router.include_router(filmium_assets.router)
