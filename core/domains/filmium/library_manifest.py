import json
import re
from datetime import date
from pathlib import Path, PurePosixPath
from typing import Any

from core.domains.filmium.library_models import (
    ArtworkManifest,
    EpisodeManifest,
    FilmiumInfoManifest,
    MediaFilesManifest,
    MediaOwnershipStatus,
    SeasonManifest,
    SubtitleManifest,
)
from core.domains.filmium.models import MediaType

# ==========          MANIFEST KONSTANTE          ==========

FILMIUM_INFO_FILE_NAME = "filmium_info.json"
CURRENT_SCHEMA_VERSION = 2
SUPPORTED_SCHEMA_VERSIONS = {1, CURRENT_SCHEMA_VERSION}


# ==========          MANIFEST GRESKE          ==========

class FilmiumManifestError(ValueError):
    """Oznacava neispravan ili nebezbedan FILMIUM manifest."""


# ==========          RELATIVNE PUTANJE          ==========

def normalize_manifest_path(
    value: str,
    field_name: str,
) -> str:
    """Normalizuje bezbednu relativnu putanju iz manifesta."""

    normalized_value = value.strip().replace("\\", "/")

    if not normalized_value:
        raise FilmiumManifestError(
            f"Manifest polje '{field_name}' ne sme biti prazno."
        )

    if re.match(r"^[A-Za-z]:", normalized_value):
        raise FilmiumManifestError(
            f"Manifest polje '{field_name}' mora biti relativna putanja."
        )

    path = PurePosixPath(normalized_value)

    if path.is_absolute() or ".." in path.parts:
        raise FilmiumManifestError(
            f"Manifest polje '{field_name}' izlazi iz filmskog foldera."
        )

    return path.as_posix()


def _optional_manifest_path(
    value: object,
    field_name: str,
) -> str | None:
    """Validira opcionu relativnu putanju."""

    if value is None:
        return None

    if not isinstance(value, str):
        raise FilmiumManifestError(
            f"Manifest polje '{field_name}' mora biti tekst ili null."
        )

    return normalize_manifest_path(value, field_name)


# ==========          POMOCNA VALIDACIJA          ==========

def _require_mapping(
    value: object,
    field_name: str,
) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise FilmiumManifestError(
            f"Manifest polje '{field_name}' mora biti JSON objekat."
        )

    return value


def _require_string(
    value: object,
    field_name: str,
) -> str:
    if not isinstance(value, str) or not value.strip():
        raise FilmiumManifestError(
            f"Manifest polje '{field_name}' mora biti neprazan tekst."
        )

    return value.strip()


def _optional_string(
    value: object,
    field_name: str,
) -> str | None:
    if value is None:
        return None

    if not isinstance(value, str):
        raise FilmiumManifestError(
            f"Manifest polje '{field_name}' mora biti tekst ili null."
        )

    return value.strip() or None


def _optional_integer(
    value: object,
    field_name: str,
) -> int | None:
    if value is None:
        return None

    if isinstance(value, bool) or not isinstance(value, int):
        raise FilmiumManifestError(
            f"Manifest polje '{field_name}' mora biti ceo broj ili null."
        )

    return value


def _parse_genres(value: object) -> tuple[str, ...]:
    if value is None:
        return ()

    if not isinstance(value, list):
        raise FilmiumManifestError(
            "Manifest polje 'genres' mora biti lista."
        )

    genres: dict[str, str] = {}

    for genre in value:
        normalized_genre = _require_string(genre, "genres")
        genres.setdefault(
            normalized_genre.casefold(),
            normalized_genre,
        )

    return tuple(genres.values())


# ==========          PARSIRANJE DATOTEKA          ==========

def _parse_subtitles(value: object) -> tuple[SubtitleManifest, ...]:
    if value is None:
        return ()

    if not isinstance(value, list):
        raise FilmiumManifestError(
            "Manifest polje 'files.subtitles' mora biti lista."
        )

    subtitles: list[SubtitleManifest] = []

    for index, subtitle_value in enumerate(value):
        subtitle_data = _require_mapping(
            subtitle_value,
            f"files.subtitles[{index}]",
        )

        subtitles.append(
            SubtitleManifest(
                path=normalize_manifest_path(
                    _require_string(
                        subtitle_data.get("path"),
                        f"files.subtitles[{index}].path",
                    ),
                    f"files.subtitles[{index}].path",
                ),
                language=_require_string(
                    subtitle_data.get("language"),
                    f"files.subtitles[{index}].language",
                ),
                label=_optional_string(
                    subtitle_data.get("label"),
                    f"files.subtitles[{index}].label",
                ),
            )
        )

    return tuple(subtitles)


