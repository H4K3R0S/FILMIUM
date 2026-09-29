"""Generisanje sličica (thumbnaila) preko ffmpeg-a.

Primarno PERSISTENTNO u `<video_dir>/.thumb/<ime>_thumb.jpg` (u samoj biblioteci), uz DB-vođenu
detekciju (FILMIUM proverava .thumb; ako fali → ffmpeg napravi). Rezerva: privremeni tmp keš.
Tolerantno: bez ffmpeg-a ili greške → vraća None (pregled radi i bez alata).
"""

import hashlib
import shutil
import subprocess
import tempfile
from pathlib import Path

from core.domains.filmium.media_probe import probe_video_file

_CACHE_DIR = Path(tempfile.gettempdir()) / "filmium_thumbnails"
THUMB_DIRNAME = ".thumb"


def thumb_dir_for(video_path: Path) -> Path:
    """Direktorijum sličica pored videa: <dir>/.thumb (film-dir ili epizode-dir)."""
    return Path(video_path).parent / THUMB_DIRNAME


def thumb_path_for(video_path: Path) -> Path:
    """Persistentna putanja sličice: <dir>/.thumb/<ime>_thumb.jpg."""
    v = Path(video_path)
    return thumb_dir_for(v) / f"{v.stem}_thumb.jpg"


def has_thumbnail(video_path: Path) -> bool:
    """DB-vođena detekcija: da li persistentna sličica već postoji u .thumb."""
    try:
        return thumb_path_for(video_path).is_file()
    except OSError:
        return False


def _cache_path(video_path: Path) -> Path | None:
    try:
        stat = Path(video_path).stat()
    except OSError:
        return None
    key = f"{Path(video_path).resolve(strict=False)}:{stat.st_size}:{int(stat.st_mtime)}"
    return _CACHE_DIR / f"{hashlib.sha1(key.encode('utf-8'), usedforsecurity=False).hexdigest()}.jpg"


def _seek_timestamp(video_path: Path) -> float:
    """Bira trenutak za sličicu (~30% trajanja, podrazumevano 10s)."""
    info = probe_video_file(Path(video_path))
    if info is not None and info.duration_seconds:
        return max(1.0, round(info.duration_seconds * 0.3, 3))
    return 10.0


def _extract_frame(video_path: Path, output: Path, width: int) -> bool:
    """ffmpeg: 1 kadar (~30%, rezerva prvi kadar) → output. True ako uspe."""
    if shutil.which("ffmpeg") is None:
        return False
    try:
        output.parent.mkdir(parents=True, exist_ok=True)
    except OSError:
        return False
    ts = _seek_timestamp(video_path)
    tail = ["-frames:v", "1", "-vf", f"scale={width}:-2", "-y", str(output)]
    for cmd in (
        ["ffmpeg", "-v", "quiet", "-ss", str(ts), "-i", str(video_path), *tail],
        ["ffmpeg", "-v", "quiet", "-i", str(video_path), *tail],
    ):
        try:
            r = subprocess.run(cmd, capture_output=True, timeout=30, check=False)
        except (OSError, subprocess.SubprocessError):
            return False
        if r.returncode == 0 and output.is_file():
            return True
    return False


def ensure_thumbnail(video_path: Path, *, width: int = 480) -> Path | None:
    """Persistentna sličica u <dir>/.thumb/. Postoji → vrati; inače ffmpeg napravi TU.
    Ako .thumb nije upisiv → None (pozivalac može tmp rezervu)."""
    v = Path(video_path)
    out = thumb_path_for(v)
    try:
        if out.is_file():
            return out
    except OSError:
        return None
    return out if _extract_frame(v, out, width) else None


def generate_episode_thumbnail(video_path: Path, *, width: int = 480) -> Path | None:
    """Sličica epizode/videa. Prvo PERSISTENTNO u .thumb (biblioteka), rezerva tmp keš."""
    v = Path(video_path)
    persistent = ensure_thumbnail(v, width=width)
    if persistent is not None:
        return persistent
    # rezerva: tmp keš (kad .thumb nije upisiv, npr. read-only izvor)
    output = _cache_path(v)
    if output is None:
        return None
    if output.is_file():
        return output
    return output if _extract_frame(v, output, width) else None
