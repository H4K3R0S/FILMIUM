"""Organizacija serije na disku u standardnu FILMIUM strukturu.

Cilj:
    <biblioteka>/<Ime serije>/Sezona N/E01 - <Naziv>.ext
    - titlovi: <biblioteka>/<Ime serije>/Sezona N/subs/E01 - <Naziv>.<kod>.srt
    - slike na nivou serije (poster, backdrop)

Kada naziv sezone nije prepoznat pri skeniranju (podrazumevano 1), sezona
se i dalje čuva kao „Sezona 1"; posebno označavanje nepoznate sezone stiže
uz proširenje skenera (placeholder koji se lako menja u kolekciji).
"""

import re
import shutil
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from core.domains.filmium.series_scanner import (
    OSTALO_FOLDERS,
    SeriesScanResult,
)

_ILLEGAL_CHARS = re.compile(r'[<>:"/\\|?*]')


# ==========          MODELI          ==========

@dataclass(frozen=True)
class SeriesMoveAction:
    source: Path
    destination: Path


@dataclass(frozen=True)
class SeriesOrganizationPlan:
    series_title: str
    target_directory: Path
    directories: tuple[Path, ...]
    actions: tuple[SeriesMoveAction, ...]
    warnings: tuple[str, ...]


@dataclass(frozen=True)
class SeriesOrganizationResult:
    target_directory: Path
    moved_file_count: int
    warnings: tuple[str, ...]


# ==========          POMOĆNE FUNKCIJE          ==========

def _safe_name(name: str) -> str:
    cleaned = _ILLEGAL_CHARS.sub("", name).strip().rstrip(". ")
    return cleaned or "Serija"


def _season_folder(season: int) -> str:
    return f"Sezona {season}"


def _episode_base(episode: int, title: str | None) -> str:
    """Naziv epizode: „E01 - Naslov" ili „E01" kada nema naslova."""

    base = f"E{episode:02d}"

    if title:
        base = f"{base} - {_safe_name(title)}"

    return base


# ==========          PLAN          ==========

def plan_series_organization(
    scan: SeriesScanResult,
    library_root: Path,
) -> SeriesOrganizationPlan:
    """Pravi plan premeštanja bez ikakve izmene filesystema."""

    library_root = Path(library_root)
    series_title = _safe_name(scan.title)
    series_dir = library_root / series_title

    directories: list[Path] = [series_dir]
    actions: list[SeriesMoveAction] = []
    warnings: list[str] = list(scan.warnings)

    # Slike: poster „<Ime> S01" (cela serija „<Ime> - poster"),
    # backdrop „S01_back_01", wallpaper „S01_wall_01", fanart „S01_fanart_01".
    counters: dict[tuple[str, int], int] = {}
    for art in scan.artwork:
        ext = art.path.suffix
        season = art.season if art.season is not None else 1

        if art.kind == "poster":
            if art.season is None:
                name = f"{series_title} - poster{ext}"
            else:
                name = f"{series_title} S{art.season:02d}{ext}"
        else:
            code = {
                "backdrop": "back",
                "wallpaper": "wall",
                "fanart": "fanart",
            }.get(art.kind)
            if code is None:
                continue
            key = (code, season)
            counters[key] = counters.get(key, 0) + 1
            name = f"S{season:02d}_{code}_{counters[key]:02d}{ext}"

        actions.append(SeriesMoveAction(art.path, series_dir / name))

    for season in scan.seasons:
        season_dir = series_dir / _season_folder(season.season_number)
        directories.append(season_dir)
        subs_dir = season_dir / "subs"
        subs_dir_added = False

        for episode in season.episodes:
            base = _episode_base(episode.episode_number, episode.title)

            actions.append(
                SeriesMoveAction(
                    episode.video_path,
                    season_dir / f"{base}{episode.video_path.suffix}",
                )
            )

            # Svi prevodi epizode idu u svoj folder po epizodi:
            # „subs/E01 - Naslov/E01 - Naslov.<jezik>.srt". Naziv zadržava
            # E-prefiks da ih plejer mapira po broju epizode.
            episode_subs_dir = subs_dir / base

            language_counts: dict[str, int] = {}
            for subtitle in episode.subtitles:
                if not subs_dir_added:
                    directories.append(subs_dir)
                    subs_dir_added = True
                if episode_subs_dir not in directories:
                    directories.append(episode_subs_dir)

                language = subtitle.language or "und"
                language_counts[language] = (
                    language_counts.get(language, 0) + 1
                )
                occurrence = language_counts[language]
                suffix = (
                    language
                    if occurrence == 1
                    else f"{language}-{occurrence}"
                )

                actions.append(
                    SeriesMoveAction(
                        subtitle.path,
                        episode_subs_dir
                        / f"{base}.{suffix}{subtitle.path.suffix}",
                    )
                )

    # Extras: Movies/Bonus/Prevod… i beleške → <Ime serije>/Extras/…
    for entry in scan.extras:
        entry_actions, entry_dirs = _extra_actions(entry, series_dir)
        actions.extend(entry_actions)
        directories.extend(entry_dirs)

    return SeriesOrganizationPlan(
        series_title=series_title,
        target_directory=series_dir,
        directories=tuple(directories),
        actions=tuple(actions),
        warnings=tuple(warnings),
    )


