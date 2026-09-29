from dataclasses import dataclass
from datetime import datetime

from core.domains.filmium.models import WatchStatus

# ==========          SEZONA          ==========

@dataclass(frozen=True)
class SeasonCreate:
    """Podaci potrebni za dodavanje jedne sezone serije."""

    media_id: int
    season_number: int
    name: str | None = None


@dataclass(frozen=True)
class Season:
    """Sačuvana sezona jedne serije."""

    id: int
    media_id: int
    season_number: int
    name: str | None
    created_at: datetime
    updated_at: datetime
    poster_path: str | None = None
    backdrop_path: str | None = None


# ==========          EPIZODA          ==========

@dataclass(frozen=True)
class EpisodeCreate:
    """Podaci potrebni za dodavanje jedne epizode."""

    season_id: int
    episode_number: int
    title: str | None = None
    runtime_minutes: int | None = None
    watch_status: WatchStatus = WatchStatus.PLANNED


@dataclass(frozen=True)
class Episode:
    """Sačuvana epizoda jedne sezone."""

    id: int
    season_id: int
    episode_number: int
    title: str | None
    runtime_minutes: int | None
    watch_status: WatchStatus
    created_at: datetime
    updated_at: datetime
