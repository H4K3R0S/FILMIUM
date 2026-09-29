"""Pozadinski instalater CORE zavisnosti.

OS-agnostičan: komandu bira SERVER po `installer` tipu zavisnosti (nikad
klijent — klijent šalje samo `key`, zaštita od injection-a):

* PIP  → `sys.executable -m pip install <paket>` — gađa BAŠ interpreter pod
  kojim backend radi (ćelijski venv), pa se paket vidi odmah i ne pada na
  `externally-managed-environment` (venv nije sistemski Python).
* NPM  → `npm install` u `apps/gui` (bez imena paketa u argumentu — usklađuje
  ceo `node_modules` sa već upisanim `package.json`).

Radi jedan posao u jednom trenutku (kao cron), sa statusom za polling iz GUI-ja.
"""

import subprocess
import sys
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from core.foundation.dependencies import (
    CORE_DEPENDENCIES,
    Dependency,
    DependencyInstaller,
)
from core.foundation.paths import core_paths

_MAX_LOG_LINES = 200


# ==========          MODEL POSLA          ==========

@dataclass
class InstallJob:
    """Snimak trenutnog install posla (u memoriji)."""

    key: str | None = None
    status: str = "idle"  # idle | running | done | error
    started_at: str | None = None
    returncode: int | None = None
    log: list[str] = field(default_factory=list)


_JOB = InstallJob()
_THREAD: threading.Thread | None = None
_LOCK = threading.Lock()


def _command_for(dependency: Dependency) -> tuple[list[str], Path]:
    """Vrati (komanda, radni_dir) za auto-instalaciju date zavisnosti.

    Raises:
        KeyError: `installer` tip nema podržanu auto-komandu na ovom OS-u.
    """

    installer = dependency.installer

    if installer is DependencyInstaller.PIP:
        # Ime pip-paketa == `key` za sve PIP zavisnosti u registru
        # (keyring, pillow, deep-translator, requests, rottentomatoes-python,
        # jikanpy, cinemagoer). pip je neosetljiv na velika/mala slova.
        command = [sys.executable, "-m", "pip", "install", dependency.key]
        # Ako backend IPAK radi pod sistemskim Python-om (nije venv), Debian/Kali
        # okruženje je "externally managed" — bez ovoga pip odbija instalaciju.
        # U normalnom radu (ćelijski venv) ova grana se ne aktivira.
        in_venv = sys.prefix != sys.base_prefix
        if not in_venv and not sys.platform.startswith("win"):
            command.append("--break-system-packages")
        return command, core_paths.root

    if installer is DependencyInstaller.NPM:
        return ["npm", "install"], core_paths.apps / "gui"

    # WINGET / PORTABLE_ZIP / NONE nemaju prenosivu auto-komandu ovde.
    raise KeyError(dependency.key)


def _run(command: list[str], cwd: Path) -> None:
    """Izvršava komandu i puni log/returncode."""

    try:
        proc = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            cwd=str(cwd),
        )

        for line in proc.stdout or []:
            _JOB.log.append(line.rstrip("\n"))
            del _JOB.log[:-_MAX_LOG_LINES]

        returncode = proc.wait()
        _JOB.returncode = returncode
        _JOB.status = "done" if returncode == 0 else "error"
    except Exception as error:  # noqa: BLE001 — prijavi bilo koji problem
        _JOB.log.append(f"GREŠKA: {error}")
        _JOB.status = "error"
        _JOB.returncode = -1
    finally:
        if _JOB.status == "done":
            import importlib

            importlib.invalidate_caches()


# ==========          JAVNI API          ==========

def start_install(key: str) -> InstallJob:
    """Pokreće instalaciju za dati ključ. Vraća početni snimak posla.

    Raises:
        KeyError: nepoznat ključ ili ključ bez automatske instalacije.
        RuntimeError: već je pokrenut jedan install posao.
    """

    global _JOB, _THREAD

    dependency = next(
        (item for item in CORE_DEPENDENCIES if item.key == key),
        None,
    )
    if dependency is None or dependency.installer is DependencyInstaller.NONE:
        raise KeyError(key)

    command, cwd = _command_for(dependency)  # KeyError ako tip nije podržan

    with _LOCK:
        if _JOB.status == "running":
            raise RuntimeError("Instalacija je već u toku.")

        _JOB = InstallJob(
            key=key,
            status="running",
            started_at=datetime.now(timezone.utc).isoformat(),
            log=[],
        )
        _THREAD = threading.Thread(
            target=_run,
            args=(command, cwd),
            daemon=True,
        )
        _THREAD.start()

    return _JOB


def get_install_status() -> InstallJob:
    """Vraća trenutni snimak install posla."""

    return _JOB
