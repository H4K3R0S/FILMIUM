"""Otvara sistemski menadžer fajlova na lokaciji datog fajla.

Windows: Explorer sa selektovanim fajlom; macOS: Finder (open -R);
Linux: otvara roditeljski folder (xdg-open). Tolerantno — vraća ``False``
ako alat nije dostupan ili poziv ne uspe, umesto da baca grešku.

Nijedan poziv NE ČEKA da se menadžer fajlova zatvori. Ove funkcije se zovu
iz sinhronih API ruta, koje rade na deljenom threadpool-u: `subprocess.run`
bi na Windows-u umeo da drži radnika dok Explorer živi i tako, posle par
klikova, zaglavi ceo CORE API.
"""

import os
import subprocess
import sys
from pathlib import Path

# Pokrenut proces ne sme da visi o CORE-u niti da otvori konzolu.
_WINDOWS_FLAGS = 0
if sys.platform.startswith("win"):  # pragma: no cover — grana po platformi
    _WINDOWS_FLAGS = (
        getattr(subprocess, "DETACHED_PROCESS", 0)
        | getattr(subprocess, "CREATE_NO_WINDOW", 0)
    )


def _spawn(command: list[str]) -> bool:
    """Pušta komandu i odmah se vraća; ne čeka njen kraj."""

    try:
        subprocess.Popen(
            command,
            close_fds=True,
            creationflags=_WINDOWS_FLAGS,
        )
        return True
    except (OSError, ValueError, subprocess.SubprocessError):
        return False


def reveal_in_file_manager(path: Path) -> bool:
    """Otkriva fajl u sistemskom menadžeru fajlova. Vraća uspeh."""

    path = Path(path)
    if not path.exists():
        return False

    if sys.platform.startswith("win"):
        # Explorer sa selektovanim fajlom.
        return _spawn(["explorer", f"/select,{path}"])

    if sys.platform == "darwin":
        return _spawn(["open", "-R", str(path)])

    # Linux i ostali — otvori roditeljski folder.
    target = path if path.is_dir() else path.parent
    return _spawn(["xdg-open", str(target)])


def open_folder(path: Path) -> bool:
    """Otvara sam folder u sistemskom menadžeru fajlova. Vraća uspeh.

    Razlika u odnosu na :func:`reveal_in_file_manager`: tamo se otvara
    RODITELJ sa selektovanom stavkom, a ovde se ulazi u sam folder — što je
    ono što korisnik očekuje od „otvori direktorijum".
    """

    path = Path(path)
    if not path.is_dir():
        return False

    if sys.platform.startswith("win"):
        # `os.startfile` je Windows poziv koji se odmah vraća; Explorer
        # nastavlja da živi sam za sebe.
        try:
            os.startfile(str(path))
            return True
        except OSError:
            return False

    if sys.platform == "darwin":
        return _spawn(["open", str(path)])

    return _spawn(["xdg-open", str(path)])
