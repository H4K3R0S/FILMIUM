"""Model nalaza pri proveri fajla koji ulazi u biblioteku."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class GuardStatus(str, Enum):
    """Ishod provere. Vrednosti su iste kao FILMIUM `SecurityStatus`."""

    UNKNOWN = "unknown"
    CLEAN = "clean"
    SUSPICIOUS = "suspicious"
    MALWARE = "malware"


@dataclass(frozen=True)
class GuardReport:
    """Nalaz jedne provere."""

    status: GuardStatus
    threats: tuple[str, ...]
    digest: str
