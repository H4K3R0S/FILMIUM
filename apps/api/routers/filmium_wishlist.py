from typing import Annotated

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    UploadFile,
    status,
)

from apps.api.dependencies import (
    get_filmium_service,
    get_wishlist_asset_service,
    get_wishlist_service,
)
from apps.api.schemas.filmium_wishlist import (
    WishlistEntryCreateRequest,
    WishlistEntryResponse,
    WishlistReconcileResponse,
    WishlistRemovedEntry,
    WishlistTmdbImageRequest,
    WishlistTmdbPreviewRequest,
    WishlistTmdbPreviewResponse,
    WishlistTranslateRequest,
    WishlistTranslateResponse,
)
from core.domains.filmium import tmdb_client
from core.domains.filmium.service import FilmiumService
from core.domains.filmium.wishlist_asset_service import (
    ASSET_KIND_COLUMN,
    WishlistAssetService,
    WishlistAssetValidationError,
)
from core.domains.filmium.wishlist_models import CatalogMatchTarget
from core.domains.filmium.wishlist_service import (
    WishlistNotFoundError,
    WishlistService,
    WishlistValidationError,
)

# ==========          WISHLIST ROUTER          ==========

router = APIRouter(
    prefix="/api/v1/filmium/wishlist",
    tags=["FILMIUM Wishlist"],
)

WishlistServiceDependency = Annotated[
    WishlistService,
    Depends(get_wishlist_service),
]

WishlistAssetServiceDependency = Annotated[
    WishlistAssetService,
    Depends(get_wishlist_asset_service),
]

FilmiumServiceDependency = Annotated[
    FilmiumService,
    Depends(get_filmium_service),
]


# ==========          CRUD          ==========

@router.get("", response_model=list[WishlistEntryResponse])
def list_wishlist(
    service: WishlistServiceDependency,
) -> list[WishlistEntryResponse]:
    """Vraća sve naslove iz liste za preuzimanje (za Home red)."""

    return [
        WishlistEntryResponse.from_domain(entry)
        for entry in service.list_entries()
    ]


@router.post(
    "",
    response_model=WishlistEntryResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_wishlist_entry(
    request: WishlistEntryCreateRequest,
    service: WishlistServiceDependency,
) -> WishlistEntryResponse:
    """Dodaje novi naslov u listu za preuzimanje."""

    try:
        entry = service.create_entry(request.to_domain())
    except WishlistValidationError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(error),
        ) from error

    return WishlistEntryResponse.from_domain(entry)


@router.delete(
    "/{entry_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_wishlist_entry(
    entry_id: int,
    service: WishlistServiceDependency,
) -> None:
    """Briše naslov iz liste za preuzimanje."""

    try:
        service.delete_entry(entry_id)
    except WishlistNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(error),
        ) from error


# ==========          USKLAĐIVANJE SA BIBLIOTEKOM          ==========

@router.post("/reconcile", response_model=WishlistReconcileResponse)
def reconcile_wishlist(
    service: WishlistServiceDependency,
    filmium_service: FilmiumServiceDependency,
) -> WishlistReconcileResponse:
    """
    Uklanja iz liste za preuzeti naslove koji su u međuvremenu ušli u
    biblioteku (poklapanje po TMDB ID-u, ili po naslovu+godini za starije
    unose bez TMDB ID-a). Vraća uklonjene naslove radi obaveštenja.
    """

    catalog = [
        CatalogMatchTarget(
            tmdb_id=item.tmdb_id,
            titles=(
                item.title,
                item.original_title or "",
                item.english_title or "",
            ),
            release_year=item.release_year,
        )
        for item in filmium_service.list_media_items()
    ]

    removed = service.reconcile_against_catalog(catalog)

    return WishlistReconcileResponse(
        removed=[
            WishlistRemovedEntry(id=entry.id, title=entry.title)
            for entry in removed
        ]
    )


# ==========          ASSETI (SLIKE + TITLOVI)          ==========

