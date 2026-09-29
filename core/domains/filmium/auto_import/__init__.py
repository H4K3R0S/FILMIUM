# ========== FILMIUM AUTO-IMPORT ==========
# Domenska logika automatskog uvoza: koristi CORE System Layer (file_monitor)
# kao mehanizam, a ovde drži pravila/stanje i odlučuje šta se dešava sa fajlom.
from core.domains.filmium.auto_import.auto_import_models import (
    AutoImportRule,
    AutoImportRuleCreate,
    DetectedFile,
    DetectedFileStatus,
    SecurityStatus,
)
from core.domains.filmium.auto_import.auto_import_repository import (
    AutoImportRepository,
)
from core.domains.filmium.auto_import.auto_import_service import (
    AutoImportService,
)
from core.domains.filmium.auto_import.file_classifier import (
    VIDEO_EXTENSIONS,
    file_matches_rule,
    is_video_file,
)

__all__ = [
    "VIDEO_EXTENSIONS",
    "AutoImportRepository",
    "AutoImportRule",
    "AutoImportRuleCreate",
    "AutoImportService",
    "DetectedFile",
    "DetectedFileStatus",
    "SecurityStatus",
    "file_matches_rule",
    "is_video_file",
]
