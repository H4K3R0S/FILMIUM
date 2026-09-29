from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from core.domains.filmium.library_models import (
    LibraryRootStatus,
    MediaFolderScanResult,
)
from core.domains.filmium.library_scanner import (
    TRAILER_MARKERS,
    VIDEO_EXTENSIONS,
    FilmiumLibraryScanError,
    scan_media_directory,
)
from core.domains.filmium.movie_collection import (
    collection_video_entries,
    is_movie_collection,
)

# Folderi koji predstavljaju sistemske ili pomocne grane, a ne
# zaseban FILMIUM sadrzaj.
SKIPPED_DIRECTORY_NAMES = {
    "$recycle.bin",
    "fanart",
    "system volume information",
    "subtitles",
    "titlovi",
    "wallpaper",
    "wallpapers",
}


# ==========          REZULTAT JEDNOG FOLDERA          ==========

class LibraryCatalogStatus(StrEnum):
    """Odnos pronađenog foldera prema postojećem katalogu."""

    NEW = "new"
    CATALOG_ONLY = "catalog_only"
    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"
    AMBIGUOUS = "ambiguous"


@dataclass(frozen=True)
class LibraryFolderScanEntry:
    """Rezultat skeniranja jednog kandidata iz korena biblioteke."""

    directory: Path
    scan_result: MediaFolderScanResult | None = None
    error_message: str | None = None
    catalog_status: LibraryCatalogStatus = LibraryCatalogStatus.NEW
    matching_media_ids: tuple[int, ...] = ()

    @property
    def can_import(self) -> bool:
        return (
            self.scan_result is not None
            and self.scan_result.can_import
            and self.error_message is None
        )


# ==========          REZULTAT CELE BIBLIOTEKE          ==========

@dataclass(frozen=True)
class LibraryRootScanResult:
    """Pregled svih neposrednih filmskih foldera jedne biblioteke."""

    root: Path
    status: LibraryRootStatus
    entries: tuple[LibraryFolderScanEntry, ...] = ()
    ignored_file_count: int = 0
    warnings: tuple[str, ...] = ()
    discovered_subtitle_count: int = 0
    inspected_subtitle_count: int = 0
    clean_subtitle_count: int = 0
    subtitle_repair_count: int = 0
    queued_subtitle_count: int = 0
    unsupported_subtitle_count: int = 0
    subtitle_scan_warnings: tuple[str, ...] = ()

    @property
    def discovered_count(self) -> int:
        return len(self.entries)

    @property
    def importable_count(self) -> int:
        return sum(entry.can_import for entry in self.entries)

    @property
    def problem_count(self) -> int:
        return self.discovered_count - self.importable_count


# ==========          POMOCNE PROVERE          ==========

def _duplicate_warnings(
    entries: list[LibraryFolderScanEntry],
) -> list[str]:
    identities: dict[tuple[str, int | None, str], list[Path]] = {}

    for entry in entries:
        if entry.scan_result is None:
            continue

        result = entry.scan_result
        identity = (
            result.title.casefold(),
            result.release_year,
            result.manifest.media_type.value,
        )
        identities.setdefault(identity, []).append(entry.directory)

    warnings: list[str] = []

    for directories in identities.values():
        if len(directories) < 2:
            continue

        folder_names = ", ".join(
            directory.name for directory in directories
        )
        warnings.append(
            f"Moguci duplikati FILMIUM sadrzaja: {folder_names}"
        )

    return warnings


# ==========          OTKRIVANJE KANDIDATA          ==========

def _video_is_trailer(path: Path) -> bool:
    tokens = {
        token
        for token in path.stem.casefold()
        .replace("_", " ")
        .replace("-", " ")
        .split()
        if token
    }
    return bool(tokens & TRAILER_MARKERS)


