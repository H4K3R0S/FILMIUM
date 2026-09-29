from datetime import datetime

from pydantic import BaseModel, Field

from core.domains.filmium.models import (
    MediaItem,
    MediaItemCreate,
    MediaType,
    WatchStatus,
)
from core.domains.filmium.series_models import Episode, Season

# ==========          SEZONE I EPIZODE (DETALJI SERIJE)          ==========

class SeriesEpisodeResponse(BaseModel):
    id: int
    episode_number: int
    title: str | None
    runtime_minutes: int | None
    watch_status: WatchStatus
    # Za sličicu epizode: root_id + putanja video fajla (relativno korenu).
    root_id: int | None = None
    video_source: str | None = None

    @classmethod
    def from_domain(
        cls,
        item: Episode,
        root_id: int | None = None,
        video_source: str | None = None,
    ) -> "SeriesEpisodeResponse":
        return cls(
            id=item.id,
            episode_number=item.episode_number,
            title=item.title,
            runtime_minutes=item.runtime_minutes,
            watch_status=item.watch_status,
            root_id=root_id,
            video_source=video_source,
        )


class EpisodeMetadataResponse(BaseModel):
    """TMDB metapodaci jedne epizode (engleski + lokalni opis)."""

    episode_number: int
    name: str | None = None
    overview_en: str | None = None
    overview_local: str | None = None
    air_date: str | None = None
    rating: float | None = None
    still_url: str | None = None


class EpisodeUpdateRequest(BaseModel):
    """Parcijalna izmena jedne epizode."""

    title: str | None = None
    runtime_minutes: int | None = None
    watch_status: WatchStatus | None = None


class SeriesSeasonResponse(BaseModel):
    id: int
    season_number: int
    name: str | None
    poster_path: str | None = None
    backdrop_path: str | None = None
    episodes: list[SeriesEpisodeResponse]

    @classmethod
    def from_domain(
        cls,
        season: Season,
        episodes: tuple[Episode, ...],
    ) -> "SeriesSeasonResponse":
        return cls(
            id=season.id,
            season_number=season.season_number,
            name=season.name,
            poster_path=getattr(season, "poster_path", None),
            backdrop_path=getattr(season, "backdrop_path", None),
            episodes=[
                SeriesEpisodeResponse.from_domain(episode)
                for episode in episodes
            ],
        )


# ==========          PRENOS (PREBACI)          ==========

class DiskResponse(BaseModel):
    """Dostupan disk/particija za prenos."""

    path: str
    label: str
    total_bytes: int
    free_bytes: int


class DirectoryEntryResponse(BaseModel):
    """Jedan pod-folder pri navigaciji odredišta."""

    name: str
    path: str


class BrowseResponse(BaseModel):
    """Rezultat navigacije foldera (roditelj + pod-folderi)."""

    path: str | None = None
    parent: str | None = None
    directories: list[DirectoryEntryResponse] = Field(default_factory=list)


class MediaFileTreeItemResponse(BaseModel):
    """Jedan fajl sadržaja za stablo izbora pri prenosu."""

    relative_path: str
    role: str
    size_bytes: int


class MediaTransferRequest(BaseModel):
    """Zahtev za kopiranje sadržaja na odredište."""

    destination: str = Field(min_length=1)
    # Prazna lista = ceo direktorijum (svi fajlovi).
    relative_paths: list[str] = Field(default_factory=list)


class MediaTransferResponse(BaseModel):
    """Rezultat kopiranja."""

    copied_files: int
    total_bytes: int
    destination: str


# ==========          TMDB DOPUNA          ==========

class MediaEnrichmentResponse(BaseModel):
    """Podaci sa TMDB-a za dopunu editora sadržaja."""

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
    cast_names: tuple[str, ...] = ()
    studio: str | None = None
    director: str | None = None
    vote_count: int | None = None
    original_language: str | None = None
    country: str | None = None
    keywords: tuple[str, ...] = ()
    collection: str | None = None
    # SR: spoljne ocene (IMDb / Rotten Tomatoes / TVmaze / MAL) koje TMDB nema —
    # popunio ih je media_external.apply_external_enrichment posle TMDB dopune.
    # Oblik: {"external": {<labela>: {...}}, "votes": {<labela>: <int>}}.
    # EN: external ratings TMDB lacks, filled after TMDB enrichment. Shape:
    # {"external": {<label>: {...}}, "votes": {<label>: <int>}}. None if none.
    external_ratings: dict | None = None


# ==========          TEHNIČKI PODACI VIDEA (ffprobe)          ==========

class MediaTechnicalResponse(BaseModel):
    """Tehnički podaci glavnog video fajla iz ffprobe-a."""

    available: bool
    found: bool
    width: int | None = None
    height: int | None = None
    video_codec: str | None = None
    frame_rate: float | None = None
    audio_codec: str | None = None
    audio_channels: int | None = None
    duration_seconds: float | None = None
    bit_rate: int | None = None
    is_hdr: bool = False
    audio_language: str | None = None


# ==========          FILMIUM API ZAHTEV          ==========

