"""Skener foldera serije: prepoznaje sezone, epizode i njihove fajlove.

Koristi parser iz ``series_parser`` za brojeve sezone/epizode, prepoznaje
jezik prevoda (naziv → ISO kod → sadržaj) i grupiše sve u strukturu
serija → sezone → epizode. Slike (poster/backdrop) se traže na nivou
serije (u korenskom folderu).
"""

import re
from dataclasses import dataclass
from pathlib import Path

from core.domains.filmium.library_scanner import (
    IMAGE_EXTENSIONS,
    SUBTITLE_EXTENSIONS,
    VIDEO_EXTENSIONS,
    classify_image_artwork,
)
from core.domains.filmium.series_parser import (
    clean_series_title,
    detect_season,
    detect_season_name,
    is_season_only_folder,
    parse_episode,
)
from core.domains.filmium.subtitle_language import (
    resolve_subtitle_language,
)

# Prevodi serija uključuju i .idx (par uz .sub kod VobSub).
SERIES_SUBTITLE_EXTENSIONS = SUBTITLE_EXTENSIONS | {".idx"}

# Folderi sa prevodima epizoda (skeniraju se, NISU extras).
EPISODE_SUBTITLE_FOLDERS = {"subs", "sub", "prevodi"}

# Folderi koji idu u „Extras/ostalo" (radni/originalni prevodi, beleške).
OSTALO_FOLDERS = {
    "prevod",
    "obrada prevod",
    "prevedeno korektno",
    "title",
    "titl",
    "ostalo",
}

# Folderi koji idu u „Extras/<naziv>" (dodaci, specijali, fanart, muzika…).
EXTRA_FOLDERS = {
    "extras",
    "extra",
    "bonus",
    "movies",
    "specials",
    "special",
}

# Svi folderi koji se izuzimaju iz skeniranja epizoda i sele u Extras.
_EXTRA_ALL = EXTRA_FOLDERS | OSTALO_FOLDERS


def _is_notes_file(name: str) -> bool:
    """Važni tekstualni fajlovi (lista epizoda, beleške) → Extras/ostalo."""

    lowered = name.casefold()
    if not lowered.endswith(".txt"):
        return False
    return (
        lowered.startswith(("vazno", "važno")) or "episode name" in lowered or "epname" in lowered or "episode order" in lowered
    )


def _extra_root_for(path: Path, directory: Path) -> Path | None:
    """Ako je fajl unutar extra foldera, vraća najviši takav folder."""

    accumulated = directory
    for part in path.relative_to(directory).parts[:-1]:
        accumulated = accumulated / part
        if part.casefold() in _EXTRA_ALL:
            return accumulated
    return None


# ==========          MODELI REZULTATA          ==========

@dataclass(frozen=True)
class SubtitleRef:
    path: Path
    language: str | None


@dataclass(frozen=True)
class ArtworkRef:
    """Slika serije: vrsta (poster/backdrop/wallpaper/fanart) i sezona.

    ``season`` je ``None`` za sliku cele serije (npr. poster sa rasponom
    godina ili slika bez oznake sezone).
    """

    path: Path
    kind: str
    season: int | None


@dataclass(frozen=True)
class EpisodeScan:
    season_number: int
    episode_number: int
    title: str | None
    video_path: Path
    subtitles: tuple[SubtitleRef, ...]


@dataclass(frozen=True)
class SeasonScan:
    season_number: int
    episodes: tuple[EpisodeScan, ...]
    name: str | None = None


@dataclass(frozen=True)
class SeriesScanResult:
    directory: Path
    title: str
    seasons: tuple[SeasonScan, ...]
    poster_path: Path | None
    backdrop_path: Path | None
    warnings: tuple[str, ...]
    artwork: tuple[ArtworkRef, ...] = ()
    extras: tuple[Path, ...] = ()


# Sistemski/nevalidni folderi koji se preskaču pri skeniranju biblioteke.
_SKIP_DIRECTORIES = {
    "system volume information",
    "$recycle.bin",
    "found.000",
    "recycler",
    ".trash-1000",
    "@eadir",
}


# ==========          POMOĆNE FUNKCIJE          ==========

def _season_from_folders(
    file_path: Path,
    series_root: Path,
) -> int | None:
    """Traži broj sezone u folderima između korena i fajla."""

    try:
        relative = file_path.relative_to(series_root)
    except ValueError:
        return None

    season: int | None = None

    for part in relative.parts[:-1]:
        detected = detect_season(part)
        if detected is not None:
            season = detected

    return season


