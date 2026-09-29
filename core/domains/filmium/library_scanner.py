import re
from dataclasses import replace
from pathlib import Path

from core.domains.filmium.image_dimensions import read_image_dimensions
from core.domains.filmium.library_manifest import (
    FILMIUM_INFO_FILE_NAME,
    FilmiumManifestError,
    load_filmium_manifest,
)
from core.domains.filmium.library_models import (
    ArtworkManifest,
    FilmiumInfoManifest,
    MediaFileRole,
    MediaFilesManifest,
    MediaFolderScanResult,
    MediaOwnershipStatus,
    ScannedMediaFile,
    SubtitleManifest,
)
from core.domains.filmium.models import MediaType
from core.domains.filmium.subtitle_language import (
    resolve_subtitle_language,
)

# ==========          PODRZANI FORMATI          ==========

VIDEO_EXTENSIONS = {
    ".avi",
    ".m4v",
    ".mkv",
    ".mov",
    ".mp4",
    ".webm",
}

IMAGE_EXTENSIONS = {
    ".jpeg",
    ".jpg",
    ".png",
    ".webp",
}

SUBTITLE_EXTENSIONS = {
    ".ass",
    ".srt",
    ".ssa",
    ".sub",
    ".vtt",
}

# Smeće koje NE pripada biblioteci i ne sme da blokira/uspori uvoz
# (torrent fajlovi su često zaključani od torrent klijenta → WinError 5).
IGNORED_EXTENSIONS = {
    ".torrent",
    ".!qb",
    ".part",
    ".aria2",
    ".!ut",
    ".bc!",
}

TRAILER_MARKERS = {"trailer", "trejler"}
POSTER_MARKERS = {"cover", "folder", "poster"}
BACKDROP_MARKERS = {
    "backdrop",
    "backgrop",
    "back",
    "fanback",
}
WALLPAPER_MARKERS = {
    "background",
    "backgrounds",
    "wallpaper",
    "wallpapers",
}
FANART_MARKERS = {"fanart"}
WALLPAPER_FOLDERS = WALLPAPER_MARKERS
FANART_FOLDERS = {"fanart", "fan-art", "fan art"}

# Godina u zagradi, uključujući raspon serije: (2024), (2013-14), (2019-2023).
# Uzima se početna godina; dozvoljen je bilo kakav sadržaj posle zagrade
# (npr. „S01 720p"), da bi se prepoznali i folderi serija.
FOLDER_PATTERN = re.compile(
    r"^(?P<title>.+?)\s*[\(\[](?P<year>\d{4})"
    r"(?:\s*[-–]\s*\d{2,4})?[\)\]].*$"
)

LANGUAGE_ALIASES: dict[str, str] = {
    "en": "en",
    "eng": "en",
    "rs": "sr",
    "sr": "sr",
    "srb": "sr",
    "sr-latn": "sr-Latn",
    "sr-latin": "sr-Latn",
    "und": "und",
}


# ==========          SCANNER GRESKE          ==========

class FilmiumLibraryScanError(ValueError):
    """Oznacava folder koji nije moguce bezbedno skenirati."""


# ==========          NAZIV I GODINA          ==========

def parse_media_folder_name(
    folder_name: str,
) -> tuple[str, int | None]:
    """Cita naslov i opcionu godinu iz naziva filmskog foldera."""

    normalized_name = folder_name.strip()
    match = FOLDER_PATTERN.fullmatch(normalized_name)

    if match is None:
        return normalized_name, None

    return (
        match.group("title").strip(),
        int(match.group("year")),
    )


def _normalized_tokens(value: str) -> set[str]:
    """Pretvara naziv datoteke u skup tokena za prepoznavanje."""

    return {
        token
        for token in re.split(r"[^a-z0-9]+", value.casefold())
        if token
    }


def _normalized_identity(value: str) -> str:
    """Pravi pojednostavljeni identitet naziva za poredjenje."""

    return "".join(
        character
        for character in value.casefold()
        if character.isalnum()
    )


# ==========          PREPOZNAVANJE ULOGE          ==========

def _detect_file_role(
    path: Path,
    expected_identity: str,
    directory: Path,
) -> MediaFileRole:
    suffix = path.suffix.casefold()
    file_name = path.name.casefold()
    tokens = _normalized_tokens(path.stem)

    if file_name == FILMIUM_INFO_FILE_NAME:
        return MediaFileRole.MANIFEST

    if suffix in SUBTITLE_EXTENSIONS:
        return MediaFileRole.SUBTITLE

    if suffix in VIDEO_EXTENSIONS:
        if tokens & TRAILER_MARKERS:
            return MediaFileRole.TRAILER

        return MediaFileRole.VIDEO

    if suffix in IMAGE_EXTENSIONS:
        kind = classify_image_artwork(path, directory, expected_identity)

        if kind == "fanart":
            return MediaFileRole.FANART
        if kind == "wallpaper":
            return MediaFileRole.WALLPAPER
        if kind == "backdrop":
            return MediaFileRole.BACKDROP
        if kind == "poster":
            return MediaFileRole.POSTER

    return MediaFileRole.UNKNOWN


