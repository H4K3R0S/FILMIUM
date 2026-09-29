from typing import Literal

from pydantic import BaseModel, Field

from core.domains.filmium.duplicate_compare import (
    DuplicateComparison,
    DuplicateFile,
)
from core.domains.filmium.library_import_commit_service import (
    MediaImportCommitResult,
)
from core.domains.filmium.library_import_models import (
    ImportPreviewAction,
    ImportPreviewFile,
    MediaImportPreview,
    MediaTechnicalInfo,
)

# ==========          DUPLIKAT POREĐENJE          ==========

class DuplicateFileResponse(BaseModel):
    relative_path: str
    name: str
    size_bytes: int
    role: str
    status: str

    @classmethod
    def from_domain(cls, item: DuplicateFile) -> "DuplicateFileResponse":
        return cls(
            relative_path=item.relative_path,
            name=item.name,
            size_bytes=item.size_bytes,
            role=item.role,
            status=item.status,
        )


class DuplicateComparisonResponse(BaseModel):
    has_duplicate: bool
    target_directory: str | None
    source_files: list[DuplicateFileResponse]
    target_files: list[DuplicateFileResponse]

    @classmethod
    def from_domain(
        cls,
        comparison: DuplicateComparison,
    ) -> "DuplicateComparisonResponse":
        return cls(
            has_duplicate=comparison.has_duplicate,
            target_directory=comparison.target_directory,
            source_files=[
                DuplicateFileResponse.from_domain(item)
                for item in comparison.source_files
            ],
            target_files=[
                DuplicateFileResponse.from_domain(item)
                for item in comparison.target_files
            ],
        )


# ==========          ZAHTEV IMPORT PREVIEW-A          ==========

class LibraryImportPreviewRequest(BaseModel):
    relative_directory: str = Field(min_length=1)
    # Uključuje punu TMDB dopunu (glumci/keywords/kolekcija/EN+SR opis).
    # Bulk auto-obogaćivanje na sken šalje True; brz pojedinačni preview
    # ostaje bez mrežnog poziva.
    include_tmdb: bool = False


# ==========          ZAHTEV POTVRDE UVOZA          ==========

class LibraryImportCommitRequest(BaseModel):
    relative_directory: str = Field(min_length=1)
    confirmed: bool = False
    target_media_id: int | None = Field(default=None, gt=0)
    target_library_root_id: int | None = Field(default=None, gt=0)
    # Opcione izmene koje korisnik napravi u panelu pre potvrde uvoza.
    # Primenjuju se samo pri kreiranju novog kataloškog zapisa.
    title: str | None = Field(default=None, min_length=1, max_length=200)
    release_year: int | None = Field(default=None, ge=1870, le=2200)
    genres: list[str] | None = None
    # Ponašanje pri podudaranju sa postojećim: fail (podrazumevano),
    # skip (dodaj samo nove fajlove) ili overwrite (prepiši postojeće).
    conflict_mode: Literal["fail", "skip", "overwrite"] = "fail"
    # Togle tipa sadržaja: regular (standardno), animated (Animirano/Filmovi)
    # ili domestic (Domaci/Filmovi).
    content_mode: Literal["regular", "animated", "domestic"] = "regular"
    # Da li je sadržaj sinhronizovan (True = SINH, False = titlovan).
    synchronized: bool = False


# ==========          PRONADJENA DATOTEKA          ==========

class ImportPreviewFileResponse(BaseModel):
    relative_path: str
    role: str
    size_bytes: int
    language: str | None

    @classmethod
    def from_domain(
        cls,
        item: ImportPreviewFile,
    ) -> "ImportPreviewFileResponse":
        return cls(
            relative_path=item.relative_path,
            role=item.role.value,
            size_bytes=item.size_bytes,
            language=item.language,
        )


# ==========          PLANIRANA AKCIJA          ==========

class ImportPreviewActionResponse(BaseModel):
    action_type: str
    source: str | None
    destination: str
    reason: str

    @classmethod
    def from_domain(
        cls,
        item: ImportPreviewAction,
    ) -> "ImportPreviewActionResponse":
        return cls(
            action_type=item.action_type,
            source=item.source,
            destination=item.destination,
            reason=item.reason,
        )


# ==========          TEHNIČKE INFORMACIJE          ==========

class ImportTechnicalInfoResponse(BaseModel):
    width: int | None
    height: int | None
    video_codec: str | None
    frame_rate: float | None
    audio_codec: str | None
    audio_channels: int | None
    duration_seconds: float | None

    @classmethod
    def from_domain(
        cls,
        item: MediaTechnicalInfo,
    ) -> "ImportTechnicalInfoResponse":
        return cls(
            width=item.width,
            height=item.height,
            video_codec=item.video_codec,
            frame_rate=item.frame_rate,
            audio_codec=item.audio_codec,
            audio_channels=item.audio_channels,
            duration_seconds=item.duration_seconds,
        )


