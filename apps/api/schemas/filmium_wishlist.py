from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from core.domains.filmium.wishlist_models import (
    WishlistEntry,
    WishlistEntryCreate,
)

MediaTypeLiteral = Literal["movie", "series"]
CategoryLiteral = Literal["regular", "domestic", "animated"]


# ==========          ZAHTEV ZA KREIRANJE          ==========

class WishlistEntryCreateRequest(BaseModel):
    """Validira zahtev za dodavanje naslova u listu za preuzimanje."""

    title: str = Field(min_length=1, max_length=300)
    release_year: int | None = Field(default=None, ge=1888, le=9999)
    media_type: MediaTypeLiteral = "movie"
    content_category: CategoryLiteral = "regular"
    is_subtitled: bool = False
    is_synchronized: bool = False
    tmdb_id: int | None = None
    english_overview: str | None = Field(default=None, max_length=10_000)
    local_overview: str | None = Field(default=None, max_length=10_000)
    original_title: str | None = Field(default=None, max_length=300)
    local_title: str | None = Field(default=None, max_length=300)

    def to_domain(self) -> WishlistEntryCreate:
        """Pretvara API zahtev u domenski model."""

        return WishlistEntryCreate(
            title=self.title,
            release_year=self.release_year,
            media_type=self.media_type,
            content_category=self.content_category,
            is_subtitled=self.is_subtitled,
            is_synchronized=self.is_synchronized,
            tmdb_id=self.tmdb_id,
            english_overview=self.english_overview,
            local_overview=self.local_overview,
            original_title=self.original_title,
            local_title=self.local_title,
        )


# ==========          ODGOVOR SA STAVKOM          ==========

class WishlistEntryResponse(BaseModel):
    """Jedan naslov iz liste za preuzimanje."""

    id: int
    title: str
    release_year: int | None
    media_type: str
    content_category: str
    is_subtitled: bool
    is_synchronized: bool
    tmdb_id: int | None
    english_overview: str | None
    local_overview: str | None
    original_title: str | None
    local_title: str | None
    poster_path: str | None
    backdrop_path: str | None
    wallpaper_path: str | None
    original_subtitle_path: str | None
    domestic_subtitle_path: str | None
    english_subtitle_path: str | None
    extra_assets: tuple[str, ...]
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_domain(cls, entry: WishlistEntry) -> "WishlistEntryResponse":
        """Pravi odgovor iz domenske stavke."""

        return cls(
            id=entry.id,
            title=entry.title,
            release_year=entry.release_year,
            media_type=entry.media_type,
            content_category=entry.content_category,
            is_subtitled=entry.is_subtitled,
            is_synchronized=entry.is_synchronized,
            tmdb_id=entry.tmdb_id,
            english_overview=entry.english_overview,
            local_overview=entry.local_overview,
            original_title=entry.original_title,
            local_title=entry.local_title,
            poster_path=entry.poster_path,
            backdrop_path=entry.backdrop_path,
            wallpaper_path=entry.wallpaper_path,
            original_subtitle_path=entry.original_subtitle_path,
            domestic_subtitle_path=entry.domestic_subtitle_path,
            english_subtitle_path=entry.english_subtitle_path,
            extra_assets=entry.extra_assets,
            created_at=entry.created_at,
            updated_at=entry.updated_at,
        )


# ==========          TMDB PRETRAGA (BEZ UPISA)          ==========

class WishlistTmdbPreviewRequest(BaseModel):
    """Zahtev za TMDB pretragu prilikom popunjavanja forme."""

    title: str = Field(min_length=1, max_length=300)
    year: int | None = Field(default=None, ge=1888, le=9999)
    media_type: MediaTypeLiteral = "movie"


class WishlistRemovedEntry(BaseModel):
    """Naslov uklonjen iz liste jer je ušao u biblioteku."""

    id: int
    title: str


class WishlistReconcileResponse(BaseModel):
    """Rezultat usklađivanja liste za preuzeti sa bibliotekom."""

    removed: list[WishlistRemovedEntry] = []


class WishlistTranslateRequest(BaseModel):
    """Zahtev za prevod naslova + opisa (EN → domaći, default bosanski)."""

    title: str = Field(default="", max_length=300)
    overview: str = Field(default="", max_length=10_000)


class WishlistTranslateResponse(BaseModel):
    """Prevedeni naslov + opis. ``available`` je False ako prevod ne radi."""

    available: bool
    title: str = ""
    overview: str = ""


class WishlistTmdbImageRequest(BaseModel):
    """Zahtev da server preuzme TMDB sliku i sačuva je uz stavku."""

    kind: Literal["poster", "backdrop"]
    url: str = Field(min_length=1, max_length=1000)


class WishlistTmdbPreviewResponse(BaseModel):
    """Podaci nađeni na TMDB-u za popunu forme (ništa se ne čuva)."""

    available: bool
    matched: bool
    tmdb_id: int | None = None
    original_title: str | None = None
    english_title: str | None = None
    english_overview: str | None = None
    local_title: str | None = None
    local_overview: str | None = None
    year: int | None = None
    genres: tuple[str, ...] = ()
    rating: float | None = None
    poster_url: str | None = None
    backdrop_url: str | None = None
