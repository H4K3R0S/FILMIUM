import os
import sqlite3
from dataclasses import replace
from pathlib import Path, PurePosixPath

from core.domains.filmium.ignored_directory_repository import (
    IgnoredDirectoryRepository,
)
from core.domains.filmium.library_models import (
    LibraryRootStatus,
    MediaFolderScanResult,
)
from core.domains.filmium.library_root_models import (
    LibraryRoot,
    LibraryRootCreate,
    LibraryRootScanStatus,
)
from core.domains.filmium.library_root_repository import (
    LibraryRootRepository,
)
from core.domains.filmium.library_root_scanner import (
    LibraryCatalogStatus,
    LibraryFolderScanEntry,
    LibraryRootScanResult,
    scan_library_root,
)
from core.domains.filmium.library_scanner import (
    FilmiumLibraryScanError,
    scan_media_directory,
)
from core.domains.filmium.media_source_service import MediaSourceService
from core.domains.filmium.models import MediaItem
from core.domains.filmium.repository import MediaRepository
from core.domains.filmium.subtitle_scan_service import (
    SubtitleScanService,
)

# ==========          GRESKE BIBLIOTEKE          ==========

class LibraryRootValidationError(ValueError):
    """Oznacava neispravne podatke biblioteke."""


class LibraryRootNotFoundError(LookupError):
    """Oznacava da registrovana biblioteka ne postoji."""


class LibraryRootConflictError(ValueError):
    """Oznacava duplirani naziv ili putanju biblioteke."""


class LibraryArtworkNotFoundError(LookupError):
    """Oznacava da kandidat nema bezbednu sliku za discovery karticu."""


# ==========          LIBRARY ROOT SERVICE          ==========

