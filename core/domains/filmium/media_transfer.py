"""Prenos (kopiranje) FILMIUM sadržaja na drugi disk/folder.

Namerno tolerantan: nedostupan disk ili fajl ne ruši aplikaciju.
Fajlovi se uvek KOPIRAJU (shutil.copy2), original ostaje netaknut.
"""

import os
import shutil
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

_CHUNK_SIZE = 1024 * 1024


# ==========          MODELI          ==========

@dataclass(frozen=True)
class DiskInfo:
    """Jedan dostupan disk/particija sa slobodnim prostorom."""

    path: str
    label: str
    total_bytes: int
    free_bytes: int


@dataclass(frozen=True)
class DirectoryEntry:
    """Jedan pod-folder za navigaciju pri izboru odredišta."""

    name: str
    path: str


@dataclass(frozen=True)
class TransferResult:
    """Rezultat kopiranja: broj fajlova, bajtova i odredišna putanja."""

    copied_files: int
    total_bytes: int
    destination: str


# ==========          DISKOVI          ==========

def list_available_disks() -> tuple[DiskInfo, ...]:
    """Vraća dostupne diskove/particije sa ukupnim i slobodnim prostorom."""

    disks: list[DiskInfo] = []

    if os.name == "nt":
        for letter in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
            root = f"{letter}:\\"
            if not os.path.exists(root):
                continue
            try:
                usage = shutil.disk_usage(root)
            except OSError:
                continue
            disks.append(
                DiskInfo(
                    path=root,
                    label=f"{letter}:",
                    total_bytes=usage.total,
                    free_bytes=usage.free,
                )
            )
        return tuple(disks)

    seen: set[str] = set()
    for mount in ("/", "/mnt", "/media", str(Path.home())):
        if not os.path.isdir(mount) or mount in seen:
            continue
        seen.add(mount)
        try:
            usage = shutil.disk_usage(mount)
        except OSError:
            continue
        disks.append(
            DiskInfo(
                path=mount,
                label=mount,
                total_bytes=usage.total,
                free_bytes=usage.free,
            )
        )
    return tuple(disks)


# ==========          NAVIGACIJA FOLDERA (za izbor odredišta)          ==========

def browse_directory(path: str | None) -> tuple[str | None, tuple[DirectoryEntry, ...]]:
    """
    Vraća (roditelj, pod-folderi) za dati folder. Kada je ``path`` prazan,
    vraća korene diskova. Fajlovi se ne prikazuju — biramo samo folder.
    """

    if not path:
        roots = tuple(
            DirectoryEntry(name=disk.label, path=disk.path)
            for disk in list_available_disks()
        )
        return None, roots

    directory = Path(path)
    if not directory.is_dir():
        return None, ()

    entries: list[DirectoryEntry] = []
    try:
        for child in sorted(
            directory.iterdir(), key=lambda item: item.name.lower()
        ):
            if child.is_dir():
                entries.append(
                    DirectoryEntry(name=child.name, path=str(child))
                )
    except OSError:
        return None, ()

    parent = str(directory.parent) if directory.parent != directory else None
    return parent, tuple(entries)


# ==========          KLASIFIKACIJA FAJLOVA          ==========

_VIDEO_EXTENSIONS = frozenset({
    ".mkv", ".mp4", ".avi", ".mov", ".m4v", ".wmv", ".flv",
    ".webm", ".mpg", ".mpeg", ".ts", ".m2ts",
})
_SUBTITLE_EXTENSIONS = frozenset({
    ".srt", ".ass", ".ssa", ".vtt", ".sub", ".idx",
})
_IMAGE_EXTENSIONS = frozenset({
    ".jpg", ".jpeg", ".png", ".webp", ".bmp", ".gif",
})


def classify_transfer_role(relative_path: str) -> str:
    """Grupa fajla za stablo prenosa: video / subtitle / image / other."""

    extension = os.path.splitext(relative_path)[1].lower()
    if extension in _VIDEO_EXTENSIONS:
        return "video"
    if extension in _SUBTITLE_EXTENSIONS:
        return "subtitle"
    if extension in _IMAGE_EXTENSIONS:
        return "image"
    return "other"


# ==========          ENUMERACIJA          ==========

def enumerate_relative_files(source_directory: Path) -> tuple[str, ...]:
    """
    Vraća sve fajlove ispod ``source_directory`` kao relativne POSIX
    putanje (za kopiranje CELOG direktorijuma). Ako folder ne postoji,
    vraća prazno.
    """

    if not source_directory.is_dir():
        return ()

    files: list[str] = []
    for current_root, _dirs, names in os.walk(source_directory):
        root_path = Path(current_root)
        for name in names:
            relative = (root_path / name).relative_to(source_directory)
            files.append(relative.as_posix())

    return tuple(sorted(files))


# ==========          KOPIRANJE          ==========

def copy_media_files(
    source_directory: Path,
    relative_paths: tuple[str, ...],
    destination_directory: Path,
    on_progress: Callable[[int, int, int, int], None] | None = None,
) -> TransferResult:
    """
    Kopira izabrane fajlove iz ``source_directory`` u
    ``destination_directory`` uz očuvanje strukture. Original ostaje.

    ``on_progress(fajlova_gotovo, fajlova_ukupno, bajtova_gotovo,
    bajtova_ukupno)`` se poziva u toku kopiranja (za progres bar).
    """

    destination_directory.mkdir(parents=True, exist_ok=True)

    files_total = len(relative_paths)
    copied = 0
    total = 0

    for relative in relative_paths:
        parts = Path(relative).parts
        if not parts:
            continue
        source_path = source_directory.joinpath(*parts)
        if not source_path.is_file():
            if on_progress is not None:
                on_progress(copied, files_total, 0, 0)
            continue

        destination_path = destination_directory.joinpath(*parts)
        destination_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            size = source_path.stat().st_size
        except OSError:
            size = 0

        try:
            copied_bytes = 0
            with (
                open(source_path, "rb") as source_file,
                open(destination_path, "wb") as target_file,
            ):
                while True:
                    chunk = source_file.read(_CHUNK_SIZE)
                    if not chunk:
                        break
                    target_file.write(chunk)
                    copied_bytes += len(chunk)
                    if on_progress is not None:
                        on_progress(copied, files_total, copied_bytes, size)
            shutil.copystat(source_path, destination_path)
        except OSError:
            continue

        copied += 1
        total += size
        if on_progress is not None:
            on_progress(copied, files_total, size, size)

    return TransferResult(
        copied_files=copied,
        total_bytes=total,
        destination=str(destination_directory),
    )