def _collect_season_names(directory: Path) -> dict[int, str]:
    """Ime sezone po broju iz naziva foldera („Sezona 2 - Avanture...").

    Gleda sam koren i sve poddirektorijume; prvo pronađeno ime za dati broj
    pobeđuje (stabilan sortiran redosled).
    """

    names: dict[int, str] = {}
    candidates = [directory, *(p for p in sorted(directory.rglob("*")) if p.is_dir())]

    for candidate in candidates:
        number = detect_season(candidate.name)
        if number is None or number in names:
            continue
        name = detect_season_name(candidate.name)
        if name:
            names[number] = name

    return names


def _subtitle_language(path: Path) -> str | None:
    # Isti postupak kao u filmskom skeneru (naziv → ISO → sadržaj).
    return resolve_subtitle_language(path)


_YEAR_RANGE = re.compile(
    r"(?:19|20)\d{2}\s*[-–]\s*(?:19|20)?\d{2}",
)
_YEAR_RANGE_OR_YEAR = re.compile(
    r"[(\[]?(?:19|20)\d{2}(?:\s*[-–]\s*(?:19|20)?\d{2})?[)\]]?",
)


def _artwork_season(image: Path, directory: Path) -> tuple[int | None, bool]:
    """Vraća (sezona, cela_serija) za sliku.

    Redosled: sezona iz nadfoldera → raspon godina u nazivu (cela serija)
    → marker sezone u nazivu („season 1", „s2", „sezona 2").
    """

    season = _season_from_folders(image, directory)
    if season is not None:
        return season, False

    if _YEAR_RANGE.search(image.stem):
        return None, True  # poster/slika cele serije

    season = detect_season(image.stem)
    if season is not None:
        return season, False

    return None, False


def _scan_artwork(
    directory: Path,
    images: list[Path],
) -> list[ArtworkRef]:
    """Klasifikuje sve slike serije (vrsta + sezona), isti klasifikator
    kao filmski skener."""

    identity = "".join(
        character for character in directory.name.casefold()
        if character.isalnum()
    )

    series_identity = _title_identity(clean_series_title(directory.name))

    refs: list[ArtworkRef] = []
    # Prednost slikama u korenu serije (stabilan, predvidiv redosled).
    ordered = sorted(
        images,
        key=lambda image: (image.parent != directory, image.as_posix()),
    )

    for image in ordered:
        kind = classify_image_artwork(image, directory, identity)

        # Rezerva: slika čiji naziv (bez godine i sezonskog markera)
        # odgovara nazivu serije je poster — cele serije („Hunter X Hunter
        # (2011-2014).jpg") ili sezone („Charmed Season 1.jpg", „Mandalorian S1").
        if kind is None and series_identity:
            stripped = _YEAR_RANGE_OR_YEAR.sub(" ", image.stem)
            stripped = re.sub(
                r"(?:seasons?e?|sezona)[\s._-]*\d{1,2}",
                " ",
                stripped,
                flags=re.IGNORECASE,
            )
            stripped = re.sub(
                r"(?:^|[\s._-])s\d{1,2}(?![\dEe])",
                " ",
                stripped,
                flags=re.IGNORECASE,
            )
            if _title_identity(stripped) == series_identity:
                kind = "poster"

        if kind is None:
            continue
        season, _whole = _artwork_season(image, directory)
        refs.append(ArtworkRef(path=image, kind=kind, season=season))

    return refs


def _representative_artwork(
    refs: list[ArtworkRef],
) -> tuple[Path | None, Path | None]:
    """Bira reprezentativni poster i backdrop serije (za API/GUI karticu):
    prvo slike cele serije, pa najniža sezona."""

    def pick(kind: str) -> Path | None:
        matches = [ref for ref in refs if ref.kind == kind]
        if not matches:
            return None
        matches.sort(
            key=lambda ref: (
                ref.season is not None,
                ref.season if ref.season is not None else -1,
            ),
        )
        return matches[0].path

    return pick("poster"), pick("backdrop")


# ==========          SKENIRANJE          ==========

