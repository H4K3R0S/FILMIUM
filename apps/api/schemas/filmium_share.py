from datetime import datetime

from pydantic import BaseModel, Field

from core.domains.filmium.share_models import (
    ShareProfile,
    ShareProfileCreate,
    ShareQueueItem,
    ShareQueueItemCreate,
    ShareTransferMode,
)

# ==========          ZAHTEV PROFILA          ==========

class ShareProfileRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    description: str | None = None
    default_destination_folder: str = Field(
        default="VIDEOS",
        min_length=1,
        max_length=100,
    )
    is_active: bool = True

    def to_domain(self) -> ShareProfileCreate:
        """Pretvara API zahtev u domenski model."""

        return ShareProfileCreate(
            name=self.name,
            description=self.description,
            default_destination_folder=(
                self.default_destination_folder
            ),
            is_active=self.is_active,
        )


# ==========          ODGOVOR PROFILA          ==========

class ShareProfileResponse(BaseModel):
    id: int
    name: str
    description: str | None
    default_destination_folder: str
    is_active: bool
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_domain(
        cls,
        item: ShareProfile,
    ) -> "ShareProfileResponse":
        """Pretvara domenski profil u API odgovor."""

        return cls(
            id=item.id,
            name=item.name,
            description=item.description,
            default_destination_folder=(
                item.default_destination_folder
            ),
            is_active=item.is_active,
            created_at=item.created_at,
            updated_at=item.updated_at,
        )


# ==========          ZAHTEVI REDA          ==========

class ShareQueueAddRequest(BaseModel):
    media_id: int = Field(gt=0)
    transfer_mode: ShareTransferMode = ShareTransferMode.PLAYBACK

    def to_domain(self, profile_id: int) -> ShareQueueItemCreate:
        """Pravi domenski zahtev sa ID-em iz URL putanje."""

        return ShareQueueItemCreate(
            profile_id=profile_id,
            media_id=self.media_id,
            transfer_mode=self.transfer_mode,
        )


class ShareTransferModeRequest(BaseModel):
    transfer_mode: ShareTransferMode


# ==========          ZAHTEV/ODGOVOR PRENOSA (KOPIRANJE)          ==========

class ShareTransferRequest(BaseModel):
    media_ids: list[int] = Field(min_length=1)
    destination_path: str = Field(min_length=1)


class ShareTransferResponse(BaseModel):
    copied_files: int
    total_bytes: int
    destination: str
    skipped_media_ids: list[int]

    @classmethod
    def from_domain(cls, summary) -> "ShareTransferResponse":
        """Pretvara sažetak prenosa u API odgovor."""

        return cls(
            copied_files=summary.copied_files,
            total_bytes=summary.total_bytes,
            destination=summary.destination,
            skipped_media_ids=list(summary.skipped_media_ids),
        )


# ==========          ODGOVOR STAVKE REDA          ==========

class ShareQueueItemResponse(BaseModel):
    id: int
    profile_id: int
    media_id: int
    transfer_mode: ShareTransferMode
    status: str
    error_message: str | None
    added_at: datetime
    updated_at: datetime
    completed_at: datetime | None

    @classmethod
    def from_domain(
        cls,
        item: ShareQueueItem,
    ) -> "ShareQueueItemResponse":
        """Pretvara stavku reda u API odgovor."""

        return cls(
            id=item.id,
            profile_id=item.profile_id,
            media_id=item.media_id,
            transfer_mode=item.transfer_mode,
            status=item.status.value,
            error_message=item.error_message,
            added_at=item.added_at,
            updated_at=item.updated_at,
            completed_at=item.completed_at,
        )