def _extra_actions(
    entry: Path,
    series_dir: Path,
) -> tuple[list[SeriesMoveAction], list[Path]]:
    """Premešta jednu extra stavku (folder ili fajl) u „Extras".

    Radni/originalni prevodi i beleške idu u „Extras/ostalo"; ostali
    dodaci (Movies, Bonus, Extras…) čuvaju svoj naziv u „Extras/<naziv>".
    """

    extras_root = series_dir / "Extras"
    actions: list[SeriesMoveAction] = []
    directories: list[Path] = [extras_root]

    if entry.is_file():
        destination = extras_root / "ostalo" / entry.name
        directories.append(destination.parent)
        actions.append(SeriesMoveAction(entry, destination))
        return actions, directories

    if entry.name.casefold() in OSTALO_FOLDERS:
        base = extras_root / "ostalo" / entry.name
    else:
        base = extras_root / entry.name

    directories.append(base)

    for file_path in sorted(entry.rglob("*")):
        if not file_path.is_file():
            continue
        destination = base / file_path.relative_to(entry)
        directories.append(destination.parent)
        actions.append(SeriesMoveAction(file_path, destination))

    return actions, directories


# ==========          IZVRŠENJE          ==========

_COPY_CHUNK = 1024 * 1024  # 1 MiB


def _move_file(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)

    try:
        source.replace(destination)
    except OSError:
        # Preko diskova rename ne radi → kopiraj pa obriši.
        shutil.move(str(source), str(destination))


def _move_file_progress(
    source: Path,
    destination: Path,
    report: Callable[[int, int], None],
) -> None:
    """Kao ``_move_file``, ali javlja byte-progres tekućeg fajla."""

    destination.parent.mkdir(parents=True, exist_ok=True)

    try:
        total = source.stat().st_size
    except OSError:
        total = 0

    try:
        source.replace(destination)
        report(total, total)
        return
    except OSError:
        pass

    try:
        copied = 0
        with source.open("rb") as reader, destination.open("wb") as writer:
            while True:
                chunk = reader.read(_COPY_CHUNK)
                if not chunk:
                    break
                writer.write(chunk)
                copied += len(chunk)
                report(copied, total)

        shutil.copystat(str(source), str(destination))
        source.unlink()
    except OSError:
        try:
            destination.unlink(missing_ok=True)
        except OSError:
            pass
        raise

    report(total, total)


