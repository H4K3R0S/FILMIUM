# ========== ŠEME: FILMIUM TORRENTI ==========
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from core.domains.filmium.torrents.torrent_models import (
    DiscoveredTorrent,
    EngineHealth,
    TorrentEntry,
    TorrentFileEntry,
    TorrentProgress,
    TorrentSettings,
)


class TorrentHealthResponse(BaseModel):
    engine_available: bool
    version: str | None = None
    message: str | None = None

    @classmethod
    def from_domain(cls, health: EngineHealth) -> TorrentHealthResponse:
        return cls(
            engine_available=health.available,
            version=health.version,
            message=health.message,
        )


class TorrentAddRequest(BaseModel):
    source: str = Field(min_length=1)


class TorrentApproveRequest(BaseModel):
    selected_indexes: list[int] = Field(default_factory=list)


class TorrentFileResponse(BaseModel):
    file_index: int
    path: str
    size_bytes: int
    selected: bool
    # Napredak fajla (0.0-1.0); 0.0 kada klijent nije dostupan.
    progress: float = 0.0

    @classmethod
    def from_domain(cls, item: TorrentFileEntry) -> TorrentFileResponse:
        return cls(
            file_index=item.file_index,
            path=item.path,
            size_bytes=item.size_bytes,
            selected=item.selected,
            progress=item.progress,
        )


class TorrentResponse(BaseModel):
    info_hash: str
    name: str
    source_kind: str
    status: str
    save_path: str
    total_bytes: int
    added_at: datetime
    completed_at: datetime | None = None
    error_message: str | None = None
    # Putanja do kopije .torrent fajla u CORE-u; prazno kad kopije nema.
    archived_path: str = ""

    @classmethod
    def from_domain(cls, entry: TorrentEntry) -> TorrentResponse:
        return cls(
            info_hash=entry.info_hash,
            name=entry.name,
            source_kind=entry.source_kind,
            status=entry.status.value,
            save_path=entry.save_path,
            total_bytes=entry.total_bytes,
            added_at=entry.added_at,
            completed_at=entry.completed_at,
            error_message=entry.error_message,
            archived_path=entry.archived_path,
        )


class TorrentProgressResponse(BaseModel):
    info_hash: str
    progress: float
    download_rate: int
    upload_rate: int
    eta_seconds: int | None = None
    seeds: int
    peers: int
    is_finished: bool
    is_paused: bool

    @classmethod
    def from_domain(cls, item: TorrentProgress) -> TorrentProgressResponse:
        return cls(
            info_hash=item.info_hash,
            progress=item.progress,
            download_rate=item.download_rate,
            upload_rate=item.upload_rate,
            eta_seconds=item.eta_seconds,
            seeds=item.seeds,
            peers=item.peers,
            is_finished=item.is_finished,
            is_paused=item.is_paused,
        )


class TorrentSettingsRequest(BaseModel):
    host: str = "127.0.0.1"
    port: int = 8080
    username: str = ""
    # Prazna lozinka znači „ne diraj postojeću".
    password: str | None = None
    watch_folders: list[str] = Field(default_factory=list)
    download_path: str = ""
    max_download_kbs: int = 0
    max_upload_kbs: int = 0
    max_active: int = 3
    auto_start: bool = True
    seed_after_complete: bool = False
    delete_source_torrent: bool = False
    unselected_extensions: list[str] = Field(
        default_factory=lambda: [".nfo", ".txt", ".url", ".jpg", ".png", ".sfv"]
    )


class TorrentSettingsResponse(BaseModel):
    """Lozinka se NIKADA ne vraća klijentu; šalje se samo da li postoji."""

    host: str
    port: int
    username: str
    has_password: bool
    watch_folders: list[str]
    download_path: str
    max_download_kbs: int
    max_upload_kbs: int
    max_active: int
    auto_start: bool
    seed_after_complete: bool
    delete_source_torrent: bool
    unselected_extensions: list[str]

    @classmethod
    def from_domain(cls, settings: TorrentSettings) -> TorrentSettingsResponse:
        return cls(
            host=settings.host,
            port=settings.port,
            username=settings.username,
            has_password=bool(settings.password),
            watch_folders=list(settings.watch_folders),
            download_path=settings.download_path,
            max_download_kbs=settings.max_download_kbs,
            max_upload_kbs=settings.max_upload_kbs,
            max_active=settings.max_active,
            auto_start=settings.auto_start,
            seed_after_complete=settings.seed_after_complete,
            delete_source_torrent=settings.delete_source_torrent,
            unselected_extensions=list(settings.unselected_extensions),
        )


# ==========          PRONAĐENI .torrent FAJLOVI          ==========

class DiscoveredFileResponse(BaseModel):
    file_index: int
    path: str
    size_bytes: int


class DiscoveredTorrentResponse(BaseModel):
    """Kartica pročitana iz samog .torrent fajla.

    `status` je `None` dok torrent postoji samo kao fajl; čim je predat
    qBittorrent-u, nosi status zapisa iz baze.
    """

    source_path: str
    info_hash: str
    name: str
    total_bytes: int
    files: list[DiscoveredFileResponse]
    status: str | None = None
    # Da li je torrent već poslat ka ekranu uvoza u biblioteku.
    handed_to_library: bool = False

    @classmethod
    def from_domain(cls, item: DiscoveredTorrent) -> DiscoveredTorrentResponse:
        return cls(
            source_path=item.source_path,
            info_hash=item.info_hash,
            name=item.name,
            total_bytes=item.total_bytes,
            files=[
                DiscoveredFileResponse(
                    file_index=entry.file_index,
                    path=entry.path,
                    size_bytes=entry.size_bytes,
                )
                for entry in item.files
            ],
            status=item.status.value if item.status is not None else None,
            handed_to_library=item.handed_to_library,
        )


class DiscoveredStartRequest(BaseModel):
    source_path: str = Field(min_length=1)
    selected_paths: list[str] = Field(default_factory=list)


class TorrentBulkResponse(BaseModel):
    """Ishod grupne radnje: koliko je torrenta promenilo stanje, a koliko ne."""

    affected: int
    failed: int = 0


class TorrentRevealResponse(BaseModel):
    """Ishod otvaranja foldera i putanja koja je otvorena."""

    revealed: bool
    folder: str
