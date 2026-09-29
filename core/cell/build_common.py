"""Cell build — niski helperi (kopiranje/brisanje) + crna lista modula —
izdvojeno iz build.py radi veličine. Leaf modul (samo stdlib)."""

from __future__ import annotations

import logging
import os
import shutil
import stat
from pathlib import Path

_logger = logging.getLogger("core.cell.build")


_IGNORE = shutil.ignore_patterns("__pycache__", "*.pyc", ".pytest_cache")


_EXCLUDED_KERNEL_FILES: dict[str, tuple[str, ...]] = {
    "foundation": ("context.py", "runtime.py"),
    "database": ("runtime.py",),
}


def _ignore_kernel_extras(directory: str, names: list[str]) -> set[str]:
    """Isključuje fajlove iz `_EXCLUDED_KERNEL_FILES`, po imenu direktorijuma."""

    ignored = set(_IGNORE(directory, names))
    extra = _EXCLUDED_KERNEL_FILES.get(Path(directory).name, ())
    ignored.update(name for name in extra if name in names)
    return ignored


_EXCLUDED_KERNEL_FILE_MODULES: tuple[str, ...] = tuple(
    f"core.{directory}.{filename.removesuffix('.py')}"
    for directory, filenames in _EXCLUDED_KERNEL_FILES.items()
    for filename in filenames
)


_FORBIDDEN_MODULES: tuple[str, ...] = (
    "core.integrations",
    "core.security",
    "apps.api.core_ai_runtime",
    "core.domains.registry",
    *_EXCLUDED_KERNEL_FILE_MODULES,
)


def _is_forbidden(module: str) -> bool:
    """Da li je `module` na crnoj listi, ili potiče iz nje (podmodul)."""

    return any(
        module == forbidden or module.startswith(forbidden + ".")
        for forbidden in _FORBIDDEN_MODULES
    )


def _copy(source: Path, target: Path, *, ignore=_IGNORE) -> None:
    """Kopira fajl ili folder, praveći roditeljske direktorijume."""

    target.parent.mkdir(parents=True, exist_ok=True)

    if source.is_dir():
        shutil.copytree(source, target, ignore=ignore, dirs_exist_ok=True)
    else:
        shutil.copy2(source, target)


def _make_writable_and_retry(func, path: str, exc: BaseException) -> None:
    """
    `onexc` za `shutil.rmtree`: Windows "samo za čitanje" fajl inače prekida
    brisanje na pola puta (`PermissionError`) i ostavlja ćeliju u polu-obrisanom
    stanju. Skida atribut (`os.chmod(..., S_IWRITE)`) i ponavlja TAČNO onu
    operaciju koja je pukla (`func`, npr. `os.unlink`/`os.rmdir`), umesto da
    nagađa koja je bila u pitanju.

    Args:
        func: Operacija koja je pukla (prosleđuje je `shutil.rmtree` sam).
        path: Putanja na kojoj je pukla.
        exc: Izuzetak koji je izazvao poziv (Python 3.14 `onexc` potpis).
    """
    try:
        os.chmod(path, stat.S_IWRITE)
        func(path)
    except OSError:
        raise exc from None


def _remove_path(path: Path) -> None:
    """
    Bezbedno uklanja fajl, direktorijum ili symlink/junction.

    Symlink/junction se uklanja KAO takav (nikad se ne prati u dubinu) — da
    `shutil.rmtree` ne bi obrisao sadržaj IZVAN ćelije ako neki child slučajno
    bude simbolička veza ka spoljnom direktorijumu. Read-only fajlovi
    (uobičajeno na Windows-u posle nekih alata) se čine upisivim pre brisanja,
    umesto da brisanje stane na pola sa `PermissionError` (vidi
    `_make_writable_and_retry`).
    """
    if path.is_symlink():
        try:
            path.unlink()
        except OSError:
            # Direktorijumski symlink/junction na Windows-u se uklanja sa
            # rmdir, ne unlink — unlink na njemu diže PermissionError.
            os.rmdir(path)
        return

    if path.is_dir():
        shutil.rmtree(path, onexc=_make_writable_and_retry)
        return

    try:
        path.unlink()
    except PermissionError:
        os.chmod(path, stat.S_IWRITE)
        path.unlink()
