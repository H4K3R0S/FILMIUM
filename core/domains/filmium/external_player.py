"""Pokretanje spoljnog plejera (VLC) za reprodukciju bilo kog kodeka.

Najjednostavnije i najpouzdanije rešenje za kodeke koje webview ne podržava
(HEVC, AC3, DTS...): otvori fajl u instaliranom VLC-u. Bez native linkovanja.
"""

import shutil
import subprocess
import sys
from pathlib import Path


def _candidate_is_file(candidate: object) -> bool:
    """Da li kandidat-putanja postoji kao fajl (OSError se tretira kao ne)."""

    try:
        return bool(candidate) and Path(candidate).is_file()
    except OSError:
        return False


def find_vlc() -> str | None:
    """Nalazi VLC izvršni fajl na sistemu (PATH + uobičajene lokacije)."""

    candidates: list[str] = []

    which = shutil.which("vlc")
    if which:
        candidates.append(which)

    if sys.platform.startswith("win"):
        candidates += [
            r"C:\Program Files\VideoLAN\VLC\vlc.exe",
            r"C:\Program Files (x86)\VideoLAN\VLC\vlc.exe",
        ]
    elif sys.platform == "darwin":
        candidates.append("/Applications/VLC.app/Contents/MacOS/VLC")
    else:
        candidates += ["/usr/bin/vlc", "/usr/local/bin/vlc", "/snap/bin/vlc"]

    for candidate in candidates:
        if _candidate_is_file(candidate):
            return candidate

    return None


def vlc_available() -> bool:
    """Da li je VLC dostupan."""

    return find_vlc() is not None


def launch_vlc(video_path: Path, subtitle_path: Path | None = None) -> bool:
    """Pokreće VLC na datom fajlu. Vraća True ako je pokrenut.

    VLC sam pronalazi prevode u istom/„subs" folderu; ``subtitle_path`` se
    prosleđuje eksplicitno kada želimo određeni prevod.
    """

    vlc = find_vlc()
    if vlc is None:
        return False

    args = [vlc, "--play-and-exit", str(video_path)]
    if subtitle_path is not None:
        args += ["--sub-file", str(subtitle_path)]

    try:
        subprocess.Popen(args)
    except OSError:
        return False

    return True