def execute_series_organization(
    plan: SeriesOrganizationPlan,
    *,
    confirmed: bool = False,
    on_progress: Callable[[int, int, int, int], None] | None = None,
) -> SeriesOrganizationResult:
    """
    Primenjuje plan samo uz jasnu potvrdu; radi best-effort po fajlu.

    ``on_progress(fajlova_gotovo, fajlova_ukupno, bajtova_gotovo,
    bajtova_ukupno)`` — byte-progres tekućeg fajla + završetak svakog
    fajla. Greška u callback-u ne ruši uvoz.
    """

    if not confirmed:
        raise ValueError("Organizacija serije nije eksplicitno potvrđena.")

    warnings: list[str] = list(plan.warnings)

    for directory in plan.directories:
        directory.mkdir(parents=True, exist_ok=True)

    total_moves = len(plan.actions)

    def _report(files_done: int, file_done: int, file_total: int) -> None:
        if on_progress is None:
            return
        try:
            on_progress(files_done, total_moves, file_done, file_total)
        except Exception:  # noqa: BLE001, S110
            pass

    moved = 0
    for action in plan.actions:
        if not action.source.is_file():
            warnings.append(
                f"Izvorni fajl nije pronađen: {action.source.name}"
            )
            continue

        if action.destination.exists():
            warnings.append(
                f"Odredište već postoji, preskočeno: {action.destination.name}"
            )
            continue

        try:
            completed = moved
            _move_file_progress(
                action.source,
                action.destination,
                lambda done, total, completed=completed: _report(completed, done, total),
            )
            moved += 1
        except OSError as error:
            warnings.append(
                f"Premeštanje nije uspelo ({action.source.name}): {error}"
            )

    return SeriesOrganizationResult(
        target_directory=plan.target_directory,
        moved_file_count=moved,
        warnings=tuple(warnings),
    )


# ==========          ČIŠĆENJE IZVORA          ==========

def cleanup_source_directory(
    source_directory: Path,
    *,
    keep: Path | None = None,
) -> tuple[int, int]:
    """
    Briše ostatke izvornog foldera posle uspešnog uvoza serije.

    Uklanja sve ``.bak`` fajlove (backup prevoda), zatim prazne
    poddirektorijume odozdo naviše i na kraju sam izvorni folder ako je
    ostao prazan. Direktorijum sa stvarnim fajlovima se NE briše (bez
    gubitka podataka). Tolerantno: greške se ignorišu — uvoz je već
    uspeo. ``keep`` (npr. odredište) i njegov podstablo se nikada ne diraju.

    Vraća ``(obrisano_bak, obrisano_dir)``.
    """

    source = Path(source_directory)
    if not source.is_dir():
        return (0, 0)

    keep_resolved = keep.resolve(strict=False) if keep is not None else None

    def _is_protected(path: Path) -> bool:
        if keep_resolved is None:
            return False
        resolved = path.resolve(strict=False)
        return resolved == keep_resolved or keep_resolved in resolved.parents

    removed_bak = 0
    removed_dirs = 0

    # 1) Obriši .bak fajlove bilo gde ispod izvora.
    for file_path in source.rglob("*"):
        if not file_path.is_file():
            continue
        if file_path.suffix.casefold() != ".bak":
            continue
        if _is_protected(file_path):
            continue
        try:
            file_path.unlink()
            removed_bak += 1
        except OSError:
            pass

    # 2) Ukloni prazne direktorijume odozdo naviše.
    directories = sorted(
        (p for p in source.rglob("*") if p.is_dir()),
        key=lambda p: len(p.parts),
        reverse=True,
    )
    for directory in directories:
        if _is_protected(directory):
            continue
        try:
            directory.rmdir()  # uspeva samo ako je prazan
            removed_dirs += 1
        except OSError:
            pass

    # 3) Na kraju sam izvorni folder ako je ostao prazan.
    if not _is_protected(source):
        try:
            source.rmdir()
            removed_dirs += 1
        except OSError:
            pass

    return (removed_bak, removed_dirs)