def _parse_artworks(
    value: object,
    field_name: str,
) -> tuple[ArtworkManifest, ...]:
    """Cita listu prenosivih wallpaper ili fanart referenci."""

    if value is None:
        return ()

    if not isinstance(value, list):
        raise FilmiumManifestError(
            f"Manifest polje '{field_name}' mora biti lista."
        )

    artworks: list[ArtworkManifest] = []

    for index, artwork_value in enumerate(value):
        item_name = f"{field_name}[{index}]"
        artwork_data = _require_mapping(artwork_value, item_name)
        is_primary = artwork_data.get("is_primary", False)

        if not isinstance(is_primary, bool):
            raise FilmiumManifestError(
                f"Manifest polje '{item_name}.is_primary' "
                "mora biti boolean."
            )

        artworks.append(
            ArtworkManifest(
                path=normalize_manifest_path(
                    _require_string(
                        artwork_data.get("path"),
                        f"{item_name}.path",
                    ),
                    f"{item_name}.path",
                ),
                label=_optional_string(
                    artwork_data.get("label"),
                    f"{item_name}.label",
                ),
                is_primary=is_primary,
            )
        )

    return tuple(artworks)


def _parse_files(value: object) -> MediaFilesManifest:
    if value is None:
        return MediaFilesManifest()

    files_data = _require_mapping(value, "files")

    return MediaFilesManifest(
        video=_optional_manifest_path(
            files_data.get("video"),
            "files.video",
        ),
        poster=_optional_manifest_path(
            files_data.get("poster"),
            "files.poster",
        ),
        backdrop=_optional_manifest_path(
            files_data.get("backdrop"),
            "files.backdrop",
        ),
        trailer=_optional_manifest_path(
            files_data.get("trailer"),
            "files.trailer",
        ),
        subtitles=_parse_subtitles(files_data.get("subtitles")),
        wallpapers=_parse_artworks(
            files_data.get("wallpapers"),
            "files.wallpapers",
        ),
        fanart=_parse_artworks(
            files_data.get("fanart"),
            "files.fanart",
        ),
    )


# ==========          MANIFEST PARSIRANJE          ==========

def _parse_seasons(value: object) -> tuple[SeasonManifest, ...]:
    """Parsira opcionu listu sezona/epizoda (aditivno polje)."""

    if not isinstance(value, list):
        return ()

    seasons: list[SeasonManifest] = []
    for raw_season in value:
        if not isinstance(raw_season, dict):
            continue
        season_number = _optional_integer(
            raw_season.get("season_number"), "season_number"
        )
        if season_number is None:
            continue

        episodes: list[EpisodeManifest] = []
        raw_episodes = raw_season.get("episodes")
        if isinstance(raw_episodes, list):
            for raw_episode in raw_episodes:
                if not isinstance(raw_episode, dict):
                    continue
                episode_number = _optional_integer(
                    raw_episode.get("episode_number"), "episode_number"
                )
                if episode_number is None:
                    continue
                episodes.append(
                    EpisodeManifest(
                        episode_number=episode_number,
                        title=_optional_string(
                            raw_episode.get("title"), "title"
                        ),
                    )
                )

        seasons.append(
            SeasonManifest(
                season_number=season_number,
                name=_optional_string(raw_season.get("name"), "name"),
                episodes=tuple(episodes),
            )
        )

    return tuple(seasons)


def parse_filmium_manifest(
    data: object,
) -> FilmiumInfoManifest:
    """Pretvara procitani JSON objekat u FILMIUM manifest."""

    manifest_data = _require_mapping(data, "manifest")
    schema_version = manifest_data.get("schema_version")

    if schema_version not in SUPPORTED_SCHEMA_VERSIONS:
        raise FilmiumManifestError(
            "Nepodrzana filmium_info.json schema verzija: "
            f"{schema_version!r}."
        )

    title = _require_string(manifest_data.get("title"), "title")

    try:
        media_type = MediaType(
            _require_string(
                manifest_data.get("media_type"),
                "media_type",
            )
        )
    except ValueError as error:
        raise FilmiumManifestError(
            "Manifest media_type mora biti 'movie' ili 'series'."
        ) from error

    release_year = _optional_integer(
        manifest_data.get("release_year"),
        "release_year",
    )
    maximum_release_year = date.today().year + 10  # noqa: DTZ011

    if (
        release_year is not None
        and not 1888 <= release_year <= maximum_release_year
    ):
        raise FilmiumManifestError(
            "Manifest godina izdanja nije u dozvoljenom opsegu."
        )

    runtime_minutes = _optional_integer(
        manifest_data.get("runtime_minutes"),
        "runtime_minutes",
    )

    if (
        runtime_minutes is not None
        and not 1 <= runtime_minutes <= 10_000
    ):
        raise FilmiumManifestError(
            "Manifest trajanje mora biti izmedju 1 i 10000 minuta."
        )

    try:
        ownership_status = MediaOwnershipStatus(
            manifest_data.get(
                "ownership_status",
                MediaOwnershipStatus.OWNED.value,
            )
        )
    except ValueError as error:
        raise FilmiumManifestError(
            "Manifest ownership_status nije podrzan."
        ) from error

    return FilmiumInfoManifest(
        # Verzija 1 se ucitava bez gubitka podataka, a sledeci
        # upis je automatski nadogradjuje na trenutnu verziju.
        schema_version=CURRENT_SCHEMA_VERSION,
        title=title,
        original_title=_optional_string(
            manifest_data.get("original_title"),
            "original_title",
        ),
        media_type=media_type,
        release_year=release_year,
        runtime_minutes=runtime_minutes,
        description=_optional_string(
            manifest_data.get("description"),
            "description",
        ),
        genres=_parse_genres(manifest_data.get("genres")),
        studio=_optional_string(
            manifest_data.get("studio"),
            "studio",
        ),
        franchise=_optional_string(
            manifest_data.get("franchise"),
            "franchise",
        ),
        franchise_order=_optional_integer(
            manifest_data.get("franchise_order"),
            "franchise_order",
        ),
        content_category=_parse_content_category(
            manifest_data.get("content_category")
        ),
        ownership_status=ownership_status,
        files=_parse_files(manifest_data.get("files")),
        seasons=_parse_seasons(manifest_data.get("seasons")),
    )


