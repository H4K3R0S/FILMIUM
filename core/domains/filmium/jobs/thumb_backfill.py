#!/usr/bin/env python3
"""thumb_backfill.py — pozadinski/cron backfill sličica: za sve video fajlove u bibliotekama
(DB `filmium_library_roots`) koji NEMAJU `.thumb` — napravi ga ffmpeg-om. Idempotentno, tolerantno.
Pokretanje: python -m core.domains.filmium.jobs.thumb_backfill [--dry] [--limit N] [--root PUTANJA]
FILMIUM ga zove za pozadinsko popunjavanje sličica koje fale."""
from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path

from core.domains.filmium.media_finders import VIDEO_EXTENSIONS
from core.domains.filmium.media_thumbnail import ensure_thumbnail, has_thumbnail

_DB = Path(__file__).resolve().parents[4] / "data" / "filmium.db"


def _roots(explicit: str) -> list[Path]:
    if explicit:
        p = Path(explicit)
        return [p] if p.is_dir() else []
    roots: list[Path] = []
    try:
        con = sqlite3.connect(str(_DB))
        con.row_factory = sqlite3.Row
        for row in con.execute("SELECT path FROM filmium_library_roots"):
            p = Path(row["path"])
            if p.is_dir():
                roots.append(p)
        con.close()
    except Exception:  # noqa: BLE001, S110
        pass
    return roots


def _videos(root: Path):
    for p in root.rglob("*"):
        if ".thumb" in p.parts:
            continue
        if p.suffix.lower() in VIDEO_EXTENSIONS and p.is_file():
            yield p



# ==========          POSAO (za jobs/cron registar + GUI)          ==========

from core.cell.jobs import Job, JobContext


class ThumbBackfillJob(Job):
    id = "thumb_backfill"
    opis = "Napravi .thumb sličice za sve video fajlove (film/epizode) koji ih nemaju."
    raspored = "on-demand (run-once) / pozadinski"

    def run(self, ctx: JobContext) -> dict:
        made = have = fail = 0
        for root in _roots(""):
            for v in _videos(root):
                if has_thumbnail(v):
                    have += 1
                    continue
                if ensure_thumbnail(v) is not None:
                    made += 1
                else:
                    fail += 1
                if (made + fail) % 20 == 0:
                    ctx.progress(made, None, f"napravljeno {made} sličica...")
        ctx.progress(made, made, f"gotovo (novih={made}, već_ima={have}, palo={fail})")
        return {"made": made, "have": have, "fail": fail}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry", action="store_true", help="samo prebroj, ne generiši")
    ap.add_argument("--limit", type=int, default=0, help="max novih (0=sve)")
    ap.add_argument("--root", default="", help="konkretan koren (inače iz DB)")
    a = ap.parse_args()
    roots = _roots(a.root)
    if not roots:
        print("STATUS: OK | nema library root-ova (DB prazan ili --root nevažeći)"); return
    made = have = fail = 0
    for root in roots:
        for v in _videos(root):
            if has_thumbnail(v):
                have += 1
                continue
            if a.limit and made >= a.limit:
                continue
            if a.dry:
                made += 1
                continue
            if ensure_thumbnail(v) is not None:
                made += 1
            else:
                fail += 1
    verb = "bi_napravio" if a.dry else "napravljeno"
    print(f"STATUS: OK | {verb}={made} već_ima={have} palo={fail} | root-ova={len(roots)}")


if __name__ == "__main__":
    main()
