# ========== MODELI AUTO-IMPORT-a ==========
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


# ========== STATUSI ==========
class DetectedFileStatus(str, Enum):
    DETECTED = "detected"     # tek primećen
    SCANNING = "scanning"     # u obradi
    READY = "ready"           # spreman za potvrdu uvoza
    IMPORTED = "imported"     # uvezen
    REJECTED = "rejected"     # odbačen


class SecurityStatus(str, Enum):
    UNKNOWN = "unknown"
    CLEAN = "clean"
    SUSPICIOUS = "suspicious"
    MALWARE = "malware"


# ========== PRAVILO AUTO-UVOZA ==========
@dataclass
class AutoImportRuleCreate:
    folder_path: str
    file_types: list[str] = field(default_factory=lambda: ["mp4", "mkv", "avi"])
    min_size_mb: int = 100          # ignoriši sitne fajlove
    auto_scan: bool = True          # automatski skeniraj metapodatke
    auto_import: bool = False       # automatski uvezi (ili samo detektuj)
    target_library_id: int | None = None
    security_scan: bool = False     # KALIMA provera pre uvoza


@dataclass
class AutoImportRule(AutoImportRuleCreate):
    id: int = 0
    created_at: datetime = field(default_factory=datetime.now)


# ========== DETEKTOVAN FAJL ==========
@dataclass
class DetectedFile:
    file_path: str
    file_size: int
    id: int = 0
    rule_id: int | None = None
    status: DetectedFileStatus = DetectedFileStatus.DETECTED
    security_status: SecurityStatus = SecurityStatus.UNKNOWN
    scan_result: dict | None = None
    detected_at: datetime = field(default_factory=datetime.now)