def scan_series_directory(directory: Path) -> SeriesScanResult:
    """Prolazi folder serije i sastavlja strukturu sezona i epizoda."""

    directory = Path(directory)
    warnings: list[str] = []
    videos: list[Path] = []
    subtitles: list[Path] = []
    images: list[Path] = []

    extras: set[Path] = set()

    for path in sorted(directory.rglob("*")):
        if not path.is_file():
            continue

        # Extras folderi (Movies/Bonus/Prevod…) se izuzimaju iz skeniranja
        # epizoda i sele u „Extras" celi.
        extra_root = _extra_root_for(path, directory)
        if extra_root is not None:
            extras.add(extra_root)
            continue

        # Važni tekstualni fajlovi (lista epizoda, beleške) → Extras/ostalo.
        if _is_notes_file(path.name):
            extras.add(path)
            continue

        suffix = path.suffix.casefold()

        if suffix in VIDEO_EXTENSIONS:
            videos.append(path)
        elif suffix in SERIES_SUBTITLE_EXTENSIONS:
            subtitles.append(path)
        elif suffix in IMAGE_EXTENSIONS:
            images.append(path)

    # (sezona, epizoda) → radni zapis epizode
    episodes: dict[tuple[int, int], dict[str, object]] = {}

    for video in videos:
        info = parse_episode(video.stem)
        episode_number = info.episode
        title = info.episode_title
        season = info.season

        # Kad naziv fajla ne otkriva epizodu, probaj naziv foldera
        # (npr. epizoda u svom folderu "Episode 1" ili "1 - Naslov").
        if episode_number is None:
            folder_info = parse_episode(video.parent.name)
            episode_number = folder_info.episode
            title = title or folder_info.episode_title
            season = season if season is not None else folder_info.season

        if episode_number is None:
            continue  # nije epizoda (npr. dodatak ili trejler)

        if season is None:
            season = _season_from_folders(video, directory)
        if season is None:
            # Sezona može biti u imenu samog root foldera
            # („His Dark Materials Sezona 1", „Carnival Row S01 720p").
            season = detect_season(directory.name)
        if season is None:
            season = 1

        key = (season, episode_number)

        if key in episodes:
            warnings.append(
                f"Više video fajlova za S{season:02d}E{episode_number:02d}."
            )
            continue

        episodes[key] = {
            "title": title,
            "video": video,
            "subs": [],
        }

    _attach_subtitles(directory, subtitles, episodes, warnings)

    seasons_map: dict[int, list[EpisodeScan]] = {}

    for (season, episode), record in episodes.items():
        scan = EpisodeScan(
            season_number=season,
            episode_number=episode,
            title=record["title"],  # type: ignore[arg-type]
            video_path=record["video"],  # type: ignore[arg-type]
            subtitles=tuple(record["subs"]),  # type: ignore[arg-type]
        )
        seasons_map.setdefault(season, []).append(scan)

    season_names = _collect_season_names(directory)

    seasons = tuple(
        SeasonScan(
            season_number=season,
            episodes=tuple(
                sorted(items, key=lambda item: item.episode_number)
            ),
            name=season_names.get(season),
        )
        for season, items in sorted(seasons_map.items())
    )

    artwork = _scan_artwork(directory, images)
    poster, backdrop = _representative_artwork(artwork)

    return SeriesScanResult(
        directory=directory,
        title=clean_series_title(directory.name),
        seasons=seasons,
        poster_path=poster,
        backdrop_path=backdrop,
        warnings=tuple(warnings),
        artwork=tuple(artwork),
        extras=tuple(sorted(extras)),
    )


def _target_from_ancestors(
    subtitle: Path,
    directory: Path,
    episodes: dict[tuple[int, int], dict[str, object]],
    season: int | None,
):
    """Strategija: broj epizode iz naziva NADFOLDERA (Subs/<Show.S01E01>/<jezik>.srt)."""

    try:
        ancestors = subtitle.relative_to(directory).parts[:-1]
    except ValueError:
        ancestors = ()
    for part in reversed(ancestors):
        # Čist sezonski folder („Season 1") nije oznaka epizode —
        # njegov goli broj se ne sme uzeti kao broj epizode.
        if is_season_only_folder(part):
            continue
        folder_info = parse_episode(part)
        if folder_info.episode is None:
            continue
        folder_season = folder_info.season
        if folder_season is None:
            folder_season = season if season is not None else 1
        return episodes.get(
            (folder_season, folder_info.episode)
        )
    return None


