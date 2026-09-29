# core/domains/filmium/jobs/subtitle_script_pair.py
# ==========          POSAO: subtitle_script_pair          ==========
"""Za svaki prevod (.srt) koji ima SAMO jedno pismo napravi drugo (latinica↔ćirilica).

Isti deterministički alat kao TMDB opisi (`transliteration.py`), SRT-svesno
(ne dira indeks/timecode/HTML tagove). Idempotentno: ako par-fajl već postoji
(po imenu `sr-Latn` ↔ `sr-Cyrl`), preskače. Radi u pozadini (boot best-effort).
"""
from __future__ import annotations

import contextlib
import sqlite3
from pathlib import Path

from core.cell.jobs import Job, JobContext
from core.domains.filmium.subtitle_transliterate import (
    _LANG_RE,
    _target_path,
    is_serbian_subtitle,
    transliterate_subtitle_file,
)
from core.domains.filmium.transliteration import detect_script
from core.foundation.paths import core_paths


@contextlib.contextmanager
def _catalog():
    con = sqlite3.connect(str(core_paths.data / "filmium.db"))
    con.row_factory = sqlite3.Row
    try:
        yield con
    finally:
        con.close()


def _subtitle_paths() -> list[Path]:
    """Apsolutne putanje svih .srt prevoda iz kataloga (postojećih na disku)."""
    try:
        with _catalog() as con:
            rows = con.execute(
                """
                SELECT lr.path AS root, s.relative_directory AS rel_dir,
                       f.relative_path AS rel
                FROM filmium_media_files f
                JOIN filmium_media_sources s ON f.source_id = s.id
                JOIN filmium_library_roots lr ON s.library_root_id = lr.id
                WHERE f.role = 'subtitle' AND lower(f.relative_path) LIKE '%.srt'
                """
            ).fetchall()
    except sqlite3.Error:
        return []
    out: list[Path] = []
    for r in rows:
        p = Path(r["root"]).joinpath(r["rel_dir"] or "", r["rel"] or "")
        # SAMO srpski prevodi (transliteracija je sr Latin↔Ćirilica) — .en/.hr… preskoči.
        if is_serbian_subtitle(p.name) and p.is_file():
            out.append(p)
    return out


def _pair_exists(path: Path) -> bool:
    """Da li već postoji fajl drugog pisma. Po srpskom kodu (jeftino) ili čitanjem."""
    match = _LANG_RE.search(path.name)
    script_code = (match.group(2) or "").lower() if match else ""
    if "latn" in script_code or "latin" in script_code:
        to_cyrillic = True                      # latinica → par je ćirilica
    elif "cyrl" in script_code or "cyr" in script_code:
        to_cyrillic = False                     # ćirilica → par je latinica
    else:
        # Bare .sr/.srp bez pisma → pročitaj i detektuj (ređe).
        try:
            to_cyrillic = detect_script(
                path.read_bytes().decode("utf-8", "replace")
            ) == "latin"
        except OSError:
            return True  # ne diramo ako ne možemo da pročitamo
    return _target_path(path, to_cyrillic).exists()


class SubtitleScriptPairJob(Job):
    id = "subtitle_script_pair"
    opis = (
        "Za svaki prevod bez para pisma (latinica/ćirilica) napravi drugo pismo "
        "(deterministička transliteracija, SRT-svesno)."
    )
    raspored = "best-effort pri boot-u + on-demand"

    def run(self, ctx: JobContext) -> dict:
        paths = _subtitle_paths()
        total = len(paths)
        created = 0
        skipped = 0
        failed = 0
        for index, path in enumerate(paths):
            if ctx.should_stop():
                break
            try:
                if _pair_exists(path):
                    skipped += 1
                else:
                    transliterate_subtitle_file(path)
                    created += 1
            except Exception:  # noqa: BLE001 — jedan fajl ne ruši posao
                failed += 1
            if index % 50 == 0:
                ctx.progress(index, total, f"pismo-parovi: {created} novih")
        ctx.progress(
            total, total,
            f"gotovo: {created} novih, {skipped} već postoji, {failed} grešaka",
        )
        return {"created": created, "skipped": skipped, "failed": failed, "total": total}
