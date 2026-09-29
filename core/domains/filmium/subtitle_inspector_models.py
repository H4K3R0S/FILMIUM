from dataclasses import dataclass
from enum import StrEnum

# ==========          TIP PROBLEMA PREVODA          ==========

class SubtitleIssueType(StrEnum):
    """Problemi koje FILMIUM moze bezbedno da prijavi."""

    INVALID_ENCODING = "invalid_encoding"
    MOJIBAKE = "mojibake"
    REPLACEMENT_CHARACTER = "replacement_character"
    SUSPICIOUS_CHARACTER = "suspicious_character"
    INVALID_SRT_STRUCTURE = "invalid_srt_structure"
    CREDIT_LINE = "credit_line"
    # Zvučna oznaka za gluve/nagluve u uglastim zagradama, npr. [Grgljanje],
    # [Zvižduci] — uklanja se iz prevoda.
    BRACKET_CUE = "bracket_cue"
    # „Typewriter" potpis: fraza (npr. „Owned by Vajira Lasantha") ispisana
    # slovo-po-slovo kroz niz kratkih uzastopnih cue-ova — ceo niz se uklanja.
    PROGRESSIVE_WATERMARK = "progressive_watermark"
    # Fajl nije tekstualni prevod — dominiraju binarni/kontrolni bajtovi
    # (moguće preimenovan izvršni/šifrovan/oštećen fajl → potencijalno opasno).
    BINARY_OR_SUSPICIOUS = "binary_or_suspicious"


class SubtitleIssueSeverity(StrEnum):
    """Nivo vaznosti pronadjenog problema."""

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


# ==========          PRONADJENI PROBLEM          ==========

@dataclass(frozen=True)
class SubtitleIssue:
    """Jedan problem pronadjen u datoteci prevoda."""

    issue_type: SubtitleIssueType
    severity: SubtitleIssueSeverity
    message: str
    line_number: int | None = None
    original_text: str | None = None
    suggested_text: str | None = None


# ==========          REZULTAT INSPEKCIJE          ==========

@dataclass(frozen=True)
class SubtitleInspectionResult:
    """Nedestruktivni rezultat analize jednog prevoda."""

    file_name: str
    detected_encoding: str
    detected_language_code: str | None
    language_confidence: float
    is_probably_serbian: bool
    needs_repair: bool
    issues: tuple[SubtitleIssue, ...]
    decoded_text: str


# ==========          PREGLED POPRAVKE          ==========

@dataclass(frozen=True)
class SubtitleRepairChange:
    """Jedna bezbedno predlozena promena reda."""

    line_number: int
    original_text: str
    repaired_text: str


@dataclass(frozen=True)
class SubtitleRepairPreview:
    """Pregled popravke koji mora biti potvrdjen pre upisa."""

    file_name: str
    detected_encoding: str
    detected_language_code: str | None
    original_text: str
    repaired_text: str
    changes: tuple[SubtitleRepairChange, ...]
    backup_required: bool = True