def _find_subtitle_target(
    subtitle: Path,
    directory: Path,
    episodes: dict[tuple[int, int], dict[str, object]],
):
    """Pronađi epizodu za prevod kroz 4 strategije (broj/folder/isti folder/prefiks)."""

    info = parse_episode(subtitle.stem)
    season = info.season

    if season is None:
        season = _season_from_folders(subtitle, directory)

    target: dict[str, object] | None = None

    # 1) Po broju sezone i epizode iz naziva prevoda.
    if info.episode is not None:
        target = episodes.get(((season or 1), info.episode))

    # 1b) Epizoda iz naziva nadfoldera (Subs/<Show.S01E01>/<jezik>.srt):
    # fajl je imenovan po jeziku, broj epizode nosi folder iznad njega.
    if target is None and info.episode is None:
        target = _target_from_ancestors(subtitle, directory, episodes, season)

    # 2) Isti folder sa tačno jednom epizodom.
    if target is None:
        same_folder = [
            record
            for record in episodes.values()
            if isinstance(record["video"], Path)
            and record["video"].parent == subtitle.parent
        ]
        if len(same_folder) == 1:
            target = same_folder[0]

    # 3) Prevod počinje istim nazivom kao video.
    if target is None:
        sub_stem = subtitle.stem.casefold()
        for record in episodes.values():
            video = record["video"]
            if (
                isinstance(video, Path)
                and sub_stem.startswith(video.stem.casefold())
            ):
                target = record
                break

    return target


def _attach_subtitles(
    directory: Path,
    subtitles: list[Path],
    episodes: dict[tuple[int, int], dict[str, object]],
    warnings: list[str],
) -> None:
    for subtitle in subtitles:
        target = _find_subtitle_target(subtitle, directory, episodes)

        if target is None:
            warnings.append(
                f"Prevod nije povezan sa epizodom: {subtitle.name}"
            )
            continue

        subs = target["subs"]
        assert isinstance(subs, list)
        subs.append(
            SubtitleRef(
                path=subtitle,
                language=_subtitle_language(subtitle),
            )
        )


def looks_like_series(directory: Path) -> bool:
    """Vraća True ako folder izgleda kao serija (bar dve epizode)."""

    result = scan_series_directory(directory)
    total = sum(len(season.episodes) for season in result.seasons)
    return total >= 2


# ==========          VIŠE SERIJA (BIBLIOTEKA)          ==========

def _episode_count(result: SeriesScanResult) -> int:
    return sum(len(season.episodes) for season in result.seasons)


def _has_direct_episodes(directory: Path) -> bool:
    """True ako folder ima video-epizode direktno u sebi (ne u podfolderu)."""

    for path in directory.iterdir():
        if not path.is_file():
            continue
        if path.suffix.casefold() not in VIDEO_EXTENSIONS:
            continue
        if parse_episode(path.stem).episode is not None:
            return True
    return False


def _title_identity(value: str) -> str:
    """Uprošćen naziv za poređenje serija (samo slova i cifre)."""

    return "".join(
        character for character in value.casefold() if character.isalnum()
    )


def _subfolder_series_title(directory: Path, sub: Path) -> str:
    """Naziv serije kojoj podfolder pripada.

    Čist sezonski folder („Sezona 1") pripada seriji iz imena roditelja;
    folder sa nazivom („His Dark Materials Sezona 1") nosi svoj naziv.
    """

    if is_season_only_folder(sub.name):
        return _title_identity(clean_series_title(directory.name))
    return _title_identity(clean_series_title(sub.name))


def _is_single_series(directory: Path, subdirs: list[Path]) -> bool:
    """True ako folder predstavlja tačno jednu seriju (a ne biblioteku)."""

    if _has_direct_episodes(directory):
        return True

    season_dirs = [
        sub for sub in subdirs if detect_season(sub.name) is not None
    ]
    if not season_dirs:
        return False

    # Podfolderi bez sezonskog markera koji ipak imaju epizode = druge serije.
    other_series = [
        sub
        for sub in subdirs
        if detect_season(sub.name) is None and _folder_has_episodes(sub)
    ]
    if other_series:
        return False

    titles = {
        _subfolder_series_title(directory, sub) for sub in season_dirs
    }
    if len(titles) != 1:
        return False

    # Jedna serija samo ako su podfolderi čiste sezone („Sezona 1") ili
    # njihov naziv odgovara samom folderu (npr. „His Dark Materials" sa
    # podfolderima „His Dark Materials Sezona 1/2"). U suprotnom je ovo
    # biblioteka sa jednom serijom (naziv se ne sme uzeti iz roditelja).
    all_pure = all(
        is_season_only_folder(sub.name) for sub in season_dirs
    )
    parent_identity = _title_identity(clean_series_title(directory.name))
    return all_pure or next(iter(titles)) == parent_identity


def _folder_has_episodes(directory: Path) -> bool:
    return _episode_count(scan_series_directory(directory)) > 0


