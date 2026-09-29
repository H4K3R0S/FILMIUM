# ========== ŠEME AUTO-IMPORT-a (API) ==========
from __future__ import annotations

from pydantic import BaseModel, Field

from core.domains.filmium.auto_import.auto_import_models import (
    AutoImportRule,
    DetectedFile,
)

# ==========          PRAVILO (ZAHTEV)          ==========

class AutoImportRuleRequest(BaseModel):
    folder_path: str = Field(..., min_length=1)
    file_types: list[str] = Field(default_factory=lambda: ["mp4", "mkv", "avi"])
    min_size_mb: int = 100
    auto_scan: bool = True
    auto_import: bool = False
    target_library_id: int | None = None
    security_scan: bool = False


# ==========          PRAVILO (ODGOVOR)          ==========

class AutoImportRuleResponse(BaseModel):
    id: int
    folder_path: str
    file_types: list[str]
    min_size_mb: int
    auto_scan: bool
    auto_import: bool
    target_library_id: int | None
    security_scan: bool
    created_at: str

    @classmethod
    def from_domain(cls, rule: AutoImportRule) -> AutoImportRuleResponse:
        return cls(
            id=rule.id,
            folder_path=rule.folder_path,
            file_types=list(rule.file_types),
            min_size_mb=rule.min_size_mb,
            auto_scan=rule.auto_scan,
            auto_import=rule.auto_import,
            target_library_id=rule.target_library_id,
            security_scan=rule.security_scan,
            created_at=rule.created_at.isoformat(),
        )


# ==========          PRAĆEN FOLDER          ==========

class MonitoredFolderResponse(BaseModel):
    folder_path: str
    is_active: bool
    rule_id: int | None = None
    last_check: str | None = None


# ==========          DETEKTOVAN FAJL          ==========

class DetectedFileResponse(BaseModel):
    id: int
    file_path: str
    file_size: int
    rule_id: int | None
    status: str
    security_status: str
    scan_result: dict | None
    detected_at: str

    @classmethod
    def from_domain(cls, item: DetectedFile) -> DetectedFileResponse:
        return cls(
            id=item.id,
            file_path=item.file_path,
            file_size=item.file_size,
            rule_id=item.rule_id,
            status=item.status.value,
            security_status=item.security_status.value,
            scan_result=item.scan_result,
            detected_at=item.detected_at.isoformat(),
        )