def _classify_image_by_ratio(path: Path) -> MediaFileRole | None:
    """Poster je portret (~2:3), backdrop pejzaž (~16:9 do ~2:1)."""

    dimensions = read_image_dimensions(path)

    if dimensions is None:
        return None

    width, height = dimensions

    if width <= 0 or height <= 0:
        return None

    ratio = width / height

    if ratio < 0.85:
        return MediaFileRole.POSTER

    if 1.5 <= ratio <= 2.1:
        return MediaFileRole.BACKDROP

    return None


def classify_image_artwork(
    path: Path,
    base_dir: Path,
    identity: str | None = None,
) -> str | None:
    """Vrsta slike: „poster" / „backdrop" / „wallpaper" / „fanart" / None.

    Deljena logika za filmski i serijski skener: prvo folder u kome slika
    stoji (fanart/wallpaper), pa oznake u nazivu, pa poklapanje sa nazivom
    (poster), i na kraju odnos stranica. ``base_dir`` je koren u odnosu na
    koji se čitaju nazivi nadfoldera; ``identity`` je identitet naziva
    filma/serije za prepoznavanje postera imenovanog kao naslov.
    """

    tokens = _normalized_tokens(path.stem)

    try:
        parent_names = {
            part.casefold()
            for part in path.relative_to(base_dir).parent.parts
        }
    except ValueError:
        parent_names = set()

    if parent_names & FANART_FOLDERS:
        return "fanart"

    if parent_names & WALLPAPER_FOLDERS:
        return "wallpaper"

    if tokens & FANART_MARKERS:
        return "fanart"

    if tokens & WALLPAPER_MARKERS:
        return "wallpaper"

    if tokens & BACKDROP_MARKERS:
        return "backdrop"

    if tokens & POSTER_MARKERS:
        return "poster"

    if identity is not None and _normalized_identity(path.stem) == identity:
        return "poster"

    ratio_role = _classify_image_by_ratio(path)
    if ratio_role is MediaFileRole.POSTER:
        return "poster"
    if ratio_role is MediaFileRole.BACKDROP:
        return "backdrop"

    return None


def _detect_subtitle_language(path: Path) -> str | None:
    """Prepoznaje jezik prevoda (naziv → ISO → sadržaj).

    Deli isti postupak sa serijskim skenerom kroz
    ``resolve_subtitle_language``.
    """

    return resolve_subtitle_language(path)


# ==========          IZBOR PRIMARNE DATOTEKE          ==========

def _select_largest(
    files: list[ScannedMediaFile],
    role: MediaFileRole,
    warnings: list[str],
) -> ScannedMediaFile | None:
    candidates = [file for file in files if file.role is role]

    if not candidates:
        return None

    candidates.sort(
        key=lambda file: (-file.size_bytes, file.path.name.casefold())
    )

    if len(candidates) > 1:
        warnings.append(
            f"Pronadjeno je vise datoteka za ulogu '{role.value}'."
        )

    return candidates[0]


def _relative_path(path: Path, directory: Path) -> str:
    return path.relative_to(directory).as_posix()


# ==========          POSTOJECI MANIFEST          ==========

def _manifest_reference_warnings(
    directory: Path,
    manifest: FilmiumInfoManifest,
) -> list[str]:
    warnings: list[str] = []
    references = (
        manifest.files.video,
        manifest.files.poster,
        manifest.files.backdrop,
        manifest.files.trailer,
        *(artwork.path for artwork in manifest.files.wallpapers),
        *(artwork.path for artwork in manifest.files.fanart),
        *(subtitle.path for subtitle in manifest.files.subtitles),
    )

    for reference in references:
        if reference is None:
            continue

        referenced_path = directory.joinpath(*reference.split("/"))

        if not referenced_path.is_file():
            warnings.append(
                f"Manifest datoteka nije pronadjena: {reference}"
            )

    return warnings


# ==========          SKENIRANJE FOLDERA          ==========