class MediaItemCreateRequest(BaseModel):
    """Validira API zahtev za dodavanje ili izmenu FILMIUM sadržaja."""

    title: str = Field(min_length=1, max_length=300)
    media_type: MediaType

    original_title: str | None = Field(
        default=None,
        max_length=300,
    )

    release_year: int | None = Field(
        default=None,
        ge=1888,
        le=9999,
    )

    runtime_minutes: int | None = Field(
    default=None,
    ge=1,
    le=10_000,
    )

    watch_status: WatchStatus = WatchStatus.PLANNED

    rating: int | None = Field(
        default=None,
        ge=1,
        le=10,
    )

    notes: str | None = Field(
        default=None,
        max_length=10_000,
    )

    genres: tuple[str, ...] = Field(
        default_factory=tuple,
        max_length=20,
    )

    is_favorite: bool = False

    english_title: str | None = Field(
        default=None,
        max_length=300,
    )

    english_description: str | None = Field(
        default=None,
        max_length=10_000,
    )

    content_category: str = "regular"

    cast_names: tuple[str, ...] = Field(
        default_factory=tuple,
        max_length=50,
    )

    studio: str | None = Field(default=None, max_length=200)

    director: str | None = Field(default=None, max_length=200)

    keywords: tuple[str, ...] = Field(
        default_factory=tuple,
        max_length=200,
    )

    collection: str | None = Field(default=None, max_length=200)

    is_synchronized: bool = False

    editor_settings: dict = Field(default_factory=dict)

    tmdb_id: int | None = None

    def to_domain(self) -> MediaItemCreate:
        """Pretvara API zahtev u FILMIUM domenski model."""

        return MediaItemCreate(
            title=self.title,
            media_type=self.media_type,
            original_title=self.original_title,
            release_year=self.release_year,
            runtime_minutes=self.runtime_minutes,
            watch_status=self.watch_status,
            rating=self.rating,
            notes=self.notes,
            genres=self.genres,
            is_favorite=self.is_favorite,
            english_title=self.english_title,
            english_description=self.english_description,
            content_category=self.content_category,
            cast_names=self.cast_names,
            studio=self.studio,
            director=self.director,
            keywords=self.keywords,
            collection=self.collection,
            is_synchronized=self.is_synchronized,
            editor_settings=self.editor_settings,
            tmdb_id=self.tmdb_id,
        )



# ==========          FILMIUM FAVORITE ZAHTEV          ==========

class MediaItemFavoriteRequest(BaseModel):
    """Validira zahtev za promenu favorite statusa."""

    is_favorite: bool

    

# ==========          FILMIUM API ODGOVOR          ==========

class RelatedTitleSchema(BaseModel):
    """Lagani TMDB povezan naslov (recommendations) za GUI."""

    tmdb_id: int
    title: str
    year: int | None = None
    poster_path: str | None = None
    media_type: str


class MediaItemResponse(BaseModel):
    """Predstavlja FILMIUM sadržaj koji API vraća GUI-ju."""

    id: int
    title: str
    media_type: MediaType
    original_title: str | None
    english_title: str | None = None
    release_year: int | None
    runtime_minutes: int | None
    watch_status: WatchStatus
    rating: int | None
    notes: str | None
    english_description: str | None = None
    created_at: datetime
    updated_at: datetime
    genres: tuple[str, ...]
    poster_path: str | None
    backdrop_path: str | None
    is_favorite: bool
    content_category: str = "regular"
    cast_names: tuple[str, ...] = ()
    studio: str | None = None
    director: str | None = None
    keywords: tuple[str, ...] = ()
    collection: str | None = None
    is_synchronized: bool = False
    editor_settings: dict = Field(default_factory=dict)
    tmdb_id: int | None = None
    related_tmdb: list[RelatedTitleSchema] = Field(default_factory=list)

    @classmethod
    def from_domain(
        cls,
        item: MediaItem,
    ) -> "MediaItemResponse":
        """Pretvara FILMIUM domenski model u API odgovor."""

        return cls(
            id=item.id,
            title=item.title,
            media_type=item.media_type,
            original_title=item.original_title,
            english_title=item.english_title,
            release_year=item.release_year,
            runtime_minutes=item.runtime_minutes,
            watch_status=item.watch_status,
            rating=item.rating,
            notes=item.notes,
            created_at=item.created_at,
            updated_at=item.updated_at,
            english_description=item.english_description,
            genres=item.genres,
            is_favorite=item.is_favorite,
            poster_path=item.poster_path,
            backdrop_path=item.backdrop_path,
            content_category=item.content_category,
            cast_names=item.cast_names,
            studio=item.studio,
            director=item.director,
            keywords=item.keywords,
            collection=item.collection,
            is_synchronized=item.is_synchronized,
            editor_settings=item.editor_settings,
            tmdb_id=item.tmdb_id,
            related_tmdb=[
                RelatedTitleSchema(
                    tmdb_id=related.tmdb_id,
                    title=related.title,
                    year=related.year,
                    poster_path=related.poster_path,
                    media_type=related.media_type.value,
                )
                for related in item.related_tmdb
            ],
        )

# ==========          AUTO UPDATE (UPDATUJ DUGME)          ==========

class AutoUpdateRequest(BaseModel):
    """Opcioni ručni override za TMDB pretragu kada automatika promaši."""

    tmdb_id: int | None = None
    override_title: str | None = Field(default=None, max_length=300)


class AutoUpdateResponse(BaseModel):
    """Rezultat auto-update-a jednog naslova + osveženi zapis."""

    matched: bool
    changed_fields: tuple[str, ...] = ()
    message: str
    item: MediaItemResponse
