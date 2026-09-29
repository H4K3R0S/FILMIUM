"""Sopstveni `.venv` sklopljene ćelije.

Ćelija ne sme da radi na sistemskom (ili CORE) Python-u — `requirements.txt`
(Task 1) navodi tačno šta joj treba, ali te pakete niko ne instalira dok
ćelija ne dobije SVOJ virtuelni environment. `.venv` je korisnički prostor
ćelije: nije u `GENERATED_ON_UPDATE` (core/cell/build.py) i `--update` ga
nikad ne dira. Ovaj modul ga pravi/ažurira, na osnovu otiska (SHA-256)
`requirements.txt`, tako da se `pip install` ne ponavlja bez potrebe.
"""

from __future__ import annotations

import hashlib
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

# Ime foldera venv-a u korenu ćelije i fajla u koji se upisuje otisak
# (SHA-256 sadržaja) poslednjeg `requirements.txt` nad kojim je `pip install`
# uspešno prošao.
VENV_DIRNAME = ".venv"
REQUIREMENTS_STAMP = ".requirements.sha256"

# Izvršava komandu u zadatom radnom folderu; baca `RuntimeError` pri neuspehu.
Runner = Callable[[list[str], Path], None]


def run_command(args: list[str], cwd: Path) -> None:
    """
    Podrazumevani `Runner` — pokreće komandu preko `subprocess.run`.

    Args:
        args: Komanda i argumenti (npr. `[python, "-m", "venv", ...]`).
        cwd: Radni folder u kom se komanda pokreće.

    Raises:
        RuntimeError: Ako komanda vrati neuspešan kod — poruka nosi poslednjih
            4000 znakova spojenog stdout/stderr izlaza.
    """
    result = subprocess.run(
        args,
        cwd=cwd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if result.returncode != 0:
        output = (result.stdout or "") + (result.stderr or "")
        raise RuntimeError(
            f"Komanda {args!r} nije uspela (kod {result.returncode}):\n{output[-4000:]}"
        )


def cell_python(cell_root: Path) -> Path:
    """Putanja Python izvršnog fajla u `.venv` ćelije, po platformi."""
    if sys.platform == "win32":
        return cell_root / VENV_DIRNAME / "Scripts" / "python.exe"
    return cell_root / VENV_DIRNAME / "bin" / "python"


def base_python() -> Path:
    """
    Bazni (sistemski) Python interpreter — onaj od kog je CORE-ov `.venv`
    napravljen, ne sam CORE `.venv`. `sys._base_executable` postoji u svakom
    venv-u; ako iz nekog razloga ne postoji (nestandardan build), pada nazad
    na `sys.executable`.
    """
    base = getattr(sys, "_base_executable", "")
    return Path(base) if base else Path(sys.executable)


def _requirements_hash(cell_root: Path) -> str:
    return hashlib.sha256((cell_root / "requirements.txt").read_bytes()).hexdigest()


def _stamp_path(cell_root: Path) -> Path:
    return cell_root / VENV_DIRNAME / REQUIREMENTS_STAMP


def ensure_cell_venv(
    cell_root: Path,
    *,
    runner: Runner = run_command,
    python: Path | None = None,
) -> str:
    """
    Pravi ili ažurira `.venv` ćelije prema `requirements.txt`.

    Pravila:
    - nema `.venv` → napravi ga (`python -m venv`), pa `pip install -r
      requirements.txt` (cwd = koren ćelije), pa upiši otisak → `"created"`;
    - `.venv` postoji, otisak se razlikuje ili fali → samo `pip install` +
      novi otisak → `"updated"`;
    - otisak isti kao trenutni `requirements.txt` → ništa → `"unchanged"`;
    - ako `pip install` padne, otisak se NE upisuje (sledeći poziv ponavlja
      instalaciju), a greška se propušta pozivaocu;
    - `.venv` postoji ali `cell_python` fajl u njemu ne postoji (pokvaren,
      napola napravljen venv) → `RuntimeError` sa uputstvom da se `.venv`
      obriše ručno; ova funkcija ga NIKAD sama ne briše.

    Args:
        cell_root: Koren sklopljene ćelije (ima `requirements.txt`).
        runner: Izvršava komande venv/pip; podrazumevano `run_command`.
        python: Bazni Python za `python -m venv`; podrazumevano
            `base_python()`.

    Returns:
        `"created"`, `"updated"` ili `"unchanged"`.
    """
    venv_dir = cell_root / VENV_DIRNAME
    python_exe = cell_python(cell_root)

    created = not venv_dir.exists()

    if not created and not python_exe.is_file():
        raise RuntimeError(
            f"Pokvaren .venv u {venv_dir} — nedostaje {python_exe}. "
            "Ova funkcija ga ne briše sama; obriši folder ručno pa ponovi."
        )

    current_hash = _requirements_hash(cell_root)
    stamp_path = _stamp_path(cell_root)
    if not created and stamp_path.is_file() and stamp_path.read_text(encoding="utf-8").strip() == current_hash:
        return "unchanged"

    if created:
        base = python if python is not None else base_python()
        runner([str(base), "-m", "venv", str(venv_dir)], cell_root)

    runner([str(python_exe), "-m", "pip", "install", "-r", "requirements.txt"], cell_root)

    stamp_path.parent.mkdir(parents=True, exist_ok=True)
    stamp_path.write_text(current_hash + "\n", encoding="utf-8")

    return "created" if created else "updated"
