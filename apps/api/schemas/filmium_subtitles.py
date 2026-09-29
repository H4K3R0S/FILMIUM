from datetime import datetime

from pydantic import BaseModel, Field

from core.domains.filmium.subtitle_inspector_models import (
    SubtitleIssue,
    SubtitleIssueSeverity,
    SubtitleIssueType,
    SubtitleRepairPreview,
)
from core.domains.filmium.subtitle_repair_models import (
    PreparedSubtitleRepair,
    SubtitleRepairApplyResult,
)
from core.domains.filmium.subtitle_repair_queue_models import (
    SubtitleRepairQueueItem,
    SubtitleRepairQueueStatus,
)

# ==========          ZAHTEVI          ==========

class SubtitleInspectRequest(BaseModel):
    file_path: str = Field(min_length=1, max_length=32767)
    media_id: int | None = Field(default=None, gt=0)
    source_id: int | None = Field(default=None, gt=0)


class SubtitleQueueStatusRequest(BaseModel):
    status: SubtitleRepairQueueStatus


class SubtitleRepairRequest(BaseModel):
    confirmed: bool


class SubtitleEditPreviewRequest(BaseModel):
    file_path: str = Field(min_length=1, max_length=32767)


class SubtitleManualSaveRequest(BaseModel):
    file_path: str = Field(min_length=1, max_length=32767)
    source_sha256: str = Field(min_length=64, max_length=64)
    content: str = Field(max_length=10 * 1024 * 1024)
    confirmed: bool


# ==========          PROBLEM I PROMENA          ==========

class SubtitleIssueResponse(BaseModel):
    issue_type: SubtitleIssueType
    severity: SubtitleIssueSeverity
    message: str
    line_number: int | None
    original_text: str | None
    suggested_text: str | None

    @classmethod
    def from_domain(
        cls,
        item: SubtitleIssue,
    ) -> "SubtitleIssueResponse":
        return cls(
            issue_type=item.issue_type,
            severity=item.severity,
            message=item.message,
            line_number=item.line_number,
            original_text=item.original_text,
            suggested_text=item.suggested_text,
        )


class SubtitleRepairChangeResponse(BaseModel):
    line_number: int
    original_text: str
    repaired_text: str


class SubtitleRepairPreviewResponse(BaseModel):
    file_name: str
    detected_encoding: str
    detected_language_code: str | None
    original_text: str
    repaired_text: str
    changes: list[SubtitleRepairChangeResponse]
    backup_required: bool

    @classmethod
    def from_domain(
        cls,
        item: SubtitleRepairPreview,
    ) -> "SubtitleRepairPreviewResponse":
        return cls(
            file_name=item.file_name,
            detected_encoding=item.detected_encoding,
            detected_language_code=item.detected_language_code,
            original_text=item.original_text,
            repaired_text=item.repaired_text,
            changes=[
                SubtitleRepairChangeResponse(
                    line_number=change.line_number,
                    original_text=change.original_text,
                    repaired_text=change.repaired_text,
                )
                for change in item.changes
            ],
            backup_required=item.backup_required,
        )


# ==========          STAVKA REDA          ==========

class SubtitleRepairQueueResponse(BaseModel):
    id: int
    media_id: int | None
    source_id: int | None
    file_path: str
    file_name: str
    source_sha256: str
    detected_encoding: str
    detected_language_code: str | None
    language_confidence: float
    issue_count: int
    status: SubtitleRepairQueueStatus
    discovered_at: datetime
    updated_at: datetime
    reviewed_at: datetime | None
    resolved_at: datetime | None

    @classmethod
    def from_domain(
        cls,
        item: SubtitleRepairQueueItem,
    ) -> "SubtitleRepairQueueResponse":
        return cls(
            id=item.id,
            media_id=item.media_id,
            source_id=item.source_id,
            file_path=item.file_path,
            file_name=item.file_name,
            source_sha256=item.source_sha256,
            detected_encoding=item.detected_encoding,
            detected_language_code=item.detected_language_code,
            language_confidence=item.language_confidence,
            issue_count=item.issue_count,
            status=item.status,
            discovered_at=item.discovered_at,
            updated_at=item.updated_at,
            reviewed_at=item.reviewed_at,
            resolved_at=item.resolved_at,
        )


# ==========          REZULTAT ANALIZE          ==========

class SubtitleInspectionResponse(BaseModel):
    file_path: str
    source_sha256: str
    file_name: str
    detected_encoding: str
    detected_language_code: str | None
    language_confidence: float
    is_probably_serbian: bool
    needs_repair: bool
    issues: list[SubtitleIssueResponse]
    preview: SubtitleRepairPreviewResponse
    queue_item: SubtitleRepairQueueResponse | None

    @classmethod
    def from_domain(
        cls,
        prepared: PreparedSubtitleRepair,
        queue_item: SubtitleRepairQueueItem | None,
    ) -> "SubtitleInspectionResponse":
        inspection = prepared.inspection
        return cls(
            file_path=str(prepared.file_path),
            source_sha256=prepared.source_sha256,
            file_name=inspection.file_name,
            detected_encoding=inspection.detected_encoding,
            detected_language_code=inspection.detected_language_code,
            language_confidence=inspection.language_confidence,
            is_probably_serbian=inspection.is_probably_serbian,
            needs_repair=inspection.needs_repair,
            issues=[
                SubtitleIssueResponse.from_domain(issue)
                for issue in inspection.issues
            ],
            preview=SubtitleRepairPreviewResponse.from_domain(
                prepared.preview
            ),
            queue_item=(
                None
                if queue_item is None
                else SubtitleRepairQueueResponse.from_domain(queue_item)
            ),
        )


# ==========          REZULTAT POPRAVKE          ==========

class SubtitleRepairResultResponse(BaseModel):
    file_path: str
    backup_path: str
    source_sha256: str
    repaired_sha256: str
    output_encoding: str
    changed_lines: int
    queue_item: SubtitleRepairQueueResponse

    @classmethod
    def from_domain(
        cls,
        result: SubtitleRepairApplyResult,
        queue_item: SubtitleRepairQueueItem,
    ) -> "SubtitleRepairResultResponse":
        return cls(
            file_path=str(result.file_path),
            backup_path=str(result.backup_path),
            source_sha256=result.source_sha256,
            repaired_sha256=result.repaired_sha256,
            output_encoding=result.output_encoding,
            changed_lines=result.changed_lines,
            queue_item=SubtitleRepairQueueResponse.from_domain(
                queue_item
            ),
        )


# ==========          REZULTAT RUCNOG SNIMANJA          ==========

class SubtitleManualSaveResponse(BaseModel):
    file_path: str
    backup_path: str
    source_sha256: str
    saved_sha256: str
    output_encoding: str
    changed_lines: int

    @classmethod
    def from_domain(
        cls,
        result: SubtitleRepairApplyResult,
    ) -> "SubtitleManualSaveResponse":
        return cls(
            file_path=str(result.file_path),
            backup_path=str(result.backup_path),
            source_sha256=result.source_sha256,
            saved_sha256=result.repaired_sha256,
            output_encoding=result.output_encoding,
            changed_lines=result.changed_lines,
        )
