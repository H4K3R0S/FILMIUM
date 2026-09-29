import shutil
from datetime import datetime
from pathlib import Path

from pydantic import BaseModel, Field

from core.domains.filmium.library_root_models import (
    LibraryRoot,
    LibraryRootCreate,
)
from core.domains.filmium.library_root_scanner import (
    LibraryFolderScanEntry,
    LibraryRootScanResult,
)

# ==========          ZAHTEV BIBLIOTEKE          ==========

class LibraryRootRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    path: str = Field(min_length=1)
    volume_id: str | None = None
    volume_label: str | None = None
    is_enabled: bool = True
    is_persistent: bool = True

    def to_domain(self) -> LibraryRootCreate:
        return LibraryRootCreate(
            name=self.name,
            path=self.path,
            volume_id=self.volume_id,
            volume_label=self.volume_label,
            is_enabled=self.is_enabled,
            is_persistent=self.is_persistent,
        )


# ==========          KAPACITET DISKA          ==========

def _read_disk_capacity(
    path: str,
) -> tuple[int | None, int | None]:
    """Vraća (ukupno, slobodno) bajtova za putanju, ili (None, None).

    Kapacitet se čita u trenutku odgovora (bez čuvanja u bazi). Ako disk
    nije priključen ili putanja ne postoji, vraća se (None, None).
    """

    try:
        usage = shutil.disk_usage(path)
    except OSError:
        return None, None

    return usage.total, usage.free


# ==========          ODGOVOR BIBLIOTEKE          ==========

class LibraryRootResponse(BaseModel):
    id: int
    name: str
    path: str
    volume_id: str | None
    volume_label: str | None
    is_enabled: bool
    is_persistent: bool
    is_main: bool
    last_scan_status: str
    last_scanned_at: datetime | None
    last_seen_at: datetime | None
    created_at: datetime
    updated_at: datetime
    total_bytes: int | None = None
    free_bytes: int | None = None

    @classmethod
    def from_domain(cls, root: LibraryRoot) -> "LibraryRootResponse":
        total_bytes, free_bytes = _read_disk_capacity(root.path)

        return cls(
            id=root.id,
            name=root.name,
            path=root.path,
            volume_id=root.volume_id,
            volume_label=root.volume_label,
            is_enabled=root.is_enabled,
            is_persistent=root.is_persistent,
            is_main=root.is_main,
            last_scan_status=root.last_scan_status.value,
            last_scanned_at=root.last_scanned_at,
            last_seen_at=root.last_seen_at,
            created_at=root.created_at,
            updated_at=root.updated_at,
            total_bytes=total_bytes,
            free_bytes=free_bytes,
        )


# ==========          IGNORISANI FOLDERI          ==========

class LibraryIgnoreDirectoryRequest(BaseModel):
    relative_directory: str = Field(min_length=1)


class LibraryIgnoredDirectoriesResponse(BaseModel):
    directories: list[str]


# ==========          ODGOVOR SKENIRANJA          ==========

class LibraryFolderScanResponse(BaseModel):
    directory: str
    title: str | None
    release_year: int | None
    can_import: bool
    catalog_status: str
    matching_media_ids: list[int]
    warnings: list[str]
    error_message: str | None

    @classmethod
    def from_domain(
        cls,
        entry: LibraryFolderScanEntry,
        root: str | None = None,
    ) -> "LibraryFolderScanResponse":
        scan = entry.scan_result
        relative_directory = entry.directory.name

        if root is not None:
            root_path = Path(root)

            try:
                relative_directory = entry.directory.relative_to(
                    root_path
                ).as_posix()
            except ValueError:
                relative_directory = str(entry.directory)

        if relative_directory in {"", "."}:
            relative_directory = "."

        return cls(
            directory=relative_directory,
            title=None if scan is None else scan.title,
            release_year=(
                None if scan is None else scan.release_year
            ),
            can_import=entry.can_import,
            catalog_status=entry.catalog_status.value,
            matching_media_ids=list(entry.matching_media_ids),
            warnings=(
                [] if scan is None else list(scan.warnings)
            ),
            error_message=entry.error_message,
        )


class LibraryRootScanResponse(BaseModel):
    root: str
    status: str
    discovered_count: int
    importable_count: int
    problem_count: int
    ignored_file_count: int
    discovered_subtitle_count: int
    inspected_subtitle_count: int
    clean_subtitle_count: int
    subtitle_repair_count: int
    queued_subtitle_count: int
    unsupported_subtitle_count: int
    subtitle_scan_warnings: list[str]
    warnings: list[str]
    entries: list[LibraryFolderScanResponse]

    @classmethod
    def from_domain(
        cls,
        result: LibraryRootScanResult,
    ) -> "LibraryRootScanResponse":
        return cls(
            root=str(result.root),
            status=result.status.value,
            discovered_count=result.discovered_count,
            importable_count=result.importable_count,
            problem_count=result.problem_count,
            ignored_file_count=result.ignored_file_count,
            discovered_subtitle_count=(
                result.discovered_subtitle_count
            ),
            inspected_subtitle_count=result.inspected_subtitle_count,
            clean_subtitle_count=result.clean_subtitle_count,
            subtitle_repair_count=result.subtitle_repair_count,
            queued_subtitle_count=result.queued_subtitle_count,
            unsupported_subtitle_count=(
                result.unsupported_subtitle_count
            ),
            subtitle_scan_warnings=list(
                result.subtitle_scan_warnings
            ),
            warnings=list(result.warnings),
            entries=[
                LibraryFolderScanResponse.from_domain(
                    entry,
                    str(result.root),
                )
                for entry in result.entries
            ],
        )
