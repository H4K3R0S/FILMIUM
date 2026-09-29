# core/domains/filmium/jobs/atom_reindex.py
# ==========          UNIVERZALNI POSAO: atom_reindex          ==========
"""Puna re-indeksacija FTS5 indeksa atoma — odrzava leksicku pretragu svezu
(v. core/domains/filmium/search/fts_index.py). Isti posao postoji u sva 4
domena (deljeni oblik, domenski `fts_index` modul)."""
from __future__ import annotations

from core.cell.jobs import Job, JobContext
from core.domains.filmium.search import fts_index, vector_index


class AtomReindexJob(Job):
    id = "atom_reindex"
    opis = "Puna re-indeksacija FTS5 indeksa atoma (odrzava pretragu svezom)."
    raspored = "on-demand (run-once) / systemd --user timer"

    def run(self, ctx: JobContext) -> dict:
        ctx.progress(0, None, "rebuild FTS5 indeksa u toku...")
        count = fts_index.rebuild()
        # Vektor (Qdrant) re-sync: force=True daje CIST indeks (izbacuje log/
        # ustajale tacke, ubacuje nove). Best-effort — ne rusi posao ako Qdrant dole.
        vec = 0
        try:
            ctx.progress(count, None, "vektor (Qdrant) re-sync u toku...")
            vec = vector_index.sync("filmium", force=True)
        except Exception:  # noqa: BLE001
            vec = -1
        ctx.progress(count, count, f"gotovo (fts={count}, vektor={vec})")
        return {"indexed": count, "vector_indexed": vec}