def _is_media_directory(directory: Path) -> bool:
    """Proverava da li folder neposredno predstavlja jedan sadrzaj."""

    if (directory / "filmium_info.json").is_file():
        return True

    try:
        children = directory.iterdir()
    except OSError:
        return False

    return any(
        child.is_file()
        and child.suffix.casefold() in VIDEO_EXTENSIONS
        and not _video_is_trailer(child)
        for child in children
    )


def _discover_media_directories(
    root: Path,
) -> tuple[list[Path], int, list[str]]:
    """Rekurzivno nalazi filmske foldere bez ulaska u njihove resurse."""

    if _is_media_directory(root):
        return [root], 0, []

    candidates: list[Path] = []
    warnings: list[str] = []
    ignored_file_count = 0
    pending = [root]

    while pending:
        current = pending.pop()

        try:
            children = sorted(
                current.iterdir(),
                key=lambda path: path.name.casefold(),
                reverse=True,
            )
        except OSError as error:
            warnings.append(
                f"Folder nije moguce procitati: {current} ({error})"
            )
            continue

        for child in children:
            if child.is_symlink():
                warnings.append(
                    f"Simbolicka veza je preskocena: {child}"
                )
                continue

            if child.is_file():
                ignored_file_count += 1
                continue

            if not child.is_dir():
                continue

            if child.name.casefold() in SKIPPED_DIRECTORY_NAMES:
                continue

            if _is_media_directory(child):
                candidates.append(child)
            else:
                pending.append(child)

    candidates.sort(
        key=lambda path: path.as_posix().casefold()
    )
    return candidates, ignored_file_count, warnings


# ==========          SKENIRANJE KORENA          ==========

def scan_library_root(
    root: Path,
    *,
    enabled: bool = True,
) -> LibraryRootScanResult:
    """Nedestruktivno skenira koren, jedan film ili duboku biblioteku."""

    if not enabled:
        return LibraryRootScanResult(
            root=root,
            status=LibraryRootStatus.DISABLED,
        )

    if not root.exists():
        return LibraryRootScanResult(
            root=root,
            status=LibraryRootStatus.OFFLINE,
            warnings=("Korenski folder biblioteke nije dostupan.",),
        )

    if not root.is_dir():
        return LibraryRootScanResult(
            root=root,
            status=LibraryRootStatus.OFFLINE,
            warnings=("Putanja biblioteke nije folder.",),
        )

    entries: list[LibraryFolderScanEntry] = []
    candidates, ignored_file_count, warnings = (
        _discover_media_directories(root)
    )

    for child in candidates:
        # Kolekcija filmova (npr. „Pirates of the Caribbean"): svaki video
        # fajl je zaseban film → posebna stavka po filmu (identitet = putanja
        # video fajla, da se ne sudaraju ključevi).
        if is_movie_collection(child):
            for entry in collection_video_entries(child):
                try:
                    scan_result = scan_media_directory(
                        child, entry.video_path.name
                    )
                except (FilmiumLibraryScanError, OSError) as error:
                    entries.append(
                        LibraryFolderScanEntry(
                            directory=entry.video_path,
                            error_message=str(error),
                        )
                    )
                    continue
                entries.append(
                    LibraryFolderScanEntry(
                        directory=entry.video_path,
                        scan_result=scan_result,
                    )
                )
            continue

        try:
            scan_result = scan_media_directory(child)
        except FilmiumLibraryScanError as error:
            entries.append(
                LibraryFolderScanEntry(
                    directory=child,
                    error_message=str(error),
                )
            )
            continue
        except OSError as error:
            entries.append(
                LibraryFolderScanEntry(
                    directory=child,
                    error_message=(
                        f"Folder nije moguce procitati: {error}"
                    ),
                )
            )
            continue

        entries.append(
            LibraryFolderScanEntry(
                directory=child,
                scan_result=scan_result,
            )
        )

    warnings.extend(_duplicate_warnings(entries))

    return LibraryRootScanResult(
        root=root,
        status=LibraryRootStatus.AVAILABLE,
        entries=tuple(entries),
        ignored_file_count=ignored_file_count,
        warnings=tuple(warnings),
    )
