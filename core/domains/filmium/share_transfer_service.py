"""Izvršava prenos (kopiranje) FILMIUM sadržaja na izabrani disk/folder.

Za svaku kataloški sadržaj (film/serija) razrešava fizički izvorni folder
preko ``MediaSource`` (snapshot roota + relativni direktorijum) i kopira
CEO taj folder u ``destination_path/<ime_foldera>``. Original ostaje.

Namerno tolerantan: sadržaj bez povezanog ili dostupnog izvora se preskače
umesto da sruši prenos.
"""

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from core.domains.filmium.media_source_repository import (
    MediaSourceRepository,
)
from core.domains.filmium.media_transfer import (
    copy_media_files,
    enumerate_relative_files,
)

# ==========          GRESKE PRENOSA          ==========

class ShareTransferError(ValueError):
    """Označava neispravne podatke prenosa (npr. prazno odredište)."""


# ==========          REZULTAT          ==========

@dataclass(frozen=True)
class ShareTransferSummary:
    """Sažetak prenosa: kopirano, veličina, odredište i preskočeno."""

    copied_files: int
    total_bytes: int
    destination: str
    skipped_media_ids: tuple[int, ...]


# ==========          SHARE TRANSFER SERVICE          ==========

class ShareTransferService:
    """Kopira kataloške stavke iz reda „Podeli" na izabranu lokaciju."""

    def __init__(
        self,
        media_source_repository: MediaSourceRepository,
    ) -> None:
        self._sources = media_source_repository

    def execute_transfer(
        self,
        media_ids: tuple[int, ...],
        destination_path: str,
        on_progress: Callable[[int, int, int, int], None] | None = None,
    ) -> ShareTransferSummary:
        """
        Kopira folder svake stavke u ``destination_path``. ``on_progress``
        prima globalni (fajlova_gotovo, fajlova_ukupno, bajtova_gotovo,
        bajtova_ukupno) preko SVIH stavki — za jedinstvenu traku progresa.
        """

        destination_root = self._normalize_destination(destination_path)

        plans: list[tuple[Path, tuple[str, ...]]] = []
        skipped: list[int] = []

        for media_id in media_ids:
            source_directory = self._resolve_source_directory(media_id)
            if source_directory is None:
                skipped.append(media_id)
                continue

            relative_files = enumerate_relative_files(source_directory)
            if not relative_files:
                skipped.append(media_id)
                continue

            plans.append((source_directory, relative_files))

        files_total = sum(len(files) for _, files in plans)
        copied_files = 0
        total_bytes = 0
        files_done = 0

        for source_directory, relative_files in plans:
            destination_directory = (
                destination_root / source_directory.name
            )

            def relay(
                item_files_done: int,
                _item_files_total: int,
                file_done: int,
                file_total: int,
                *,
                base: int = files_done,
            ) -> None:
                if on_progress is not None:
                    on_progress(
                        base + item_files_done,
                        files_total,
                        file_done,
                        file_total,
                    )

            result = copy_media_files(
                source_directory,
                relative_files,
                destination_directory,
                relay,
            )
            copied_files += result.copied_files
            total_bytes += result.total_bytes
            files_done += len(relative_files)

        # Zaključi na punom progresu (ako je uopšte bilo fajlova).
        if on_progress is not None and files_total > 0:
            on_progress(files_total, files_total, 1, 1)

        return ShareTransferSummary(
            copied_files=copied_files,
            total_bytes=total_bytes,
            destination=str(destination_root),
            skipped_media_ids=tuple(skipped),
        )

    @staticmethod
    def _normalize_destination(destination_path: str) -> Path:
        cleaned = (destination_path or "").strip()
        if not cleaned:
            raise ShareTransferError(
                "Odredišna putanja ne sme biti prazna."
            )
        return Path(cleaned)

    def _resolve_source_directory(self, media_id: int) -> Path | None:
        """Prvi dostupni fizički folder za dati kataloški sadržaj."""

        for source in self._sources.list_for_media(media_id):
            if source.relative_directory in {"", "."}:
                directory = Path(source.root_path_snapshot)
            else:
                directory = Path(source.root_path_snapshot).joinpath(
                    *Path(source.relative_directory).parts
                )

            if directory.is_dir():
                return directory

        return None
