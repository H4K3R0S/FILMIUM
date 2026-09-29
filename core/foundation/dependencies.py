"""Registar zavisnosti FILMIUM domena.

Svaki domen/ćelija sam opisuje šta mu treba da radi: Python paketi, Node
okruženje i spoljni alati (npr. ffmpeg/ffprobe). Ovaj registar pokriva
FILMIUM (biblioteka filmova/serija). Koristi ga i "doktor" skripta
(`scripts/check_dependencies.py`) i API koji GUI-ju daje zdravstveni status.
"""

import importlib.util
import shutil
import sys
from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

# Platforma: hintovi na Linux/Kali idu preko apt/pip, ne winget-a. Radi na oba OS-a.
_IS_WINDOWS = sys.platform.startswith("win")


def _hint(windows: str, linux: str) -> str:
    """Vrati install hint prikladan trenutnom OS-u (Windows vs Linux)."""

    return windows if _IS_WINDOWS else linux


def _pip_hint(package: str) -> str:
    """Komanda za pip koja gađa BAŠ interpreter pod kojim app radi (ćelijski
    venv). Kopiranje u terminal ne pada na `externally-managed-environment`
    (Kali/Debian) jer ne koristi sistemski `python`/`python3`, već pun put do
    venv Python-a (`sys.executable`)."""

    return f'"{sys.executable}" -m pip install {package}'


def _installer_for(windows: "DependencyInstaller", linux: "DependencyInstaller") -> "DependencyInstaller":
    """Auto-instaler prikladan trenutnom OS-u. Windows nosi .ps1/winget/portable;
    na Linux-u sistemski alati (mpv/vlc/ffmpeg) idu preko `apt`, koji aplikacija
    NE pokreće kao root — zato NONE (dugme se sakrije), a tačna `apt` komanda se
    prikazuje u `install_hint`-u sa kopiranjem. Tako prozor nudi opciju za BAŠ
    taj sistem (Filmium prvo detektuje OS preko `_IS_WINDOWS`)."""
    return windows if _IS_WINDOWS else linux


# ==========          VRSTE I NIVOI          ==========

class DependencyKind(StrEnum):
    """Odakle dolazi zavisnost i kako se proverava."""

    PYTHON = "python"
    NODE = "node"
    NPM = "npm"
    SYSTEM = "system"


class DependencySeverity(StrEnum):
    """Koliko je zavisnost bitna za rad sistema."""

    CRITICAL = "critical"    # bez ovoga backend/GUI ne rade
    IMPORTANT = "important"  # sistem radi, ali neka funkcija nedostaje
    OPTIONAL = "optional"    # lepo je imati, nije nužno


class DependencyInstaller(StrEnum):
    """Kako se zavisnost automatski instalira preko INSTALL dugmeta."""

    PIP = "pip"                    # Python paket preko pip-a
    NPM = "npm"                    # GUI paket preko `npm install` u apps/gui
    WINGET = "winget"              # Windows paket preko winget-a
    PORTABLE_ZIP = "portable_zip"  # download release zip + raspakuj u bin/
    NONE = "none"                  # nema automatske instalacije


# ==========          MODEL ZAVISNOSTI          ==========

@dataclass(frozen=True)
class Dependency:
    """Jedna zavisnost i način na koji se proverava/instalira."""

    key: str
    label: str
    kind: DependencyKind
    severity: DependencySeverity
    # Python: ime za import; NPM: ime paketa iz package.json;
    # Node/System: ime izvršnog fajla na PATH-u.
    probe: str
    purpose: str
    install_hint: str
    installer: DependencyInstaller = DependencyInstaller.NONE
    # Ako je zadato, koristi se umesto provere po `kind` (npr. VLC/mpv).
    probe_fn: Callable[[], bool] | None = None


@dataclass(frozen=True)
class DependencyStatus:
    """Rezultat provere jedne zavisnosti."""

    dependency: Dependency
    installed: bool


# ==========          POSEBNE PROVERE          ==========

def npm_package_installed(
    package: str,
    gui_root: Path | None = None,
) -> bool:
    """Proverava da li je npm paket raspakovan u `apps/gui/node_modules`.

    npm paket nije izvršni fajl na PATH-u, nego folder sa svojim
    `package.json`. Zato se ne sme proveravati preko `shutil.which`.

    Args:
        package: Ime paketa iz `package.json`, uključujući scope
            (npr. `monaco-editor` ili `@xterm/xterm`).
        gui_root: Opcioni koren GUI aplikacije. Koristi se u testovima.
    """

    if gui_root is None:
        from core.foundation.paths import core_paths

        gui_root = core_paths.apps / "gui"

    # Scoped ime (`@xterm/xterm`) se prirodno razrešava u ugnežđen folder.
    manifest = gui_root / "node_modules" / Path(package) / "package.json"

    return manifest.is_file()


