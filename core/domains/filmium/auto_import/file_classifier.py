# ========== KLASIFIKATOR FAJLOVA ==========
# Odlučuje da li je fajl video i da li zadovoljava pravilo auto-uvoza.
from __future__ import annotations

import os

from core.domains.filmium.auto_import.auto_import_models import AutoImportRule

# Podržane video ekstenzije (bez tačke, mala slova)
VIDEO_EXTENSIONS = frozenset({
    "mp4", "mkv", "avi", "mov", "wmv", "flv", "webm", "m4v", "mpg", "mpeg", "ts",
})


def _ext(path: str) -> str:
    return os.path.splitext(path)[1].lstrip(".").lower()


def is_video_file(path: str) -> bool:
    return _ext(path) in VIDEO_EXTENSIONS


def file_matches_rule(path: str, rule: AutoImportRule, *, size_bytes: int | None = None) -> bool:
    # Tip fajla mora biti u pravilu (ili opšte video ako lista prazna).
    ext = _ext(path)
    allowed = {t.lstrip(".").lower() for t in (rule.file_types or [])}
    if allowed:
        if ext not in allowed:
            return False
    elif not is_video_file(path):
        return False

    # Minimalna veličina (MB). size_bytes se može proslediti radi testiranja.
    if size_bytes is None:
        try:
            size_bytes = os.path.getsize(path)
        except OSError:
            return False
    return size_bytes >= rule.min_size_mb * 1024 * 1024
