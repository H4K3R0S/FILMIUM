import os
import sqlite3
from dataclasses import replace
from datetime import datetime
from pathlib import Path
from typing import ClassVar

from core.domains.filmium.artwork_sync_service import (
    ArtworkSyncError,
    ArtworkSyncService,
)
from core.domains.filmium.library_manifest import (
    FilmiumManifestError,
    normalize_manifest_path,
)
from core.domains.filmium.library_models import (
    MediaFileRole,
    MediaFileStatus,
)
from core.domains.filmium.library_root_repository import (
    LibraryRootRepository,
)
from core.domains.filmium.library_scanner import (
    FilmiumLibraryScanError,
    scan_media_directory,
)
from core.domains.filmium.media_source_models import (
    MediaFileCreate,
    MediaSource,
    MediaSourceCreate,
)
from core.domains.filmium.media_source_repository import (
    MediaSourceRepository,
)
from core.domains.filmium.models import MediaType
from core.domains.filmium.repository import MediaRepository

# ==========          GRESKE FIZICKOG IZVORA          ==========

class MediaSourceValidationError(ValueError):
    """Oznacava neispravne ili nebezbedne podatke izvora."""


class MediaSourceNotFoundError(LookupError):
    """Oznacava da trazeni fizicki izvor ne postoji."""


class MediaSourceMediaNotFoundError(LookupError):
    """Oznacava da katalog nema sadrzaj za novi izvor."""


class MediaSourceLibraryNotFoundError(LookupError):
    """Oznacava da registrovana biblioteka ne postoji."""


class MediaSourceConflictError(ValueError):
    """Oznacava da je isti fizicki izvor vec povezan."""


class MediaSourceRescanError(RuntimeError):
    """Oznacava neuspesno ponovno skeniranje izvora."""


# ==========          MEDIA SOURCE SERVICE          ==========

