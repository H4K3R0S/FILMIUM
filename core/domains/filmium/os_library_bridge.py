"""Cross-platform usklađivanje korena FILMIUM biblioteke sa trenutnim OS-om.

FILMIUM biblioteka (filmovi + izvorne slike/prevodi) živi na ODVOJENOM disku koji
Windows vidi kao ``F:\\``, a Linux montira drugde (npr. ``/run/media/<user>/FILMIUM``).
U bazi je koren sačuvan kao Windows putanja (``F:\\`` → na Linuxu se „ogoli" u ``/``),
pa izvorni fajlovi ne mogu da se pročitaju i reprodukcija ne radi.

Rešenje: pri pokretanju NAĐI stvarni mount diska koji drži biblioteku i prepiši koren
u bazi. Ključno — disk se ne pogađa iz lokacije aplikacije (app može biti na sistemskom
disku, biblioteka na eksternom), već se **validira probom**: kandidat-mount je pravi tek
ako ``<mount>/<relative_directory-iz-baze>`` postoji na disku. OS-neutralno i idempotentno.

Relativne putanje (``relative_directory``) su već OS-neutralne (forward-slash), ne diraju se.
Lokalni ``data/filmium/assets`` ostaje SAMO keš; izvor je biblioteka na disku.
"""

from __future__ import annotations

import getpass
import os
import sqlite3
import sys
from pathlib import Path, PureWindowsPath


def current_disk_root(cell_root: Path) -> str:
    """Koren diska NA KOME JE APLIKACIJA (fallback kad app živi na istom disku kao biblioteka).

    Windows: slovo diska (``F:\\``). Linux/mac: predak koji je stvarna tačka montiranja.
    """
    cell_root = Path(cell_root).resolve()
    if sys.platform.startswith("win"):
        drive = PureWindowsPath(cell_root).drive
        return f"{drive}\\" if drive else str(cell_root.anchor)
    directory = cell_root
    while not os.path.ismount(str(directory)) and directory != directory.parent:
        directory = directory.parent
    return str(directory)


def _norm(path: str | None) -> str:
    """Uporediva normalizacija putanje (bez završnog separatora, unificiran slash)."""
    return (path or "").rstrip("\\/").replace("\\", "/").lower()


def _sample_relative_dirs(cursor: sqlite3.Cursor, limit: int = 12) -> list[str]:
    """Nekoliko `relative_directory` iz baze — za validaciju kandidat-mounta."""
    try:
        rows = cursor.execute(
            "SELECT DISTINCT relative_directory FROM filmium_media_sources "
            "WHERE relative_directory IS NOT NULL AND relative_directory <> '' LIMIT ?",
            (limit,),
        ).fetchall()
    except sqlite3.Error:
        return []
    return [r[0] for r in rows if r and r[0]]


def _holds_library(root: str | None, samples: list[str]) -> bool:
    """Da li `root` STVARNO drži biblioteku (bar jedan `relative_directory` postoji)."""
    if not root:
        return False
    try:
        base = Path(root)
        if not samples:
            return base.is_dir()
        for rel in samples:
            parts = [p for p in rel.replace("\\", "/").split("/") if p]
            if base.joinpath(*parts).is_dir():
                return True
        return False
    except OSError:
        return False


def _candidate_roots() -> list[str]:
    """Mogući koreni diskova za probu, za trenutni OS."""
    seen: set[str] = set()
    out: list[str] = []

    def add(p: str) -> None:
        if p and p not in seen and os.path.isdir(p):
            seen.add(p)
            out.append(p)

    if sys.platform.startswith("win"):
        for letter in "FGHEDICJKLMNOPQRSTUVWXYZAB":
            add(f"{letter}:\\")
        return out

    # Linux/mac: prvo tipične tačke za prenosive diskove, pa svi mountovi iz /proc/mounts.
    user = getpass.getuser()
    for base in (f"/run/media/{user}", f"/media/{user}", "/media", "/mnt", "/run/media"):
        try:
            for entry in sorted(Path(base).iterdir()):
                add(str(entry))
        except OSError:
            pass
    try:
        with open("/proc/mounts", encoding="utf-8") as fh:
            for line in fh:
                cols = line.split()
                if len(cols) >= 2:
                    add(cols[1].replace("\\040", " "))
    except OSError:
        pass
    add("/")
    return out


def find_library_root(db_path: str | Path, cell_root: str | Path | None = None) -> str | None:
    """Nađi koren diska koji STVARNO drži biblioteku (validacija probom). None ako nijedan."""
    try:
        connection = sqlite3.connect(str(db_path))
    except sqlite3.Error:
        return None
    try:
        samples = _sample_relative_dirs(connection.cursor())
    finally:
        connection.close()

    for candidate in _candidate_roots():
        if _holds_library(candidate, samples):
            return candidate

    # Fallback: disk aplikacije (kad app živi na istom disku kao biblioteka).
    if cell_root is not None:
        guess = current_disk_root(Path(cell_root))
        if _holds_library(guess, samples):
            return guess
    return None


def sync_library_roots_for_current_os(db_path: str | Path, cell_root: str | Path) -> int:
    """Uskladi korene biblioteke u bazi sa stvarnim mountom diska koji ih drži.

    Menja SAMO korene koji NE drže biblioteku na trenutnom OS-u (npr. ``/`` ili ``F:\\``
    na Linuxu). Ako se pravi mount ne nađe (disk nije montiran) — NIŠTA ne dira.
    Vraća broj izmenjenih redova. Tolerantno — greška ne ruši start.
    """
    db_path = str(db_path)
    if not os.path.isfile(db_path):
        return 0

    new_root = find_library_root(db_path, cell_root)
    if not new_root:
        # Disk verovatno nije montiran — ne diramo bazu (nema pouzdanog korena).
        return 0

    changed = 0
    connection = sqlite3.connect(db_path)
    try:
        cursor = connection.cursor()
        samples = _sample_relative_dirs(cursor)

        # 1) filmium_library_roots.path — popravi svaki koren koji ne drži biblioteku.
        for root_id, path in cursor.execute(
            "SELECT id, path FROM filmium_library_roots"
        ).fetchall():
            if _norm(path) != _norm(new_root) and not _holds_library(path, samples):
                cursor.execute(
                    "UPDATE filmium_library_roots "
                    "SET path = ?, updated_at = datetime('now') WHERE id = ?",
                    (new_root, root_id),
                )
                changed += cursor.rowcount

        # 2) filmium_media_sources.root_path_snapshot (deljeni koren svih izvora).
        for (old_root,) in cursor.execute(
            "SELECT DISTINCT root_path_snapshot FROM filmium_media_sources"
        ).fetchall():
            if _norm(old_root) != _norm(new_root) and not _holds_library(old_root, samples):
                cursor.execute(
                    "UPDATE filmium_media_sources "
                    "SET root_path_snapshot = ? WHERE root_path_snapshot = ?",
                    (new_root, old_root),
                )
                changed += cursor.rowcount

        connection.commit()
    finally:
        connection.close()

    return changed
