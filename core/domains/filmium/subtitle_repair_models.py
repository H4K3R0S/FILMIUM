from dataclasses import dataclass
from pathlib import Path

from core.domains.filmium.subtitle_inspector_models import (
    SubtitleInspectionResult,
    SubtitleRepairPreview,
)

# ==========          PRIPREMLJENA POPRAVKA          ==========

@dataclass(frozen=True)
class PreparedSubtitleRepair:
    """Pregled vezan za tacnu verziju originalne datoteke."""

    file_path: Path
    source_sha256: str
    inspection: SubtitleInspectionResult
    preview: SubtitleRepairPreview


# ==========          ZAHTEV ZA UPIS          ==========

@dataclass(frozen=True)
class SubtitleRepairApplyRequest:
    """Eksplicitna potvrda upisa prethodno pregledane popravke."""

    prepared: PreparedSubtitleRepair
    confirmed: bool


# ==========          REZULTAT UPISA          ==========

@dataclass(frozen=True)
class SubtitleRepairApplyResult:
    """Rezultat popravke sa putanjom sacuvane rezervne kopije."""

    file_path: Path
    backup_path: Path
    source_sha256: str
    repaired_sha256: str
    output_encoding: str
    changed_lines: int