class LibraryRootService:
    """Validira biblioteke i povezuje bazu sa skenerom diskova."""

    def __init__(
        self,
        repository: LibraryRootRepository,
        subtitle_scan_service: SubtitleScanService | None = None,
        media_repository: MediaRepository | None = None,
        media_source_service: MediaSourceService | None = None,
        ignored_repository: IgnoredDirectoryRepository | None = None,
    ) -> None:
        self._repository = repository
        self._subtitle_scan_service = subtitle_scan_service
        self._media_repository = media_repository
        self._media_source_service = media_source_service
        self._ignored_repository = ignored_repository

    def create_library_root(
        self,
        item: LibraryRootCreate,
    ) -> LibraryRoot:
        normalized = self._normalize_item(item)

        try:
            return self._repository.create(normalized)
        except sqlite3.IntegrityError as error:
            raise LibraryRootConflictError(
                "Biblioteka sa tim nazivom ili putanjom vec postoji."
            ) from error

    def list_library_roots(self) -> tuple[LibraryRoot, ...]:
        return self._repository.list_all()

    def get_library_root(self, root_id: int) -> LibraryRoot:
        root = self._repository.get(root_id)

        if root is None:
            raise LibraryRootNotFoundError(
                f"FILMIUM biblioteka sa ID-em {root_id} ne postoji."
            )

        return root

    def update_library_root(
        self,
        root_id: int,
        item: LibraryRootCreate,
    ) -> LibraryRoot:
        normalized = self._normalize_item(item)

        try:
            updated = self._repository.update(root_id, normalized)
        except sqlite3.IntegrityError as error:
            raise LibraryRootConflictError(
                "Biblioteka sa tim nazivom ili putanjom vec postoji."
            ) from error

        if updated is None:
            raise LibraryRootNotFoundError(
                f"FILMIUM biblioteka sa ID-em {root_id} ne postoji."
            )

        return updated

    def delete_library_root(self, root_id: int) -> None:
        if not self._repository.delete(root_id):
            raise LibraryRootNotFoundError(
                f"FILMIUM biblioteka sa ID-em {root_id} ne postoji."
            )

    def set_main_library(self, root_id: int) -> LibraryRoot:
        """Označava disk kao glavni (podrazumevano odredište uvoza)."""

        updated = self._repository.set_main(root_id)

        if updated is None:
            raise LibraryRootNotFoundError(
                f"FILMIUM biblioteka sa ID-em {root_id} ne postoji."
            )

        return updated

    def scan_library_root(
        self,
        root_id: int,
        *,
        scan_subtitles: bool = True,
        only_new: bool = False,
    ) -> LibraryRootScanResult:
        root = self.get_library_root(root_id)
        result = scan_library_root(
            Path(root.path),
            enabled=root.is_enabled,
        )
        result = self._filter_ignored_entries(result, root_id)
        result = self._add_catalog_statuses(result)

        # SAMO NOVO toggle: fizički izbacuje sve što nije novo (već u katalogu,
        # dvosmisleno ili neuvezivo) pre dalje obrade i pre skeniranja titlova.
        if only_new:
            result = self._keep_only_new_entries(result)

        # PREVODI toggle: skeniranje titlova je opciono (podrazumevano
        # uključeno radi kompatibilnosti; GUI ga isključuje po defaultu).
        if (
            scan_subtitles
            and self._subtitle_scan_service is not None
            and result.status is LibraryRootStatus.AVAILABLE
        ):
            subtitle_summary = (
                self._subtitle_scan_service.scan_library_result(result)
            )
            result = replace(
                result,
                discovered_subtitle_count=(
                    subtitle_summary.discovered_count
                ),
                inspected_subtitle_count=(
                    subtitle_summary.inspected_count
                ),
                clean_subtitle_count=subtitle_summary.clean_count,
                subtitle_repair_count=(
                    subtitle_summary.needs_repair_count
                ),
                queued_subtitle_count=(
                    subtitle_summary.queued_for_attention_count
                ),
                unsupported_subtitle_count=(
                    subtitle_summary.unsupported_count
                ),
                subtitle_scan_warnings=subtitle_summary.warnings,
            )

        status = {
            LibraryRootStatus.AVAILABLE: LibraryRootScanStatus.AVAILABLE,
            LibraryRootStatus.OFFLINE: LibraryRootScanStatus.OFFLINE,
            LibraryRootStatus.DISABLED: LibraryRootScanStatus.DISABLED,
        }[result.status]

        self._repository.record_scan(root_id, status)
        return result

    # ==========          IGNORISANI FOLDERI          ==========

    def ignore_directory(
        self,
        root_id: int,
        relative_directory: str,
    ) -> None:
        """Trajno izuzima folder iz budućih skeniranja biblioteke."""

        self.get_library_root(root_id)

        if self._ignored_repository is None:
            raise RuntimeError(
                "Repozitorijum ignorisanih foldera nije konfigurisan."
            )

        self._ignored_repository.add(
            root_id,
            self._normalize_relative_directory(relative_directory),
        )

    def unignore_directory(
        self,
        root_id: int,
        relative_directory: str,
    ) -> bool:
        """Vraća folder u skeniranje; True ako je bio ignorisan."""

        self.get_library_root(root_id)

        if self._ignored_repository is None:
            return False

        return self._ignored_repository.remove(
            root_id,
            self._normalize_relative_directory(relative_directory),
        )

    def list_ignored_directories(
        self,
        root_id: int,
    ) -> tuple[str, ...]:
        """Vraća sve ignorisane foldere jedne biblioteke."""

        self.get_library_root(root_id)

        if self._ignored_repository is None:
            return ()

        return self._ignored_repository.list_for_root(root_id)

    def _filter_ignored_entries(
        self,
        result: LibraryRootScanResult,
        root_id: int,
    ) -> LibraryRootScanResult:
        """Izbacuje ignorisane foldere iz rezultata skeniranja."""

        if self._ignored_repository is None:
            return result

        ignored = {
            value.casefold()
            for value in self._ignored_repository.list_for_root(root_id)
        }

        if not ignored:
            return result

        root_path = Path(result.root)
        kept = tuple(
            entry
            for entry in result.entries
            if self._entry_relative_directory(
                entry, root_path
            ).casefold()
            not in ignored
        )

        if len(kept) == len(result.entries):
            return result

        importable = sum(1 for entry in kept if entry.can_import)
        return replace(
            result,
            entries=kept,
            discovered_count=len(kept),
            importable_count=importable,
            problem_count=len(kept) - importable,
        )

    @staticmethod
    def _keep_only_new_entries(
        result: LibraryRootScanResult,
    ) -> LibraryRootScanResult:
        """Zadržava samo nove, uvezive stavke (SAMO NOVO toggle)."""

        kept = tuple(
            entry
            for entry in result.entries
            if entry.can_import
            and entry.catalog_status is LibraryCatalogStatus.NEW
        )

        if len(kept) == len(result.entries):
            return result

        # discovered_count/importable_count/problem_count su computed
        # property-ji na rezultatu — preračunaju se iz `entries`.
        return replace(result, entries=kept)

    @staticmethod
    def _entry_relative_directory(
        entry: LibraryFolderScanEntry,
        root_path: Path,
    ) -> str:
        """Relativni posix folder stavke (isti oblik kao u API odgovoru)."""

        directory = entry.directory
        relative = directory.name

        try:
            relative = directory.relative_to(root_path).as_posix()
        except ValueError:
            relative = str(directory)

        return "." if relative in {"", "."} else relative

    @staticmethod
    def _normalize_relative_directory(value: str) -> str:
        normalized = value.strip().replace("\\", "/")
        return normalized if normalized not in {"", "."} else "."

    def get_discovery_artwork(
        self,
        root_id: int,
        relative_directory: str,
    ) -> Path:
        """Vraća backdrop ili poster isključivo iz registrovanog foldera."""

        root = self.get_library_root(root_id)
        root_path = Path(root.path).resolve(strict=False)
        normalized = relative_directory.strip().replace("\\", "/")

        if normalized in {"", "."}:
            candidate = root_path
        else:
            relative_path = PurePosixPath(normalized)

            if relative_path.is_absolute() or ".." in relative_path.parts:
                raise LibraryArtworkNotFoundError(
                    "Putanja slike izlazi iz registrovane biblioteke."
                )

            candidate = root_path.joinpath(*relative_path.parts)

        try:
            candidate = candidate.resolve(strict=False)
            candidate.relative_to(root_path)
        except ValueError as error:
            raise LibraryArtworkNotFoundError(
                "Putanja slike izlazi iz registrovane biblioteke."
            ) from error

        # Film iz „kolekcije": identitet je VIDEO fajl → slike su u
        # roditeljskom folderu; skeniraj samo taj film.
        video_reference: str | None = None
        if candidate.is_file():
            video_reference = candidate.name
            candidate = candidate.parent

        if not candidate.is_dir() or candidate.is_symlink():
            raise LibraryArtworkNotFoundError(
                "Folder otkrivenog sadržaja nije dostupan."
            )

        try:
            scan = scan_media_directory(candidate, video_reference)
        except (FilmiumLibraryScanError, OSError) as error:
            raise LibraryArtworkNotFoundError(str(error)) from error

        references = (
            scan.manifest.files.backdrop,
            scan.manifest.files.poster,
            *(
                artwork.path
                for artwork in scan.manifest.files.wallpapers
                if artwork.is_primary
            ),
            *(artwork.path for artwork in scan.manifest.files.wallpapers),
            *(artwork.path for artwork in scan.manifest.files.fanart),
        )

        for reference in references:
            if reference is None:
                continue

            artwork = candidate.joinpath(
                *PurePosixPath(reference).parts
            )

            try:
                resolved_artwork = artwork.resolve(strict=False)
                resolved_artwork.relative_to(candidate)
            except ValueError:
                continue

            if (
                resolved_artwork.is_file()
                and not resolved_artwork.is_symlink()
                and resolved_artwork.suffix.casefold()
                in {".jpg", ".jpeg", ".png", ".webp"}
            ):
                return resolved_artwork

        raise LibraryArtworkNotFoundError(
            "Poster ili backdrop nije pronađen."
        )

    def get_entry_artwork_file(
        self,
        root_id: int,
        relative_directory: str,
        relative_file: str,
    ) -> Path:
        """Vraća tačno određenu sliku (poster/backdrop...) iz foldera."""

        root = self.get_library_root(root_id)
        root_path = Path(root.path).resolve(strict=False)
        directory = self._safe_join(root_path, relative_directory)

        # Film iz „kolekcije": identitet je VIDEO fajl → slike su u
        # roditeljskom folderu (relativne putanje su u odnosu na njega).
        if directory.is_file():
            directory = directory.parent

        if not directory.is_dir() or directory.is_symlink():
            raise LibraryArtworkNotFoundError(
                "Folder otkrivenog sadržaja nije dostupan."
            )

        file_path = self._safe_join(directory, relative_file)

        if (
            file_path.is_file()
            and not file_path.is_symlink()
            and file_path.suffix.casefold()
            in {".jpg", ".jpeg", ".png", ".webp"}
        ):
            return file_path

        raise LibraryArtworkNotFoundError(
            "Tražena slika nije pronađena."
        )

    @staticmethod
    def _safe_join(base: Path, relative: str) -> Path:
        """Bezbedno spaja putanju i garantuje da ostaje unutar baze."""

        normalized = relative.strip().replace("\\", "/")

        if normalized in {"", "."}:
            return base

        relative_path = PurePosixPath(normalized)

        if relative_path.is_absolute() or ".." in relative_path.parts:
            raise LibraryArtworkNotFoundError(
                "Putanja slike izlazi iz registrovane biblioteke."
            )

        candidate = base.joinpath(*relative_path.parts).resolve(
            strict=False
        )

        try:
            candidate.relative_to(base.resolve(strict=False))
        except ValueError as error:
            raise LibraryArtworkNotFoundError(
                "Putanja slike izlazi iz registrovane biblioteke."
            ) from error

        return candidate

    def _add_catalog_statuses(
        self,
        result: LibraryRootScanResult,
    ) -> LibraryRootScanResult:
        """Povezuje pronađene foldere sa katalogom i fizičkim izvorima."""

        if (
            self._media_repository is None
            or result.status is not LibraryRootStatus.AVAILABLE
        ):
            return result

        catalog = self._media_repository.list_all()
        entries = tuple(
            self._add_entry_catalog_status(
                entry,
                catalog,
            )
            for entry in result.entries
        )
        return replace(result, entries=entries)

    def _add_entry_catalog_status(
        self,
        entry: LibraryFolderScanEntry,
        catalog: tuple[MediaItem, ...],
    ) -> LibraryFolderScanEntry:
        if entry.scan_result is None:
            return entry

        matches = self._catalog_matches(entry.scan_result, catalog)
        matching_ids = tuple(item.id for item in matches)

        if not matches:
            status = LibraryCatalogStatus.NEW
        elif len(matches) > 1:
            status = LibraryCatalogStatus.AMBIGUOUS
        else:
            status = self._single_match_status(
                matches[0],
                entry.directory,
            )

        return replace(
            entry,
            catalog_status=status,
            matching_media_ids=matching_ids,
        )

    def _single_match_status(
        self,
        media: MediaItem,
        directory: Path,
    ) -> LibraryCatalogStatus:
        if self._media_source_service is None:
            return LibraryCatalogStatus.CATALOG_ONLY

        sources = self._media_source_service.list_media_sources(media.id)

        if not sources:
            return LibraryCatalogStatus.CATALOG_ONLY

        wanted_directory = directory.resolve(strict=False)

        # Isti fizički folder može biti pronađen kroz različite
        # registrovane root-ove. Zato se poredi konačna apsolutna
        # putanja, a ne samo library_root_id.
        for source in sources:
            source_root = Path(source.root_path_snapshot)
            source_directory = source_root.joinpath(
                *Path(source.relative_directory).parts
            )

            if (
                source_directory.resolve(strict=False)
                == wanted_directory
            ):
                return LibraryCatalogStatus.AVAILABLE

        return LibraryCatalogStatus.UNAVAILABLE

    @classmethod
    def _catalog_matches(
        cls,
        scan: MediaFolderScanResult,
        catalog: tuple[MediaItem, ...],
    ) -> tuple[MediaItem, ...]:
        wanted_titles = {cls._title_identity(scan.title)}

        if scan.manifest.original_title:
            wanted_titles.add(
                cls._title_identity(scan.manifest.original_title)
            )

        matches: list[MediaItem] = []

        for item in catalog:
            if item.media_type is not scan.manifest.media_type:
                continue

            item_titles = {cls._title_identity(item.title)}

            if item.original_title:
                item_titles.add(cls._title_identity(item.original_title))

            if wanted_titles.isdisjoint(item_titles):
                continue

            if (
                scan.release_year is not None
                and item.release_year is not None
                and scan.release_year != item.release_year
            ):
                continue

            matches.append(item)

        return tuple(sorted(matches, key=lambda item: item.id))

    @staticmethod
    def _title_identity(value: str) -> str:
        return "".join(
            character
            for character in value.casefold()
            if character.isalnum()
        )

    @staticmethod
    def _optional_text(value: str | None) -> str | None:
        if value is None:
            return None

        return value.strip() or None

    @classmethod
    def _normalize_item(
        cls,
        item: LibraryRootCreate,
    ) -> LibraryRootCreate:
        name = item.name.strip()
        raw_path = item.path.strip().strip('"')

        if not name:
            raise LibraryRootValidationError(
                "Naziv biblioteke ne sme biti prazan."
            )

        if len(name) > 100:
            raise LibraryRootValidationError(
                "Naziv biblioteke ne sme biti duzi od 100 znakova."
            )

        if not raw_path:
            raise LibraryRootValidationError(
                "Putanja biblioteke ne sme biti prazna."
            )

        normalized_path = os.path.normpath(raw_path)

        if not Path(normalized_path).is_absolute():
            raise LibraryRootValidationError(
                "Putanja biblioteke mora biti apsolutna."
            )

        return LibraryRootCreate(
            name=name,
            path=normalized_path,
            volume_id=cls._optional_text(item.volume_id),
            volume_label=cls._optional_text(item.volume_label),
            is_enabled=bool(item.is_enabled),
            is_persistent=bool(item.is_persistent),
        )
