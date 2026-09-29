from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum

# ==========          TIP MEDIJSKOG SADRŽAJA          ==========

class MediaType(StrEnum):
    """Podržani tipovi sadržaja unutar FILMIUM kataloga."""

    MOVIE = "movie"
    SERIES = "series"


# ==========          STATUS GLEDANJA          ==========

class WatchStatus(StrEnum):
    """Podržani statusi gledanja FILMIUM sadržaja."""

    PLANNED = "planned"
    WATCHING = "watching"
    COMPLETED = "completed"
    PAUSED = "paused"
    DROPPED = "dropped"


# ==========          POVEZAN TMDB NASLOV          ==========

@dataclass(frozen=True)
class RelatedTitle:
    """Lagani zapis TMDB povezanog naslova (recommendations)."""

    tmdb_id: int
    title: str
    year: int | None
    poster_path: str | None
    media_type: MediaType


# ==========          NOVI MEDIJSKI SADRŽAJ          ==========

@dataclass(frozen=True)
class MediaItemCreate:
    """Podaci potrebni za dodavanje sadržaja u FILMIUM katalog."""

    title: str
    media_type: MediaType
    original_title: str | None = None
    english_title: str | None = None
    release_year: int | None = None
    runtime_minutes: int | None = None
    watch_status: WatchStatus = WatchStatus.PLANNED
    rating: int | None = None
    notes: str | None = None
    english_description: str | None = None
    content_category: str = "regular"
    cast_names: tuple[str, ...] = ()
    studio: str | None = None
    director: str | None = None
    keywords: tuple[str, ...] = ()
    collection: str | None = None
    is_synchronized: bool = False
    editor_settings: dict = field(default_factory=dict)
    tmdb_id: int | None = None

    genres: tuple[str, ...] = ()
    is_favorite: bool = False
    related_tmdb: tuple[RelatedTitle, ...] = ()


# ==========          MEDIJSKI SADRŽAJ          ==========

@dataclass(frozen=True)
class MediaItem:
    """Kompletan zapis jednog sadržaja iz FILMIUM kataloga."""

    id: int
    title: str
    media_type: MediaType
    original_title: str | None
    release_year: int | None
    watch_status: WatchStatus
    rating: int | None
    notes: str | None
    created_at: datetime
    updated_at: datetime
    genres: tuple[str, ...] = ()
    is_favorite: bool = False
    runtime_minutes: int | None = None
    poster_path: str | None = None
    backdrop_path: str | None = None
    english_title: str | None = None
    english_description: str | None = None
    content_category: str = "regular"
    cast_names: tuple[str, ...] = ()
    studio: str | None = None
    director: str | None = None
    keywords: tuple[str, ...] = ()
    collection: str | None = None
    is_synchronized: bool = False
    editor_settings: dict = field(default_factory=dict)
    tmdb_id: int | None = None
    related_tmdb: tuple[RelatedTitle, ...] = ()



# ==========          NOVA KOLEKCIJA          ==========

@dataclass(frozen=True)
class CollectionCreate:
    """Podaci potrebni za kreiranje FILMIUM kolekcije."""

    name: str
    description: str | None = None


# ==========          FILMIUM KOLEKCIJA          ==========

@dataclass(frozen=True)
class MediaCollection:
    """Predstavlja jednu organizovanu kolekciju FILMIUM sadržaja."""

    id: int
    name: str
    description: str | None
    item_ids: tuple[int, ...]
    created_at: datetime
    updated_at: datetime