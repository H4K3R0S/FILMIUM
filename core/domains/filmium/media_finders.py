"""Namenski finderi datoteka u folderu sadržaja (video / prevodi).

Odvojene, deljene funkcije koje koriste i uvoz i osvežavanje biblioteke.
Prevodi se traže i u pod-folderima sa uobičajenim imenima (subs, titlovi...),
jer korisnici drže prevode odvojeno od videa.
"""

from pathlib import Path

from core.domains.filmium.subtitle_language import resolve_subtitle_language

VIDEO_EXTENSIONS = {
    ".mp4",
    ".mkv",
    ".avi",
    ".m4v",
    ".mov",
    ".webm",
    ".ts",
    ".m2ts",
    ".wmv",
    ".flv",
    ".mpg",
    ".mpeg",
    ".vob",
    ".ogv",
    ".ogm",
    ".divx",
    ".3gp",
    ".rmvb",
}

SUBTITLE_EXTENSIONS = {
    ".srt",
    ".vtt",
    ".sub",
    ".ass",
    ".ssa",
    ".smi",
}

# Imena pod-foldera u kojima se često drže prevodi.
SUBTITLE_DIR_NAMES = {
    "sub",
    "subs",
    "subtitle",
    "subtitles",
    "titl",
    "titlovi",
    "prevod",
    "prevodi",
    "prijevod",
    "prijevodi",
}

_SKIP_DIR_NAMES = {
    "system volume information",
    "$recycle.bin",
    "extras",
    "featurettes",
}


def _iter_dir(directory: Path):
    try:
        return sorted(directory.iterdir())
    except OSError:
        return []


def find_video_files(directory: Path) -> list[Path]:
    """Vraća video fajlove u folderu (i jednom nivou pod-foldera)."""

    directory = Path(directory)
    videos: list[Path] = []

    for entry in _iter_dir(directory):
        try:
            if entry.is_file() and entry.suffix.lower() in VIDEO_EXTENSIONS:
                videos.append(entry)
            elif entry.is_dir():
                name = entry.name.casefold()
                if name in _SKIP_DIR_NAMES or name.startswith("$"):
                    continue
                for sub in _iter_dir(entry):
                    if (
                        sub.is_file()
                        and sub.suffix.lower() in VIDEO_EXTENSIONS
                    ):
                        videos.append(sub)
        except OSError:
            continue

    return videos


def find_subtitle_files(
    directory: Path,
    max_depth: int = 3,
) -> list[Path]:
    """Vraća prevode u folderu i pod-folderima (subs/titlovi/...)."""

    directory = Path(directory)
    found: list[Path] = []

    def walk(current: Path, depth: int) -> None:
        for entry in _iter_dir(current):
            try:
                if entry.is_file():
                    if entry.suffix.lower() in SUBTITLE_EXTENSIONS:
                        found.append(entry)
                elif entry.is_dir() and depth > 0:
                    name = entry.name.casefold()
                    if name in _SKIP_DIR_NAMES or name.startswith("$"):
                        continue
                    walk(entry, depth - 1)
            except OSError:
                continue

    walk(directory, max_depth)
    return found


def subtitle_language(path: Path) -> str | None:
    """Prepoznaje jezik prevoda (naziv → ISO → sadržaj)."""

    try:
        return resolve_subtitle_language(Path(path))
    except Exception:  # noqa: BLE001
        return None
