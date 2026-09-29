"""Provera fajla pre uvoza u biblioteku.

Kopija KALIMA skenera, bez mreže i bez karantina: ćelija fajl samo označi, ne
premešta ga. Postoji zato što torrenti i nadzirani folderi umeju da donesu
izvršni fajl pod imenom filma.
"""

from __future__ import annotations

import os
from collections.abc import Iterable

from core.domains.filmium.import_guard.hash_checker import sha256_file
from core.domains.filmium.import_guard.models import GuardReport, GuardStatus

# Ekstenzije koje su izvršne ili rizične u kontekstu preuzetog „videa".
DANGEROUS_EXT = frozenset({
    "exe", "scr", "bat", "cmd", "com", "js", "vbs", "jar", "msi", "ps1", "sh", "apk",
})

# Ekstenzije koje se legitimno pojavljuju kao prvi deo dvostruke ekstenzije.
_MEDIA_EXT = frozenset({
    "mp4", "mkv", "avi", "mov", "wmv", "srt", "sub", "ass", "vtt",
})


class ImportGuard:
    """Skenira fajl i vraća nalaz."""

    def __init__(self, known_hashes: Iterable[str] | None = None) -> None:
        """
        Args:
            known_hashes: Sažeci poznatog malware-a. Prazno po podrazumevanom.
        """
        self._known = frozenset(known_hashes or ())

    def scan(self, file_path: str) -> GuardReport:
        """
        Proverava fajl i vraća nalaz.

        Args:
            file_path: Putanja fajla.

        Returns:
            Nalaz sa statusom, spiskom pretnji i sažetkom.
        """
        extension = os.path.splitext(file_path)[1].lstrip(".").lower()
        threats: list[str] = []
        status = GuardStatus.CLEAN
        digest = ""

        try:
            digest = sha256_file(file_path)
            if digest in self._known:
                threats.append("poznat malware hash")
                status = GuardStatus.MALWARE
        except OSError:
            threats.append("nemoguće pročitati fajl")
            status = GuardStatus.SUSPICIOUS

        if status is not GuardStatus.MALWARE:
            if self._has_double_extension(file_path):
                threats.append("dvostruka ekstenzija (maskiranje)")
                status = GuardStatus.SUSPICIOUS
            if extension in DANGEROUS_EXT:
                threats.append(f"izvršna ekstenzija .{extension}")
                status = GuardStatus.SUSPICIOUS

        return GuardReport(status=status, threats=tuple(threats), digest=digest)

    def status_for(self, file_path: str) -> GuardStatus:
        """Vraća samo status, za ubrizgavanje u `AutoImportService`."""

        return self.scan(file_path).status

    @staticmethod
    def _has_double_extension(file_path: str) -> bool:
        """Tačno: `film.mp4.exe`. Netačno: `film.2024.mkv`."""

        name = os.path.basename(file_path).lower()
        parts = name.split(".")

        if len(parts) < 3:
            return False

        return parts[-2] in _MEDIA_EXT and parts[-1] in DANGEROUS_EXT
