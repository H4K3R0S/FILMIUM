from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

from core.domains.filmium.library_import_models import MediaTechnicalInfo
from core.domains.filmium.series_import_service import (
    SeriesImportResult,
)
from core.domains.filmium.series_scanner import (
    EpisodeScan,
    SeasonScan,
    SeriesScanResult,
)
from core.domains.filmium.tmdb_client import TmdbEpisode, TmdbSeries


def _relative_to_root(path: Path, root_path: Path | None) -> str:
    """Putanja videa relativna na koren biblioteke (za probe/thumbnail)."""

    if root_path is None:
        return path.name
    try:
        return path.resolve(strict=False).relative_to(
            root_path.resolve(strict=False)
        ).as_posix()
    except ValueError:
        return path.name


# ==========          ZAHTEVI          ==========

class SeriesPreviewRequest(BaseModel):
    relative_directory: str = Field(min_length=1)


class SeriesImportRequest(BaseModel):
    relative_directory: str = Field(min_length=1)
    confirmed: bool = False
    target_library_root_id: int | None = Field(default=None, gt=0)
    # Togle tipa sadržaja: regular / animated (Animirano/Serije) /
    # domestic (Domaci/Serije).
    content_mode: Literal["regular", "animated", "domestic"] = "regular"
    # Da li je serija sinhronizovana (True = SINH, False = titlovana).
    synchronized: bool = False


# ==========          PREGLED SERIJE          ==========

class SeriesEpisodeResponse(BaseModel):
    season_number: int
    episode_number: int
    title: str | None
    video: str
    source: str
    subtitles: list[str]

    @classmethod
    def from_domain(
        cls,
        episode: EpisodeScan,
        root_path: Path | None = None,
    ) -> "SeriesEpisodeResponse":
        return cls(
            season_number=episode.season_number,
            episode_number=episode.episode_number,
            title=episode.title,
            video=episode.video_path.name,
            source=_relative_to_root(episode.video_path, root_path),
            subtitles=[
                subtitle.language or "und"
                for subtitle in episode.subtitles
            ],
        )


class SeriesSeasonResponse(BaseModel):
    season_number: int
    episodes: list[SeriesEpisodeResponse]

    @classmethod
    def from_domain(
        cls,
        season: SeasonScan,
        root_path: Path | None = None,
    ) -> "SeriesSeasonResponse":
        return cls(
            season_number=season.season_number,
            episodes=[
                SeriesEpisodeResponse.from_domain(episode, root_path)
                for episode in season.episodes
            ],
        )


def _relative_artwork(scan: SeriesScanResult, path) -> str | None:
    if path is None:
        return None

    try:
        return path.relative_to(scan.directory).as_posix()
    except ValueError:
        return None


class SeriesArtworkResponse(BaseModel):
    kind: str
    season: int | None
    file: str


class SeriesScanResponse(BaseModel):
    title: str
    relative_directory: str
    poster: str | None
    backdrop: str | None
    seasons: list[SeriesSeasonResponse]
    warnings: list[str]
    artwork: list[SeriesArtworkResponse]
    extras: list[str]

    @classmethod
    def from_domain(
        cls,
        scan: SeriesScanResult,
        relative_directory: str = ".",
        root_path: Path | None = None,
    ) -> "SeriesScanResponse":
        artwork: list[SeriesArtworkResponse] = []
        for ref in scan.artwork:
            relative = _relative_artwork(scan, ref.path)
            if relative is None:
                continue
            artwork.append(
                SeriesArtworkResponse(
                    kind=ref.kind,
                    season=ref.season,
                    file=relative,
                )
            )

        return cls(
            title=scan.title,
            relative_directory=relative_directory,
            poster=_relative_artwork(scan, scan.poster_path),
            backdrop=_relative_artwork(scan, scan.backdrop_path),
            seasons=[
                SeriesSeasonResponse.from_domain(season, root_path)
                for season in scan.seasons
            ],
            warnings=list(scan.warnings),
            artwork=artwork,
            extras=[entry.name for entry in scan.extras],
        )


class SeriesLibraryScanResponse(BaseModel):
    """Rezultat skeniranja foldera koji može sadržati više serija."""

    series: list[SeriesScanResponse]

    @classmethod
    def from_domain(
        cls,
        scans: list[tuple[str, SeriesScanResult]],
        root_path: Path | None = None,
    ) -> "SeriesLibraryScanResponse":
        return cls(
            series=[
                SeriesScanResponse.from_domain(
                    scan,
                    relative_directory,
                    root_path,
                )
                for relative_directory, scan in scans
            ]
        )