class MediaSourceService:
    """Validira i povezuje katalog sa lokalnim media datotekama."""

    _SINGLE_FILE_ROLES: ClassVar = {
        MediaFileRole.POSTER,
        MediaFileRole.BACKDROP,
        MediaFileRole.TRAILER,
        MediaFileRole.MANIFEST,
    }

    def __init__(
        self,
        repository: MediaSourceRepository,
        media_repository: MediaRepository,
        library_root_repository: LibraryRootRepository,
        artwork_sync_service: ArtworkSyncService | None = None,
    ) -> None:
        self._repository = repository
        self._media_repository = media_repository
        self._library_root_repository = library_root_repository
        # Kada je prisutan, rescan posle osvežavanja fajlova ponovo napravi
        # source artwork redove iz svežeg manifesta — tako DB uhvati postere/
        # backdrop-ove koje je korisnik naknadno dodao (i serije koje ranije
        # nisu prošle artwork sync).
        self._artwork_sync_service = artwork_sync_service

    def create_media_source(
        self,
        item: MediaSourceCreate,
    ) -> MediaSource:
        media = self._media_repository.get_by_id(item.media_id)

        if media is None:
            raise MediaSourceMediaNotFoundError(
                f"FILMIUM sadrzaj sa ID-em {item.media_id} ne postoji."
            )

        library_root = self._library_root_repository.get(
            item.library_root_id
        )

        if library_root is None:
            raise MediaSourceLibraryNotFoundError(
                "FILMIUM biblioteka sa ID-em "
                f"{item.library_root_id} ne postoji."
            )

        normalized_files = self._normalize_files(
            item.files,
            media.media_type,
        )
        normalized = MediaSourceCreate(
            media_id=media.id,
            library_root_id=library_root.id,
            # Registrovana biblioteka je autoritativni izvor snapshot putanje.
            root_path_snapshot=os.path.normpath(library_root.path),
            relative_directory=self._normalize_relative_path(
                item.relative_directory,
                "relative_directory",
            ),
            manifest_path=self._normalize_relative_path(
                item.manifest_path,
                "manifest_path",
            ),
            availability_status=MediaFileStatus(
                item.availability_status
            ),
            files=normalized_files,
        )

        try:
            return self._repository.create(normalized)
        except sqlite3.IntegrityError as error:
            raise MediaSourceConflictError(
                "Ovaj fizicki FILMIUM izvor je vec povezan sa sadrzajem."
            ) from error

    def list_media_sources(
        self,
        media_id: int,
    ) -> tuple[MediaSource, ...]:
        if self._media_repository.get_by_id(media_id) is None:
            raise MediaSourceMediaNotFoundError(
                f"FILMIUM sadrzaj sa ID-em {media_id} ne postoji."
            )

        return self._repository.list_for_media(media_id)

    def get_media_source(self, source_id: int) -> MediaSource:
        source = self._repository.get(source_id)

        if source is None:
            raise MediaSourceNotFoundError(
                f"FILMIUM izvor sa ID-em {source_id} ne postoji."
            )

        return source

    def replace_media_files(
        self,
        source_id: int,
        files: tuple[MediaFileCreate, ...],
    ) -> MediaSource:
        source = self.get_media_source(source_id)
        media = self._media_repository.get_by_id(source.media_id)

        if media is None:
            raise MediaSourceMediaNotFoundError(
                f"FILMIUM sadrzaj sa ID-em {source.media_id} ne postoji."
            )

        normalized = self._normalize_files(files, media.media_type)

        try:
            updated = self._repository.replace_files(
                source_id,
                normalized,
            )
        except sqlite3.IntegrityError as error:
            raise MediaSourceConflictError(
                "Izvor sadrzi dupliranu relativnu putanju."
            ) from error

        if updated is None:
            raise MediaSourceNotFoundError(
                f"FILMIUM izvor sa ID-em {source_id} ne postoji."
            )

        return updated

    def rescan_media_source(
        self,
        source_id: int,
    ) -> MediaSource:
        """Ponovo skenira folder izvora i osvezava indeks datoteka."""

        source = self.get_media_source(source_id)
        source_directory = (
            Path(source.root_path_snapshot)
            if source.relative_directory == "."
            else Path(source.root_path_snapshot).joinpath(
                *Path(source.relative_directory).parts
            )
        )

        try:
            scan = scan_media_directory(source_directory)
        except (FilmiumLibraryScanError, OSError) as error:
            raise MediaSourceRescanError(str(error)) from error

        files = self._scan_files(scan)

        updated = self.replace_media_files(source_id, files)

        # Osveži source artwork iz istog skeniranja (poster/backdrop koje je
        # korisnik dodao pored filma, sezonske slike serija). `sync_source_
        # manifest` radi nad svežim `updated.files`, pa se putanje poklapaju.
        if self._artwork_sync_service is not None:
            try:
                self._artwork_sync_service.sync_source_manifest(
                    updated,
                    scan.manifest,
                )
            except ArtworkSyncError as error:
                raise MediaSourceRescanError(str(error)) from error

        return updated

    def set_media_source_availability(
        self,
        source_id: int,
        status: MediaFileStatus,
    ) -> MediaSource:
        updated = self._repository.set_availability(
            source_id,
            MediaFileStatus(status),
        )

        if updated is None:
            raise MediaSourceNotFoundError(
                f"FILMIUM izvor sa ID-em {source_id} ne postoji."
            )

        return updated

    def delete_media_source(self, source_id: int) -> None:
        if not self._repository.delete(source_id):
            raise MediaSourceNotFoundError(
                f"FILMIUM izvor sa ID-em {source_id} ne postoji."
            )

    # ==========          UPRAVLJANJE TITLOVIMA          ==========

    _ALLOWED_SUBTITLE_EXTENSIONS: ClassVar = {
        ".srt",
        ".ass",
        ".ssa",
        ".vtt",
        ".sub",
    }

    def _source_directory(self, source: MediaSource) -> Path:
        """Apsolutni folder izvora (root + relativni direktorijum)."""

        if source.relative_directory == ".":
            return Path(source.root_path_snapshot)
        return Path(source.root_path_snapshot).joinpath(
            *Path(source.relative_directory).parts
        )

    def add_subtitle_file(
        self,
        source_id: int,
        filename: str,
        content: bytes,
    ) -> MediaSource:
        """Upisuje titl u folder izvora i ponovo skenira izvor."""

        source = self.get_media_source(source_id)
        safe_name = os.path.basename(filename or "")
        extension = os.path.splitext(safe_name)[1].lower()

        if not safe_name or extension not in (
            self._ALLOWED_SUBTITLE_EXTENSIONS
        ):
            raise MediaSourceValidationError(
                "Dozvoljeni su samo titl fajlovi (.srt, .ass, .ssa, "
                ".vtt, .sub)."
            )

        directory = self._source_directory(source)
        if not directory.is_dir():
            raise MediaSourceRescanError(
                "Folder izvora nije dostupan na disku."
            )

        try:
            (directory / safe_name).write_bytes(content)
        except OSError as error:
            raise MediaSourceRescanError(str(error)) from error

        return self.rescan_media_source(source_id)

    def delete_source_file(
        self,
        source_id: int,
        file_id: int,
    ) -> MediaSource:
        """Briše fizičku datoteku izvora sa diska i osvežava indeks."""

        source = self.get_media_source(source_id)
        target = next(
            (file for file in source.files if file.id == file_id),
            None,
        )
        if target is None:
            raise MediaSourceNotFoundError(
                f"Datoteka {file_id} ne postoji u izvoru {source_id}."
            )

        path = self._source_directory(source).joinpath(
            *Path(target.relative_path).parts
        )
        try:
            if path.exists():
                path.unlink()
        except OSError as error:
            raise MediaSourceRescanError(str(error)) from error

        return self.rescan_media_source(source_id)

    def copy_source_file_to_desktop(
        self,
        source_id: int,
        file_id: int,
    ) -> str:
        """Kopira datoteku izvora na Desktop i vraća odredišnu putanju."""

        import shutil

        source = self.get_media_source(source_id)
        target = next(
            (file for file in source.files if file.id == file_id),
            None,
        )
        if target is None:
            raise MediaSourceNotFoundError(
                f"Datoteka {file_id} ne postoji u izvoru {source_id}."
            )

        origin = self._source_directory(source).joinpath(
            *Path(target.relative_path).parts
        )
        if not origin.is_file():
            raise MediaSourceRescanError(
                "Izvorna datoteka nije dostupna na disku."
            )

        desktop = Path.home() / "Desktop"
        destination_dir = desktop if desktop.is_dir() else Path.home()
        destination = destination_dir / origin.name

        counter = 1
        stem = destination.stem
        suffix = destination.suffix
        while destination.exists():
            destination = destination_dir / f"{stem} ({counter}){suffix}"
            counter += 1

        try:
            shutil.copy2(origin, destination)
        except OSError as error:
            raise MediaSourceRescanError(str(error)) from error

        return str(destination)

    @staticmethod
    def _scan_files(scan) -> tuple[MediaFileCreate, ...]:
        items: list[MediaFileCreate] = []
        subtitle_languages = {
            subtitle.path.casefold(): subtitle.language
            for subtitle in scan.manifest.files.subtitles
        }

        for file in scan.detected_files:
            relative_path = file.path.relative_to(
                scan.directory
            ).as_posix()
            language = file.language

            if (
                file.role is MediaFileRole.SUBTITLE
                and language is None
            ):
                language = subtitle_languages.get(
                    relative_path.casefold(),
                    "und",
                )

            items.append(
                MediaFileCreate(
                    role=file.role,
                    relative_path=relative_path,
                    language=language,
                    size_bytes=file.size_bytes,
                    modified_at=datetime.fromtimestamp(  # noqa: DTZ006
                        file.path.stat().st_mtime
                    ),
                )
            )

        return tuple(items)

    @classmethod
    def _normalize_files(
        cls,
        files: tuple[MediaFileCreate, ...],
        media_type: MediaType,
    ) -> tuple[MediaFileCreate, ...]:
        normalized_files: list[MediaFileCreate] = []
        paths: set[str] = set()
        role_counts: dict[MediaFileRole, int] = {}

        for index, item in enumerate(files):
            role = MediaFileRole(item.role)
            relative_path = cls._normalize_relative_path(
                item.relative_path,
                f"files[{index}].relative_path",
            )
            path_key = relative_path.casefold()

            if path_key in paths:
                raise MediaSourceValidationError(
                    "Izvor ne sme sadrzati duplirane putanje datoteka."
                )

            if item.size_bytes < 0:
                raise MediaSourceValidationError(
                    "Velicina datoteke ne sme biti negativna."
                )

            language = cls._optional_text(item.language)

            if role is MediaFileRole.SUBTITLE and language is None:
                raise MediaSourceValidationError(
                    "Prevodi moraju imati oznaku jezika."
                )

            paths.add(path_key)
            role_counts[role] = role_counts.get(role, 0) + 1
            normalized_files.append(
                replace(
                    item,
                    role=role,
                    relative_path=relative_path,
                    language=language,
                    size_bytes=int(item.size_bytes),
                    file_status=MediaFileStatus(item.file_status),
                )
            )

        for role in cls._SINGLE_FILE_ROLES:
            if role_counts.get(role, 0) > 1:
                raise MediaSourceValidationError(
                    f"Izvor moze imati samo jednu '{role.value}' datoteku."
                )

        if (
            media_type is MediaType.MOVIE
            and role_counts.get(MediaFileRole.VIDEO, 0) > 1
        ):
            raise MediaSourceValidationError(
                "Filmski izvor moze imati samo jednu glavnu video datoteku."
            )

        return tuple(normalized_files)

    @staticmethod
    def _normalize_relative_path(
        value: str,
        field_name: str,
    ) -> str:
        try:
            return normalize_manifest_path(value, field_name)
        except FilmiumManifestError as error:
            raise MediaSourceValidationError(str(error)) from error

    @staticmethod
    def _optional_text(value: str | None) -> str | None:
        if value is None:
            return None

        return value.strip() or None
