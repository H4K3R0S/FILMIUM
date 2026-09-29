# ========== ARHIVA .torrent FAJLOVA ==========
# Kopija svakog .torrent fajla koji je krenuo u preuzimanje čuva se unutar
# CORE-a. Nadzirani folder je korisnikov (Downloads i slično) i tamo fajl
# ume da nestane — čišćenjem, torrent klijentom ili klikom na „X".
#
# Kopija živi dok živi i zapis o torrentu; briše se zajedno sa njim.
from __future__ import annotations

import os
import shutil
from pathlib import Path

from core.foundation.paths import core_paths

ARCHIVE_EXTENSION = ".torrent"


def _safe_name(info_hash: str) -> str:
    """Ime fajla u arhivi; samo heks znakovi, bez ičega iz korisničkog unosa."""

    cleaned = "".join(
        character for character in info_hash.strip().lower()
        if character in "0123456789abcdef"
    )
    return cleaned or "nepoznat"


# ========== ARHIVA ==========
class TorrentArchive:
    """Kopije .torrent fajlova unutar CORE data foldera."""

    def __init__(self, folder: Path | None = None) -> None:
        self._folder = folder or (core_paths.data / "filmium" / "torrents")

    @property
    def folder(self) -> Path:
        return self._folder

    def path_for(self, info_hash: str) -> Path:
        return self._folder / f"{_safe_name(info_hash)}{ARCHIVE_EXTENSION}"

    def store(self, source_path: str, info_hash: str) -> str:
        """Kopira .torrent u arhivu i vraća putanju kopije.

        Prazna niska znači da kopija nije napravljena (izvor nije čitljiv);
        to NIJE razlog da preuzimanje stane.
        """

        source = os.path.abspath(source_path.strip())
        if not os.path.isfile(source):
            return ""

        target = self.path_for(info_hash)

        # Ista putanja bi `copyfile` oborila (SameFileError) i time srušila
        # dodavanje torrenta koji je već u arhivi.
        if os.path.abspath(str(target)) == source:
            return str(target)

        try:
            self._folder.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)
        except OSError:
            return ""

        return str(target)

    def discard(self, info_hash: str) -> None:
        """Briše kopiju; nepostojeća kopija nije greška."""

        try:
            os.remove(self.path_for(info_hash))
        except OSError:
            pass