@router.post(
    "/{entry_id}/asset",
    response_model=WishlistEntryResponse,
)
async def upload_wishlist_asset(
    entry_id: int,
    service: WishlistServiceDependency,
    asset_service: WishlistAssetServiceDependency,
    kind: str = Form(...),
    file: UploadFile = File(...),
) -> WishlistEntryResponse:
    """
    Čuva jednu datoteku (poster/backdrop/wallpaper/prevod/extra) i beleži
    njenu putanju na stavci liste za preuzimanje.
    """

    # Provera da stavka postoji (i za 404 poruku).
    try:
        service.get_entry(entry_id)
    except WishlistNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(error),
        ) from error

    try:
        content = await file.read()
        relative_path = asset_service.save(
            entry_id=entry_id,
            kind=kind,
            filename=file.filename or "",
            content=content,
        )
    except WishlistAssetValidationError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(error),
        ) from error
    finally:
        await file.close()

    if kind == "extra":
        entry = service.append_extra_asset(entry_id, relative_path)
    else:
        entry = service.set_asset_path(
            entry_id,
            ASSET_KIND_COLUMN[kind],
            relative_path,
        )

    return WishlistEntryResponse.from_domain(entry)


# ==========          TMDB SLIKA (SERVER PREUZIMA)          ==========

@router.post(
    "/{entry_id}/tmdb-image",
    response_model=WishlistEntryResponse,
)
def save_wishlist_tmdb_image(
    entry_id: int,
    request: WishlistTmdbImageRequest,
    service: WishlistServiceDependency,
    asset_service: WishlistAssetServiceDependency,
) -> WishlistEntryResponse:
    """
    Preuzima TMDB sliku (poster ili backdrop) na serveru i beleži je uz
    stavku. Time se zaobilazi CORS pri klijentskom preuzimanju slike.
    """

    if request.kind not in ("poster", "backdrop"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Vrsta TMDB slike mora biti 'poster' ili 'backdrop'.",
        )

    try:
        service.get_entry(entry_id)
    except WishlistNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(error),
        ) from error

    content = tmdb_client.download_image(request.url)
    if not content:
        # Slika je pomoćna — vrati postojeću stavku bez greške.
        return WishlistEntryResponse.from_domain(service.get_entry(entry_id))

    extension = request.url.rsplit(".", 1)[-1].lower()
    if extension not in ("jpg", "jpeg", "png", "webp"):
        extension = "jpg"
    filename = f"{request.kind}.{extension}"

    try:
        relative_path = asset_service.save(
            entry_id=entry_id,
            kind=request.kind,
            filename=filename,
            content=content,
        )
    except WishlistAssetValidationError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(error),
        ) from error

    entry = service.set_asset_path(
        entry_id,
        ASSET_KIND_COLUMN[request.kind],
        relative_path,
    )

    return WishlistEntryResponse.from_domain(entry)


# ==========          TMDB PRETRAGA (POPUNA FORME)          ==========

@router.post(
    "/tmdb-preview",
    response_model=WishlistTmdbPreviewResponse,
)
def wishlist_tmdb_preview(
    request: WishlistTmdbPreviewRequest,
) -> WishlistTmdbPreviewResponse:
    """
    Traži naslov na TMDB-u (ime + godina) i vraća podatke za popunu forme.
    Ništa se ne čuva u bazu — samo pomoć pri unosu.
    """

    if not tmdb_client.is_tmdb_available():
        return WishlistTmdbPreviewResponse(available=False, matched=False)

    enrichment = (
        tmdb_client.enrich_series(request.title, request.year)
        if request.media_type == "series"
        else tmdb_client.enrich_movie(request.title, request.year)
    )

    if enrichment is None:
        return WishlistTmdbPreviewResponse(available=True, matched=False)

    return WishlistTmdbPreviewResponse(
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
        poster_url=enrichment.poster_url,
        backdrop_url=enrichment.backdrop_url,
    )


# ==========          PREVOD (EN → BOSANSKI)          ==========

@router.post("/translate", response_model=WishlistTranslateResponse)
def wishlist_translate(
    request: WishlistTranslateRequest,
) -> WishlistTranslateResponse:
    """Prevede naslov + opis na domaći (bosanski) preko TranslatorService-a.

    Koristi engleski izvor. Na grešku prevodioca vraća ``available=False``
    umesto da ruši formu.
    """

    from integrations.translator.base import TranslationError
    from integrations.translator.service import TranslatorService

    if not request.title.strip() and not request.overview.strip():
        return WishlistTranslateResponse(available=True, title="", overview="")

    try:
        translated_title, translated_overview = TranslatorService().translate_pair(
            request.title,
            request.overview,
            target="bs",
        )
    except TranslationError:
        return WishlistTranslateResponse(available=False)

    return WishlistTranslateResponse(
        available=True,
        title=translated_title,
        overview=translated_overview,
    )