def _resolve_scan_title(directory: Path, video_reference: str | None):
    """Naslov/godina iz naziva foldera; režim kolekcije override-uje iz naziva video fajla."""

    title, release_year = parse_media_folder_name(directory.name)

    # Režim kolekcije: naslov/godina iz naziva video fajla; fallback folder.
    collection_video_stem: str | None = None
    collection_order: int | None = None
    if video_reference is not None:
        from core.domains.filmium.movie_collection import (
            collection_title,
            parse_collection_entry,
        )

        collection_video_stem = Path(video_reference).stem
        parsed = parse_collection_entry(collection_video_stem)
        if parsed is not None:
            collection_order, entry_title, entry_year = parsed
            title = collection_title(entry_title, directory.name)
            release_year = entry_year
    return title, release_year, collection_video_stem, collection_order


def _scan_detected_files(directory: Path, collection_video_stem, collection_order, warnings):
    """Skenira fajlove foldera (rglob): preskače simbolične veze/smeće/tuđe filmove kolekcije; svakom dodeljuje rolu."""

    if collection_video_stem is not None:
        from core.domains.filmium.movie_collection import (
            collection_sidecar_matches,
        )

    expected_identity = _normalized_identity(directory.name)
    detected_files: list[ScannedMediaFile] = []

    for path in sorted(
        directory.rglob("*"),
        key=lambda item: item.as_posix().casefold(),
    ):
        if path.is_symlink():
            warnings.append(
                f"Simbolicka veza je preskocena: {path.name}"
            )
            continue

        if not path.is_file():
            continue

        # Smeće (torrent/temp): ne skeniraj i ne premeštaj — ostaje u izvoru.
        if path.suffix.casefold() in IGNORED_EXTENSIONS:
            continue

        # Režim kolekcije: preskoči sve što ne pripada ovom filmu (video +
        # sidecar istog baznog naziva ILI po rednom broju filma).
        if collection_video_stem is not None and not (
            collection_order is not None
            and collection_sidecar_matches(
                path,
                collection_video_stem,
                directory.name,
                collection_order,
            )
        ):
            continue

        role = _detect_file_role(
            path,
            expected_identity,
            directory,
        )
        detected_files.append(
            ScannedMediaFile(
                path=path,
                role=role,
                size_bytes=path.stat().st_size,
                language=(
                    _detect_subtitle_language(path)
                    if role is MediaFileRole.SUBTITLE
                    else None
                ),
            )
        )
    return detected_files


def _select_artwork_manifests(detected_files, directory: Path):
    """Sortiraj i mapiraj titlove/wallpaper/fanart u manifest-torke. Vraća (subtitles, wallpapers, fanart)."""

    wallpaper_files = sorted(
        (
            file
            for file in detected_files
            if file.role is MediaFileRole.WALLPAPER
        ),
        key=lambda file: file.path.as_posix().casefold(),
    )
    fanart_files = sorted(
        (
            file
            for file in detected_files
            if file.role is MediaFileRole.FANART
        ),
        key=lambda file: file.path.as_posix().casefold(),
    )

    subtitle_files = sorted(
        (
            file
            for file in detected_files
            if file.role is MediaFileRole.SUBTITLE
        ),
        key=lambda file: file.path.as_posix().casefold(),
    )

    subtitles = tuple(
        SubtitleManifest(
            path=_relative_path(subtitle.path, directory),
            language=subtitle.language or "und",
            label=None,
        )
        for subtitle in subtitle_files
    )
    wallpapers = tuple(
        ArtworkManifest(
            path=_relative_path(artwork.path, directory),
            is_primary=index == 0,
        )
        for index, artwork in enumerate(wallpaper_files)
    )
    fanart = tuple(
        ArtworkManifest(
            path=_relative_path(artwork.path, directory),
            is_primary=index == 0,
        )
        for index, artwork in enumerate(fanart_files)
    )
    return subtitles, wallpapers, fanart


def _has_disk_files(primary_video, poster, backdrop, trailer,
                    subtitles, wallpapers, fanart) -> bool:
    """Ima li folder ijedan fajl sa diska (video/slike/titlovi)?"""
    return (
        primary_video is not None
        or poster is not None
        or backdrop is not None
        or trailer is not None
        or bool(subtitles)
        or bool(wallpapers)
        or bool(fanart)
    )


def resolve_media_type(directory: Path, detector=None) -> MediaType:
    """Auto film-vs-serija za folder (>=2 detektovane epizode → serija).

    `detector` je injektabilan radi testova; podrazumevano `looks_like_series`.
    Best-effort: bilo koja greška → MOVIE (bezbedan podrazumevani tip).
    """
    det = detector
    if det is None:
        try:
            from core.domains.filmium.series_scanner import looks_like_series
            det = looks_like_series
        except Exception:  # noqa: BLE001
            return MediaType.MOVIE
    try:
        return MediaType.SERIES if det(directory) else MediaType.MOVIE
    except Exception:  # noqa: BLE001
        return MediaType.MOVIE