def _vlc_installed() -> bool:
    """VLC preko PATH-a i uobičajenih instalacionih putanja."""

    from core.domains.filmium.external_player import find_vlc

    return find_vlc() is not None


def _mpv_installed() -> bool:
    """mpv: na Windows portable bin/mpv.exe, na Linux sistemski mpv (PATH) ili bin/mpv."""

    if not _IS_WINDOWS:
        from core.foundation.paths import core_paths

        return shutil.which("mpv") is not None or (core_paths.root / "bin" / "mpv").is_file()

    from core.foundation.paths import core_paths

    return (core_paths.root / "bin" / "mpv.exe").is_file()


# ==========          REGISTAR ZAVISNOSTI          ==========

DOMAIN_DEPENDENCIES: tuple[Dependency, ...] = (
    Dependency(
        key="fastapi",
        label="FastAPI",
        kind=DependencyKind.PYTHON,
        severity=DependencySeverity.CRITICAL,
        probe="fastapi",
        purpose="Backend API sloj CORE sistema.",
        install_hint=_pip_hint("-r requirements.txt"),
    ),
    Dependency(
        key="uvicorn",
        label="Uvicorn",
        kind=DependencyKind.PYTHON,
        severity=DependencySeverity.CRITICAL,
        probe="uvicorn",
        purpose="ASGI server koji pokreće backend.",
        install_hint=_pip_hint("-r requirements.txt"),
    ),
    Dependency(
        key="python-multipart",
        label="python-multipart",
        kind=DependencyKind.PYTHON,
        severity=DependencySeverity.CRITICAL,
        probe="multipart",
        purpose="Upload fajlova i form podaci u FastAPI rutama.",
        install_hint=_pip_hint("python-multipart"),
    ),
    Dependency(
        key="node",
        label="Node.js",
        kind=DependencyKind.NODE,
        severity=DependencySeverity.IMPORTANT,
        probe="node",
        purpose="Pokretanje i build GUI-ja (Vite/Tauri).",
        install_hint=_hint("Instaliraj Node.js LTS sa https://nodejs.org", "sudo apt install -y nodejs npm"),
    ),
    Dependency(
        key="ffprobe",
        label="FFmpeg (ffprobe)",
        kind=DependencyKind.SYSTEM,
        severity=DependencySeverity.IMPORTANT,
        probe="ffprobe",
        purpose="Tačna rezolucija, kodek i FPS videa pri uvozu.",
        install_hint=_hint("winget install Gyan.FFmpeg", "sudo apt install -y ffmpeg"),
    ),
    Dependency(
        key="watchdog",
        label="watchdog",
        kind=DependencyKind.PYTHON,
        severity=DependencySeverity.IMPORTANT,
        probe="watchdog",
        purpose="Automatsko praćenje foldera (FILMIUM auto-import).",
        install_hint=_pip_hint("watchdog"),
    ),
    Dependency(
        key="qbittorrent-api",
        label="qbittorrent-api",
        kind=DependencyKind.PYTHON,
        severity=DependencySeverity.OPTIONAL,
        probe="qbittorrentapi",
        purpose="Torrent modul FILMIUM-a (veza sa qBittorrent Web UI-jem).",
        install_hint=_pip_hint("qbittorrent-api"),
    ),
    Dependency(
        key="psutil",
        label="psutil",
        kind=DependencyKind.PYTHON,
        severity=DependencySeverity.IMPORTANT,
        probe="psutil",
        purpose="Detekcija priključenih diskova (USB) u System Layer-u.",
        install_hint=_pip_hint("psutil"),
    ),
    Dependency(
        key="pillow",
        label="Pillow",
        kind=DependencyKind.PYTHON,
        severity=DependencySeverity.IMPORTANT,
        probe="PIL",
        purpose="Obrada slika (posteri, thumbnail-ovi, dimenzije).",
        install_hint=_pip_hint("Pillow"),
        installer=DependencyInstaller.PIP,
    ),
    Dependency(
        key="deep-translator",
        label="deep-translator",
        kind=DependencyKind.PYTHON,
        severity=DependencySeverity.IMPORTANT,
        probe="deep_translator",
        purpose="Prevod prevoda/opisa (titlovi, lokalizacija).",
        install_hint=_pip_hint("deep-translator"),
        installer=DependencyInstaller.PIP,
    ),
    Dependency(
        key="vlc",
        label="VLC",
        kind=DependencyKind.SYSTEM,
        severity=DependencySeverity.OPTIONAL,
        probe="vlc",
        purpose="Spoljni plejer za kodeke koje webview ne podržava.",
        install_hint=_hint("winget install VideoLAN.VLC", "sudo apt install -y vlc"),
        installer=_installer_for(DependencyInstaller.WINGET, DependencyInstaller.NONE),
        probe_fn=_vlc_installed,
    ),
    Dependency(
        key="mpv",
        label=_hint("mpv (portable)", "mpv"),
        kind=DependencyKind.SYSTEM,
        severity=DependencySeverity.OPTIONAL,
        probe="mpv",
        purpose="Plejer sa overlay-om (Windows: bin/mpv.exe; Linux: sistemski mpv).",
        install_hint=_hint("INSTALL dugme preuzima portable mpv u bin/", "sudo apt install -y mpv libmpv2"),
        installer=_installer_for(DependencyInstaller.PORTABLE_ZIP, DependencyInstaller.NONE),
        probe_fn=_mpv_installed,
    ),
    Dependency(
        key="keyring",
        label="keyring",
        kind=DependencyKind.PYTHON,
        severity=DependencySeverity.IMPORTANT,
        probe="keyring",
        purpose="Bezbedno čuvanje API ključeva u OS keychain-u (Credential Manager).",
        install_hint=_pip_hint("keyring"),
        installer=DependencyInstaller.PIP,
    ),
    Dependency(
        key="requests",
        label="requests",
        kind=DependencyKind.PYTHON,
        severity=DependencySeverity.IMPORTANT,
        probe="requests",
        purpose="HTTP klijent za spoljno obogaćivanje (TVmaze, Jikan).",
        install_hint=_pip_hint("requests"),
        installer=DependencyInstaller.PIP,
    ),
    Dependency(
        key="rottentomatoes-python",
        label="Rotten Tomatoes",
        kind=DependencyKind.PYTHON,
        severity=DependencySeverity.OPTIONAL,
        probe="rottentomatoes",
        purpose="Ocene kritičara/publike (Tomatometer, Audience) za filmove.",
        install_hint=_pip_hint("rottentomatoes-python"),
        installer=DependencyInstaller.PIP,
    ),
    Dependency(
        key="jikanpy",
        label="Jikan (MyAnimeList)",
        kind=DependencyKind.PYTHON,
        severity=DependencySeverity.OPTIONAL,
        probe="jikanpy",
        purpose="Anime/manga podaci (MAL ocena, studio, epizode).",
        install_hint=_pip_hint("jikanpy"),
        installer=DependencyInstaller.PIP,
    ),
    Dependency(
        key="cinemagoer",
        label="IMDb (Cinemagoer)",
        kind=DependencyKind.PYTHON,
        severity=DependencySeverity.OPTIONAL,
        probe="imdb",
        purpose="IMDb ocene i glasovi za filmove/serije.",
        install_hint=_pip_hint("cinemagoer"),
        installer=DependencyInstaller.PIP,
    ),
)