def _parse_content_category(value: object) -> str:
    """Kategorija sadržaja iz manifesta (regular/animated/domestic)."""

    if isinstance(value, str) and value in {
        "regular",
        "animated",
        "domestic",
    }:
        return value
    return "regular"


# ==========          MANIFEST CITANJE          ==========

def load_filmium_manifest(path: Path) -> FilmiumInfoManifest:
    """Ucitava i validira filmium_info.json datoteku."""

    try:
        with path.open("r", encoding="utf-8") as manifest_file:
            data = json.load(manifest_file)
    except (OSError, json.JSONDecodeError) as error:
        raise FilmiumManifestError(
            f"FILMIUM manifest nije moguce procitati: {path}"
        ) from error

    return parse_filmium_manifest(data)


# ==========          MANIFEST SERIJALIZACIJA          ==========

def filmium_manifest_to_dict(
    manifest: FilmiumInfoManifest,
) -> dict[str, Any]:
    """Pretvara manifest u JSON kompatibilan recnik."""

    return {
        "schema_version": CURRENT_SCHEMA_VERSION,
        "media_type": manifest.media_type.value,
        "title": manifest.title,
        "original_title": manifest.original_title,
        "release_year": manifest.release_year,
        "runtime_minutes": manifest.runtime_minutes,
        "description": manifest.description,
        "genres": list(manifest.genres),
        "studio": manifest.studio,
        "franchise": manifest.franchise,
        "franchise_order": manifest.franchise_order,
        "content_category": manifest.content_category,
        "ownership_status": manifest.ownership_status.value,
        "files": {
            "video": manifest.files.video,
            "poster": manifest.files.poster,
            "backdrop": manifest.files.backdrop,
            "trailer": manifest.files.trailer,
            "subtitles": [
                {
                    "path": subtitle.path,
                    "language": subtitle.language,
                    "label": subtitle.label,
                }
                for subtitle in manifest.files.subtitles
            ],
            "wallpapers": [
                {
                    "path": artwork.path,
                    "label": artwork.label,
                    "is_primary": artwork.is_primary,
                }
                for artwork in manifest.files.wallpapers
            ],
            "fanart": [
                {
                    "path": artwork.path,
                    "label": artwork.label,
                    "is_primary": artwork.is_primary,
                }
                for artwork in manifest.files.fanart
            ],
        },
        "seasons": [
            {
                "season_number": season.season_number,
                "name": season.name,
                "episodes": [
                    {
                        "episode_number": episode.episode_number,
                        "title": episode.title,
                    }
                    for episode in season.episodes
                ],
            }
            for season in manifest.seasons
        ],
    }


# ==========          MANIFEST UPIS          ==========

def write_filmium_manifest(
    path: Path,
    manifest: FilmiumInfoManifest,
) -> None:
    """Atomski upisuje FILMIUM manifest u UTF-8 formatu."""

    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = path.with_name(f".{path.name}.tmp")

    try:
        with temporary_path.open("w", encoding="utf-8") as manifest_file:
            json.dump(
                filmium_manifest_to_dict(manifest),
                manifest_file,
                ensure_ascii=False,
                indent=2,
            )
            manifest_file.write("\n")

        temporary_path.replace(path)
    except OSError as error:
        temporary_path.unlink(missing_ok=True)

        raise FilmiumManifestError(
            f"FILMIUM manifest nije moguce sacuvati: {path}"
        ) from error