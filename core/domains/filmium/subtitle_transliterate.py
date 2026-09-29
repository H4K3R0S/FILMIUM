"""Transliteracija .srt u drugo pismo (latinica ↔ ćirilica).

Isti deterministički alat (`transliteration.py`) koji auto-update pipeline koristi za
TMDB opise; ovde primenjen na prevode, SRT-svesno (ne dira indeks/timecode/HTML tagove).
Detektuje pismo i pravi NOVI fajl sa zamenjenim kodom pisma (`sr-Latn` ↔ `sr-Cyrl`).
"""
from __future__ import annotations

import re
import shutil
from pathlib import Path
from typing import Any

from core.domains.filmium.subtitle_inspector_service import SubtitleInspectorService
from core.domains.filmium.transliteration import detect_script, transliterate_srt

# Srpski jezički kod (segment pre ekstenzije): .sr, .srp, .sr-Latn/-Cyrl/-Latin/-Cyr.
_LANG_RE = re.compile(r"\.(sr|srp)(-(?:latn|latin|cyrl|cyr))?(?=\.[^.]+$)", re.IGNORECASE)


def is_serbian_subtitle(name: str) -> bool:
    """Da li ime fajla nosi srpski jezički kod (ne .en/.hr/...)."""
    return _LANG_RE.search(name) is not None


def _target_path(path: Path, to_cyrillic: bool) -> Path:
    """Putanja izlaza sa srpskim kodom pisma zamenjenim/dodatim u imenu."""
    to_code = ".sr-Cyrl" if to_cyrillic else ".sr-Latn"
    name = path.name
    if _LANG_RE.search(name):
        new_name = _LANG_RE.sub(to_code, name)
    else:
        stem, dot, ext = name.rpartition(".")
        new_name = f"{stem}{to_code}.{ext}" if dot else f"{name}{to_code}"
    return path.with_name(new_name)


def transliterate_subtitle_file(path: Path) -> dict[str, Any]:
    """Detektuj pismo prevoda i napiši drugo pismo u novi fajl. Vrati sažetak."""
    content = path.read_bytes()
    inspection = SubtitleInspectorService().inspect(content, path.name)
    text = inspection.decoded_text

    from_script = detect_script(text)
    to_cyrillic = from_script == "latin"
    converted = transliterate_srt(text, to_cyrillic=to_cyrillic)

    target = _target_path(path, to_cyrillic)
    if target.resolve() == path.resolve():
        # Ime nije nosilo kod pisma pa bi se poklopilo — dodaj sufiks.
        target = path.with_name(f"{path.stem}.{'sr-Cyrl' if to_cyrillic else 'sr-Latn'}{path.suffix}")

    if target.exists():
        shutil.copyfile(target, target.with_suffix(target.suffix + ".bak"))
    target.write_text(converted, encoding="utf-8")

    return {
        "from_script": from_script,
        "to_script": "cyrillic" if to_cyrillic else "latin",
        "source": str(path),
        "created": str(target),
        "created_name": target.name,
    }