def _build_disk_manifest(directory, title, release_year, detected_files, warnings):
    """Iz detektovanih fajlova bira primarne + gradi disk-manifest. Vraća (manifest, primary_video, has_disk_files)."""

    primary_video = _select_largest(
        detected_files,
        MediaFileRole.VIDEO,
        warnings,
    )
    poster = _select_largest(
        detected_files,
        MediaFileRole.POSTER,
        warnings,
    )
    backdrop = _select_largest(
        detected_files,
        MediaFileRole.BACKDROP,
        warnings,
    )
    trailer = _select_largest(
        detected_files,
        MediaFileRole.TRAILER,
        warnings,
    )
    subtitles, wallpapers, fanart = _select_artwork_manifests(
        detected_files, directory
    )
    disk_manifest = FilmiumInfoManifest(
        title=title,
        media_type=resolve_media_type(directory),
        release_year=release_year,
        ownership_status=(
            MediaOwnershipStatus.OWNED
            if primary_video is not None
            else MediaOwnershipStatus.CATALOG_ONLY
        ),
        files=MediaFilesManifest(
            video=(
                _relative_path(primary_video.path, directory)
                if primary_video is not None
                else None
            ),
            poster=(
                _relative_path(poster.path, directory)
                if poster is not None
                else None
            ),
            backdrop=(
                _relative_path(backdrop.path, directory)
                if backdrop is not None
                else None
            ),
            trailer=(
                _relative_path(trailer.path, directory)
                if trailer is not None
                else None
            ),
            subtitles=subtitles,
            wallpapers=wallpapers,
            fanart=fanart,
        ),
    )
    has_disk_files = _has_disk_files(
        primary_video, poster, backdrop, trailer,
        subtitles, wallpapers, fanart,
    )
    return disk_manifest, primary_video, has_disk_files


def _reconcile_with_json(directory, disk_manifest, primary_video, has_disk_files,
                         title, release_year, warnings):
    """Ako postoji filmium_info.json: metapodaci iz njega, fajlovi sa diska. Vraća (manifest, result_title, result_year)."""

    manifest_path = directory / FILMIUM_INFO_FILE_NAME

    if manifest_path.is_file():
        # Postoji filmium_info.json: zadrži METAPODATKE iz njega, ali FAJLOVE
        # uzmi sa diska (video/titlovi/slike). Time se pravilno formiran folder
        # ne prikazuje kao offline / "samo json".
        try:
            loaded = load_filmium_manifest(manifest_path)
        except FilmiumManifestError as error:
            raise FilmiumLibraryScanError(str(error)) from error

        reconciled_files = (
            disk_manifest.files if has_disk_files else loaded.files
        )
        manifest = replace(
            loaded,
            files=reconciled_files,
            ownership_status=(
                MediaOwnershipStatus.OWNED
                if primary_video is not None
                else loaded.ownership_status
            ),
        )
        warnings.extend(
            _manifest_reference_warnings(directory, manifest)
        )
        result_title = manifest.title
        result_year = manifest.release_year
    else:
        manifest = disk_manifest
        result_title = title
        result_year = release_year
    return manifest, result_title, result_year


def scan_media_directory(
    directory: Path,
    video_reference: str | None = None,
) -> MediaFolderScanResult:
    """
    Skenira jedan folder bez izmene njegovih datoteka.

    ``video_reference`` (naziv video fajla unutar foldera) skenira SAMO jedan
    film iz „kolekcije filmova" (npr. „Pirates of the Caribbean"): uzima taj
    video + sidecar fajlove (poster/backdrop/prevod) istog baznog naziva, a
    naslov/godinu izvlači iz naziva fajla (fallback na ime foldera).
    """

    if not directory.is_dir():
        raise FilmiumLibraryScanError(
            f"FILMIUM folder ne postoji: {directory}"
        )

    title, release_year, collection_video_stem, collection_order = (
        _resolve_scan_title(directory, video_reference)
    )

    warnings: list[str] = []

    detected_files = _scan_detected_files(
        directory, collection_video_stem, collection_order, warnings
    )

    disk_manifest, primary_video, has_disk_files = _build_disk_manifest(
        directory, title, release_year, detected_files, warnings
    )

    manifest, result_title, result_year = _reconcile_with_json(
        directory, disk_manifest, primary_video, has_disk_files,
        title, release_year, warnings
    )

    return MediaFolderScanResult(
        directory=directory,
        title=result_title,
        release_year=result_year,
        manifest=manifest,
        detected_files=tuple(detected_files),
        warnings=tuple(warnings),
    )