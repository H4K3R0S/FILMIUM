from datetime import datetime

from pydantic import BaseModel, Field

from core.domains.filmium.library_models import (
    MediaFileRole,
    MediaFileStatus,
)
from core.domains.filmium.media_source_models import (
    MediaFile,
    MediaFileCreate,
    MediaSource,
    MediaSourceCreate,
)

# ==========          ZAHTEV DATOTEKE          ==========

class MediaFileRequest(BaseModel):
    role: MediaFileRole
    relative_path: str = Field(min_length=1)
    language: str | None = None
    size_bytes: int = Field(default=0, ge=0)
    modified_at: datetime | None = None
    file_status: MediaFileStatus = MediaFileStatus.AVAILABLE

    def to_domain(self) -> MediaFileCreate:
        return MediaFileCreate(
            role=self.role,
            relative_path=self.relative_path,
            language=self.language,
            size_bytes=self.size_bytes,
            modified_at=self.modified_at,
            file_status=self.file_status,
        )


# ==========          ZAHTEV IZVORA          ==========

class MediaSourceRequest(BaseModel):
    library_root_id: int = Field(gt=0)
    relative_directory: str = Field(min_length=1)
    manifest_path: str = Field(
        default="filmium_info.json",
        min_length=1,
    )
    availability_status: MediaFileStatus = MediaFileStatus.AVAILABLE
    files: list[MediaFileRequest] = Field(default_factory=list)

    def to_domain(self, media_id: int) -> MediaSourceCreate:
        return MediaSourceCreate(
            media_id=media_id,
            library_root_id=self.library_root_id,
            # Servis uzima autoritativnu snapshot putanju iz biblioteke.
            root_path_snapshot="",
            relative_directory=self.relative_directory,
            manifest_path=self.manifest_path,
            availability_status=self.availability_status,
            files=tuple(item.to_domain() for item in self.files),
        )


class MediaFilesReplaceRequest(BaseModel):
    files: list[MediaFileRequest] = Field(default_factory=list)

    def to_domain(self) -> tuple[MediaFileCreate, ...]:
        return tuple(item.to_domain() for item in self.files)


class MediaSourceAvailabilityRequest(BaseModel):
    availability_status: MediaFileStatus


# ==========          ODGOVOR DATOTEKE          ==========

class MediaFileResponse(BaseModel):
    id: int
    source_id: int
    role: str
    relative_path: str
    language: str | None
    size_bytes: int
    modified_at: datetime | None
    file_status: str
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_domain(cls, item: MediaFile) -> "MediaFileResponse":
        return cls(
            id=item.id,
            source_id=item.source_id,
            role=item.role.value,
            relative_path=item.relative_path,
            language=item.language,
            size_bytes=item.size_bytes,
            modified_at=item.modified_at,
            file_status=item.file_status.value,
            created_at=item.created_at,
            updated_at=item.updated_at,
        )


# ==========          ODGOVOR IZVORA          ==========

class MediaSourceResponse(BaseModel):
    id: int
    media_id: int
    library_root_id: int | None
    root_path_snapshot: str
    relative_directory: str
    manifest_path: str
    availability_status: str
    last_verified_at: datetime | None
    created_at: datetime
    updated_at: datetime
    files: list[MediaFileResponse]

    @classmethod
    def from_domain(cls, item: MediaSource) -> "MediaSourceResponse":
        return cls(
            id=item.id,
            media_id=item.media_id,
            library_root_id=item.library_root_id,
            root_path_snapshot=item.root_path_snapshot,
            relative_directory=item.relative_directory,
            manifest_path=item.manifest_path,
            availability_status=item.availability_status.value,
            last_verified_at=item.last_verified_at,
            created_at=item.created_at,
            updated_at=item.updated_at,
            files=[
                MediaFileResponse.from_domain(file)
                for file in item.files
            ],
        )