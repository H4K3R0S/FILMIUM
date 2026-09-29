from dataclasses import dataclass
from datetime import datetime

# ==========          PODACI ZA KREIRANJE „ZA PREUZETI"          ==========

@dataclass(frozen=True)
class WishlistEntryCreate:
    """Podaci potrebni za dodavanje naslova u listu za preuzimanje."""

    title: str
    release_year: int | None = None
    media_type: str = "movie"
    content_category: str = "regular"
    is_subtitled: bool = False
    is_synchronized: bool = False
    tmdb_id: int | None = None
    english_overview: str | None = None
    local_overview: str | None = None
    original_title: str | None = None
    local_title: str | None = None


# ==========          STAVKA LISTE „ZA PREUZETI"          ==========

@dataclass(frozen=True)
class CatalogMatchTarget:
    """Minimalni opis stavke kataloga za poređenje sa listom za preuzeti."""

    tmdb_id: int | None
    titles: tuple[str, ...]
    release_year: int | None


@dataclass(frozen=True)
class WishlistEntry:
    """Predstavlja jedan naslov koji korisnik planira da nabavi."""

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
