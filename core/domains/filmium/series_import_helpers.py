"""Series import: enrichment + file/thumb/mode helperi — izdvojeno radi veličine."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from core.domains.filmium import tmdb_client
from core.domains.filmium.library_category import (
    infer_content_mode_from_parts,
)
from core.domains.filmium.library_manifest import FILMIUM_INFO_FILE_NAME
from core.domains.filmium.media_finders import (
    find_subtitle_files,
    subtitle_language,
)
from core.domains.filmium.media_source_models import (
    MediaFileCreate,
    MediaFileRole,
    MediaSourceCreate,
)
from core.domains.filmium.series_scanner import SeriesScanResult


@dataclass(frozen=True)
class SeriesEnrichment:
    """Lokalizovana imena sa TMDB-a, spojena preko lokalnog skena."""

    overview: str | None = None
    genres: tuple[str, ...] = ()
    year: int | None = None
    # {broj_sezone: (ime_sezone, {broj_epizode: naslov})}
    seasons: dict[int, tuple[str | None, dict[int, str]]] = field(
        default_factory=dict
    )

    def season_name(self, season_number: int) -> str | None:
        entry = self.seasons.get(season_number)
        return entry[0] if entry else None

    def episode_title(
        self, season_number: int, episode_number: int
    ) -> str | None:
        entry = self.seasons.get(season_number)
        if not entry:
            return None
        return entry[1].get(episode_number)


def fetch_series_enrichment(scan: SeriesScanResult) -> SeriesEnrichment:
    """
    Nalazi seriju na TMDB-u i vraća lokalizovana imena sezona/epizoda.

    Tolerantno: bez TMDB ključa/mreže/pogotka vraća prazno obogaćivanje,
    pa uvoz nastavlja sa lokalnim skenom.
    """

    if not tmdb_client.is_tmdb_available():
        return SeriesEnrichment()

    year = getattr(scan, "year", None)
    series = tmdb_client.match_series(scan.title, year)
    if series is None:
        return SeriesEnrichment()

    seasons: dict[int, tuple[str | None, dict[int, str]]] = {}
    for scanned in scan.seasons:
        localized = tmdb_client.get_localized_season(
            series.tmdb_id, scanned.season_number
        )
        if localized is None:
            continue
        titles = {
            episode.episode_number: episode.name
            for episode in localized.episodes
            if episode.name
        }
        seasons[scanned.season_number] = (localized.name, titles)

    return SeriesEnrichment(
        overview=series.overview,
        genres=series.genres,
        year=series.year,
        seasons=seasons,
    )


# ==========          SERVIS UVOZA SERIJE          ==========

def _collect_episode_files(scan: SeriesScanResult, directory: Path) -> list[MediaFileCreate]:
    """Video + prevodi svake epizode kao MediaFileCreate (relativno ka folderu)."""

    files: list[MediaFileCreate] = []
    for season in scan.seasons:
        for episode in season.episodes:
            video = Path(episode.video_path)
            try:
                rel = video.relative_to(directory).as_posix()
            except ValueError:
                continue
            try:
                size = video.stat().st_size
            except OSError:
                size = 0
            files.append(
                MediaFileCreate(
                    role=MediaFileRole.VIDEO,
                    relative_path=rel,
                    size_bytes=size,
                )
            )

            for subtitle in episode.subtitles:
                sub_path = Path(subtitle.path)
                try:
                    sub_rel = sub_path.relative_to(directory).as_posix()
                except ValueError:
                    continue
                files.append(
                    MediaFileCreate(
                        role=MediaFileRole.SUBTITLE,
                        relative_path=sub_rel,
                        language=(
                            getattr(subtitle, "language", None) or "und"
                        ),
                    )
                )
    return files


def _append_extra_subtitles(directory: Path, files: list[MediaFileCreate]) -> None:
    """Dodaj prevode iz pod-foldera (Sezona N/subs…) koje skener epizoda može
    da promaši. Menja `files` (bez duplikata)."""

    known = {f.relative_path for f in files}
    for sub in find_subtitle_files(directory):
        try:
            sub_rel = Path(sub).relative_to(directory).as_posix()
        except ValueError:
            continue
        if sub_rel in known:
            continue
        known.add(sub_rel)
        files.append(
            MediaFileCreate(
                role=MediaFileRole.SUBTITLE,
                relative_path=sub_rel,
                language=subtitle_language(sub) or "und",
            )
        )


def _upsert_media_source(media_source_service, media_id: int, root, root_path: Path,
                         relative_directory: str, files: list[MediaFileCreate]) -> None:
    """Napravi ili ažuriraj media_source. Postojeći sa pogrešnim/NULL korenom se
    presloži iz nule; inače se samo zamene fajlovi. Best-effort (ne ruši uvoz)."""

    try:
        existing = media_source_service.list_media_sources(
            media_id
        )
    except Exception:  # noqa: BLE001
        existing = ()

    def _create() -> None:
        media_source_service.create_media_source(
            MediaSourceCreate(
                media_id=media_id,
                library_root_id=root.id,
                root_path_snapshot=str(root_path),
                relative_directory=relative_directory,
                manifest_path=FILMIUM_INFO_FILE_NAME,
                files=tuple(files),
            )
        )

    try:
        if existing:
            current = existing[0]
            # `replace_media_files` NE dira library_root_id. Kada
            # postojeći izvor ima pogrešan ili NULL koren (stari zapisi
            # bez `library_root_id` → epizode bez putanje, nema sličica
            # ni reprodukcije), presloži ga iz nule sa ispravnim korenom.
            if (
                current.library_root_id != root.id
                or current.relative_directory != relative_directory
            ):
                media_source_service.delete_media_source(
                    current.id
                )
                _create()
            else:
                media_source_service.replace_media_files(
                    current.id, tuple(files)
                )
        else:
            _create()
    except Exception:  # noqa: BLE001, S110
        # Registracija izvora je pomoćna; ne ruši uvoz/osvežavanje.
        pass


def _ensure_thumb_safe(video_path) -> None:
    """Napravi sličicu epizode; greška (ili nedostupan modul) ne obara uvoz."""

    try:
        from core.domains.filmium.media_thumbnail import ensure_thumbnail
        ensure_thumbnail(Path(video_path))
    except Exception:  # noqa: BLE001, S110
        pass


def _title_identity(value: str) -> str:
    return "".join(
        character for character in value.casefold() if character.isalnum()
    )


def _infer_content_mode(directory: Path, root_path: Path) -> str:
    """Zaključuje kategoriju iz putanje (Strano/Domace/Animirano + stari nazivi)."""

    try:
        parts = {
            part.casefold()
            for part in directory.resolve(strict=False)
            .relative_to(root_path)
            .parts
        }
    except ValueError:
        parts = {part.casefold() for part in directory.parts}

    return infer_content_mode_from_parts(parts)
