"""TMDB modeli (dataklase) — izdvojeno iz tmdb_client radi veličine fajla."""

from dataclasses import dataclass


@dataclass(frozen=True)
class TmdbSeries:
    tmdb_id: int
    name: str
    original_name: str | None
    year: int | None
    genres: tuple[str, ...]
    overview: str | None
    rating: float | None
    poster_url: str | None
    backdrop_url: str | None
    season_count: int | None


@dataclass(frozen=True)
class TmdbEpisode:
    episode_number: int
    name: str | None
    overview: str | None
    air_date: str | None
    rating: float | None
    still_url: str | None


@dataclass(frozen=True)
class TmdbEpisodeMeta:
    """Epizoda sa opisom na engleskom i lokalnom jeziku (sr→hr→bs)."""

    episode_number: int
    name: str | None
    overview_en: str | None
    overview_local: str | None
    air_date: str | None
    rating: float | None
    still_url: str | None


@dataclass(frozen=True)
class TmdbSeason:
    """Sezona sa TMDB-a: naziv sezone + njene epizode."""

    season_number: int
    name: str | None
    episodes: tuple[TmdbEpisode, ...]


@dataclass(frozen=True)
class TmdbMovie:
    tmdb_id: int
    title: str
    original_title: str | None
    year: int | None
    genres: tuple[str, ...]
    overview: str | None
    rating: float | None
    poster_url: str | None
    backdrop_url: str | None


@dataclass(frozen=True)
class MediaTitleEnrichment:
    """Naslovi/opisi sa TMDB-a u tri varijante (izvorni/engleski/lokalni)."""

    tmdb_id: int
    original_title: str | None
    english_title: str | None
    english_overview: str | None
    local_title: str | None
    local_overview: str | None
    year: int | None
    genres: tuple[str, ...]
    rating: float | None
    poster_url: str | None
    backdrop_url: str | None
    cast_names: tuple[str, ...] = ()
    studio: str | None = None
    director: str | None = None
    vote_count: int | None = None
    original_language: str | None = None
    country: str | None = None
    keywords: tuple[str, ...] = ()
    collection: str | None = None
    recommendations: tuple = ()


# ==========          KLJUČ / KONFIGURACIJA          ==========

@dataclass(frozen=True)
class TmdbCredentials:
    access_token: str | None
    api_key: str | None

    @property
    def is_configured(self) -> bool:
        return bool(self.access_token or self.api_key)