# ==========          TMDB DOPUNA (PREVIEW)          ==========

class ImportTmdbInfoResponse(BaseModel):
    """Puna TMDB dopuna kandidata koja se nosi u query pri „Prebaci sve"."""

    tmdb_id: int | None = None
    original_title: str | None = None
    english_title: str | None = None
    english_overview: str | None = None
    local_title: str | None = None
    local_overview: str | None = None
    year: int | None = None
    genres: list[str] = []
    rating: float | None = None
    cast_names: list[str] = []
    studio: str | None = None
    director: str | None = None
    vote_count: int | None = None
    original_language: str | None = None
    country: str | None = None
    keywords: list[str] = []
    collection: str | None = None

    @classmethod
    def from_domain(cls, item: object) -> "ImportTmdbInfoResponse":
        return cls(
            tmdb_id=item.tmdb_id,
            original_title=item.original_title,
            english_title=item.english_title,
            english_overview=item.english_overview,
            local_title=item.local_title,
            local_overview=item.local_overview,
            year=item.year,
            genres=list(item.genres),
            rating=item.rating,
            cast_names=list(item.cast_names),
            studio=item.studio,
            director=item.director,
            vote_count=item.vote_count,
            original_language=item.original_language,
            country=item.country,
            keywords=list(item.keywords),
            collection=item.collection,
        )


# ==========          ODGOVOR IMPORT PREVIEW-A          ==========

class LibraryImportPreviewResponse(BaseModel):
    library_root_id: int
    relative_directory: str
    title: str
    original_title: str | None
    media_type: str
    release_year: int | None
    runtime_minutes: int | None
    description: str | None
    genres: list[str]
    unrecognized_genres: list[str]
    studio: str | None
    franchise: str | None
    franchise_order: int | None
    ownership_status: str
    match_status: str
    matching_media_ids: list[int]
    planned_target_directory: str
    detected_files: list[ImportPreviewFileResponse]
    actions: list[ImportPreviewActionResponse]
    warnings: list[str]
    blocking_warnings: list[str]
    can_confirm: bool
    requires_organization: bool
    technical: ImportTechnicalInfoResponse | None = None
    suggested_genres: list[str] = []
    tmdb: ImportTmdbInfoResponse | None = None

    @classmethod
    def from_domain(
        cls,
        item: MediaImportPreview,
    ) -> "LibraryImportPreviewResponse":
        return cls(
            library_root_id=item.library_root_id,
            relative_directory=item.relative_directory,
            title=item.title,
            original_title=item.original_title,
            media_type=item.media_type.value,
            release_year=item.release_year,
            runtime_minutes=item.runtime_minutes,
            description=item.description,
            genres=list(item.genres),
            unrecognized_genres=list(item.unrecognized_genres),
            studio=item.studio,
            franchise=item.franchise,
            franchise_order=item.franchise_order,
            ownership_status=item.ownership_status.value,
            match_status=item.match_status.value,
            matching_media_ids=list(item.matching_media_ids),
            planned_target_directory=item.planned_target_directory,
            detected_files=[
                ImportPreviewFileResponse.from_domain(file)
                for file in item.detected_files
            ],
            actions=[
                ImportPreviewActionResponse.from_domain(action)
                for action in item.actions
            ],
            warnings=list(item.warnings),
            blocking_warnings=list(item.blocking_warnings),
            can_confirm=item.can_confirm,
            requires_organization=item.requires_organization,
            technical=(
                ImportTechnicalInfoResponse.from_domain(item.technical)
                if item.technical is not None
                else None
            ),
            suggested_genres=list(item.suggested_genres),
            tmdb=(
                ImportTmdbInfoResponse.from_domain(item.tmdb)
                if item.tmdb is not None
                else None
            ),
        )


# ==========          ODGOVOR POTVRDJENOG UVOZA          ==========

class LibraryImportCommitResponse(BaseModel):
    media_id: int
    source_id: int
    title: str
    media_type: str
    relative_directory: str
    artwork_ids: list[int]
    created_media: bool
    created_source: bool
    moved_file_count: int
    created_directory_count: int

    @classmethod
    def from_domain(
        cls,
        item: MediaImportCommitResult,
    ) -> "LibraryImportCommitResponse":
        return cls(
            media_id=item.media.id,
            source_id=item.source.id,
            title=item.media.title,
            media_type=item.media.media_type.value,
            relative_directory=item.source.relative_directory,
            artwork_ids=[
                artwork.id
                for artwork in item.artworks
            ],
            created_media=item.created_media,
            created_source=item.created_source,
            moved_file_count=item.moved_file_count,
            created_directory_count=item.created_directory_count,
        )