def _merge_series(
    title: str,
    directory: Path,
    scans: list[SeriesScanResult],
) -> SeriesScanResult:
    """Spaja više foldera (sezona) iste serije u jedan rezultat."""

    seasons_map: dict[int, list[EpisodeScan]] = {}
    season_names: dict[int, str] = {}
    warnings: list[str] = []
    artwork: list[ArtworkRef] = []
    extras: list[Path] = []

    for scan in scans:
        for season in scan.seasons:
            seasons_map.setdefault(season.season_number, []).extend(
                season.episodes
            )
            if season.name and season.season_number not in season_names:
                season_names[season.season_number] = season.name
        warnings.extend(scan.warnings)
        artwork.extend(scan.artwork)
        extras.extend(scan.extras)

    seasons = tuple(
        SeasonScan(
            season_number=number,
            episodes=tuple(
                sorted(items, key=lambda item: item.episode_number)
            ),
            name=season_names.get(number),
        )
        for number, items in sorted(seasons_map.items())
    )

    poster, backdrop = _representative_artwork(artwork)

    return SeriesScanResult(
        directory=directory,
        title=title,
        seasons=seasons,
        poster_path=poster,
        backdrop_path=backdrop,
        warnings=tuple(warnings),
        artwork=tuple(artwork),
        extras=tuple(sorted(set(extras))),
    )


def _collect_series_subdirs(entries: list[Path]) -> list[Path]:
    """Podfolderi koji su kandidati za serije (preskoči sistemske / $-foldere)."""

    subdirs = []
    for entry in entries:
        name = entry.name.casefold()
        if name in _SKIP_DIRECTORIES or name.startswith("$"):
            continue
        try:
            if entry.is_dir():
                subdirs.append(entry)
        except OSError:
            continue
    return subdirs


def _group_subdirs_by_title(subdirs: list[Path]) -> tuple[dict[str, list[Path]], list[str]]:
    """Grupiši podfoldere po identitetu naziva serije (sezone iste serije zajedno)."""

    groups: dict[str, list[Path]] = {}
    order: list[str] = []
    for entry in subdirs:
        key = _title_identity(clean_series_title(entry.name))
        if key not in groups:
            groups[key] = []
            order.append(key)
        groups[key].append(entry)
    return groups, order


def _scan_series_group(folders: list[Path]) -> list["SeriesScanResult"]:
    """Skeniraj jednu grupu foldera istog naziva: jedan folder → rekurzija
    (razmota kolekcije), više foldera → spoji sezone u jednu seriju."""

    if len(folders) == 1:
        # Jedan folder istog naziva: može biti serija ILI kolekcija
        # više serija (npr. „0 MARVEL", „0NOVO"). Rekurzija razmotava
        # kolekcije u pojedinačne serije, a običnu seriju vraća kao
        # jednu stavku.
        return scan_series_library(folders[0])

    # Više foldera istog naziva = sezone iste serije → spoji u jednu.
    scans = [scan_series_directory(folder) for folder in folders]
    scans = [scan for scan in scans if _episode_count(scan) > 0]

    if not scans:
        return []

    if len(scans) == 1:
        return [scans[0]]
    return [_merge_series(scans[0].title, folders[0], scans)]


def scan_series_library(directory: Path) -> list[SeriesScanResult]:
    """Skenira folder koji može da sadrži VIŠE serija.

    Ako folder sam po sebi izgleda kao jedna serija (epizode direktno u
    njemu ili sezonski podfolderi iste serije), vraća listu sa tom jednom
    serijom. Inače tretira svaki neposredni podfolder kao seriju, a
    podfoldere-sezone istog naziva spaja u jednu seriju.
    """

    directory = Path(directory)

    if not directory.is_dir():
        return []

    # Neki sistemski folderi (npr. „System Volume Information", $RECYCLE.BIN)
    # brane pristup ili nisu deo biblioteke — preskaču se bez rušenja.
    try:
        entries = sorted(directory.iterdir())
    except (PermissionError, OSError):
        return []

    subdirs = _collect_series_subdirs(entries)

    # Sam folder je jedna serija (epizode direktno ili sezone iste serije).
    if _is_single_series(directory, subdirs):
        single = scan_series_directory(directory)
        return [single] if _episode_count(single) > 0 else []

    # Grupiši podfoldere po nazivu serije: sezone iste serije idu zajedno.
    groups, order = _group_subdirs_by_title(subdirs)

    series: list[SeriesScanResult] = []
    for key in order:
        series.extend(_scan_series_group(groups[key]))

    if series:
        return series

    # Rezerva: probaj ceo folder kao jednu seriju.
    single = scan_series_directory(directory)
    return [single] if _episode_count(single) > 0 else []

