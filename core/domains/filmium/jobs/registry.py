# core/domains/filmium/jobs/registry.py
# ==========          REGISTAR POSLOVA — FILMIUM          ==========
"""Modulski singleton `REGISTRY` (v. core/cell/jobs.py). Registracija samo
pravi lagane objekte (Lock/Event) — NE pokrece nista pri uvozu (v. duh
"lenji importi runtime-a": boot ne sme da cheka na ovo). `AutoUpdateBulkJob`
NE pokrece svoj subprocess pri registraciji — samo se prijavljuje u registar;
subprocess se pokrece isto kao i pre (na `start`), postojecom logikom u
`auto_update_cron.py`."""
from __future__ import annotations

from core.cell.jobs import JobRegistry
from core.domains.filmium.jobs.atom_reindex import AtomReindexJob
from core.domains.filmium.jobs.auto_update_job import AutoUpdateBulkJob
from core.domains.filmium.jobs.tmdb_people_import import TmdbPeopleImportJob

REGISTRY = JobRegistry(domain="filmium")
REGISTRY.register(AtomReindexJob())
REGISTRY.register(AutoUpdateBulkJob())
REGISTRY.register(TmdbPeopleImportJob())
from core.domains.filmium.jobs.thumb_backfill import ThumbBackfillJob

REGISTRY.register(ThumbBackfillJob())
from core.domains.filmium.jobs.subtitle_script_pair import (
    SubtitleScriptPairJob,
)

REGISTRY.register(SubtitleScriptPairJob())