# ==========          MEDIA-PROBE (ffprobe)          ==========

class SeriesProbeRequest(BaseModel):
    source: str = Field(min_length=1)


class RevealPathRequest(BaseModel):
    relative_path: str = Field(min_length=1)


class RevealPathResponse(BaseModel):
    revealed: bool


class ReplaceFileRequest(BaseModel):
    relative_path: str = Field(min_length=1)
    source_path: str = Field(min_length=1)


class ReplaceFileResponse(BaseModel):
    replaced: bool


class SeriesProbeResponse(BaseModel):
    width: int | None
    height: int | None
    video_codec: str | None
    frame_rate: float | None
    audio_codec: str | None
    audio_channels: int | None
    duration_seconds: float | None
    available: bool

    @classmethod
    def from_domain(
        cls,
        info: MediaTechnicalInfo | None,
    ) -> "SeriesProbeResponse":
        if info is None:
            return cls(
                width=None,
                height=None,
                video_codec=None,
                frame_rate=None,
                audio_codec=None,
                audio_channels=None,
                duration_seconds=None,
                available=False,
            )
        return cls(
            width=info.width,
            height=info.height,
            video_codec=info.video_codec,
            frame_rate=info.frame_rate,
            audio_codec=info.audio_codec,
            audio_channels=info.audio_channels,
            duration_seconds=info.duration_seconds,
            available=True,
        )


# ==========          TMDB OBOGAĆIVANJE          ==========

class SeriesTmdbMatchRequest(BaseModel):
    title: str = Field(min_length=1)
    year: int | None = Field(default=None)


class SeriesTmdbResponse(BaseModel):
    matched: bool
    configured: bool
    tmdb_id: int | None
    name: str | None
    year: int | None
    genres: list[str]
    overview: str | None
    rating: float | None
    poster_url: str | None
    backdrop_url: str | None
    season_count: int | None

    @classmethod
    def from_domain(
        cls,
        series: TmdbSeries | None,
        configured: bool,
    ) -> "SeriesTmdbResponse":
        if series is None:
            return cls(
                matched=False,
                configured=configured,
                tmdb_id=None,
                name=None,
                year=None,
                genres=[],
                overview=None,
                rating=None,
                poster_url=None,
                backdrop_url=None,
                season_count=None,
            )
        return cls(
            matched=True,
            configured=configured,
            tmdb_id=series.tmdb_id,
            name=series.name,
            year=series.year,
            genres=list(series.genres),
            overview=series.overview,
            rating=series.rating,
            poster_url=series.poster_url,
            backdrop_url=series.backdrop_url,
            season_count=series.season_count,
        )


class SeriesTmdbSeasonRequest(BaseModel):
    tmdb_id: int = Field(gt=0)
    season_number: int = Field(ge=0)


class SeriesTmdbEpisodeResponse(BaseModel):
    episode_number: int
    name: str | None
    overview: str | None
    air_date: str | None
    rating: float | None
    still_url: str | None

    @classmethod
    def from_domain(
        cls,
        episode: TmdbEpisode,
    ) -> "SeriesTmdbEpisodeResponse":
        return cls(
            episode_number=episode.episode_number,
            name=episode.name,
            overview=episode.overview,
            air_date=episode.air_date,
            rating=episode.rating,
            still_url=episode.still_url,
        )


class SeriesTmdbSeasonResponse(BaseModel):
    episodes: list[SeriesTmdbEpisodeResponse]

    @classmethod
    def from_domain(
        cls,
        episodes: list[TmdbEpisode],
    ) -> "SeriesTmdbSeasonResponse":
        return cls(
            episodes=[
                SeriesTmdbEpisodeResponse.from_domain(episode)
                for episode in episodes
            ]
        )


# ==========          REZULTAT UVOZA          ==========

class SeriesImportResponse(BaseModel):
    media_id: int
    series_title: str
    target_directory: str
    season_count: int
    episode_count: int
    created_media: bool

    @classmethod
    def from_domain(
        cls,
        result: SeriesImportResult,
    ) -> "SeriesImportResponse":
        return cls(
            media_id=result.media_id,
            series_title=result.series_title,
            target_directory=result.target_directory,
            season_count=result.season_count,
            episode_count=result.episode_count,
            created_media=result.created_media,
        )