# Back-compat alias: stariji uvoznici (npr. core/foundation/installer.py) i
# dalje traže `CORE_DEPENDENCIES`. Ovaj fajl je sada domen-skopiran registar
# (svaki domen/ćelija sam sebe opisuje), ali alias štiti postojeće uvoze.
CORE_DEPENDENCIES = DOMAIN_DEPENDENCIES


# ==========          PROVERA          ==========

def check_dependency(dependency: Dependency) -> bool:
    """Vraća True ako je zavisnost dostupna u trenutnom okruženju."""

    if dependency.probe_fn is not None:
        try:
            return dependency.probe_fn()
        except Exception:  # noqa: BLE001
            return False

    if dependency.kind is DependencyKind.PYTHON:
        try:
            return importlib.util.find_spec(dependency.probe) is not None
        except (ImportError, ValueError):
            return False

    if dependency.kind is DependencyKind.NPM:
        return npm_package_installed(dependency.probe)

    # Node i sistemski alati se traže kao izvršni fajl na PATH-u.
    return shutil.which(dependency.probe) is not None


def evaluate_dependencies(
    dependencies: tuple[Dependency, ...] = DOMAIN_DEPENDENCIES,
) -> tuple[DependencyStatus, ...]:
    """Proverava sve zavisnosti i vraća njihov status."""

    return tuple(
        DependencyStatus(
            dependency=dependency,
            installed=check_dependency(dependency),
        )
        for dependency in dependencies
    )


def overall_status(
    statuses: tuple[DependencyStatus, ...],
) -> str:
    """Sažima najveći nivo problema: "critical", "warning" ili "ok"."""

    missing = [status for status in statuses if not status.installed]

    if any(
        status.dependency.severity is DependencySeverity.CRITICAL
        for status in missing
    ):
        return "critical"

    if missing:
        return "warning"

    return "ok"
