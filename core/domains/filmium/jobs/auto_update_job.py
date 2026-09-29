# core/domains/filmium/jobs/auto_update_job.py
# ==========          UVEZENI POSAO: bulk auto-update          ==========
"""Omotac oko POSTOJECEG bulk auto-update posla
(`core/domains/filmium/auto_update_cron.py`, vec izlozenog na
`/api/v1/filmium/auto-update/{status,start,stop}` preko
`apps/api/routers/filmium_cron.py`) kao `Job` u jedinstvenom registru.

NE DUPLIRA logiku: `run()`/`live_status()`/`live_stop()` samo pozivaju
postojece `cron.start/status/stop` funkcije. Stari
`/api/v1/filmium/auto-update/*` ruter OSTAJE netaknut (kompatibilnost) —
ovaj Job ga samo cini VIDLJIVIM i pod `/api/v1/filmium/jobs` takodje.

`cron.start()` sam upravlja svojim (pod)procesom i stanjem u
`data/filmium_auto_update/state.json`, pa je stvarni izvor istine ZA STATUS
taj fajl, ne generic nit-wrapper iz `core/cell/jobs.py` — otud
`live_status`/`live_stop` hook-ovi (v. Job.live_status docstring)."""
from __future__ import annotations

from core.cell.jobs import Job, JobContext
from core.domains.filmium import auto_update_cron as cron


class AutoUpdateBulkJob(Job):
    id = "filmium_auto_update"
    opis = (
        "Bulk auto-update svih filmova/serija (postojeci auto_update_cron, "
        "vidljiv i na /api/v1/filmium/auto-update/*)."
    )
    raspored = "on-demand (start/stop) — nastavlja gde je stao pri sledecem start-u"

    def run(self, ctx: JobContext) -> dict:
        # Lenj uvoz: `apps.api.dependencies` gradi servise vec pri svom
        # uvozu (v. cell_app.py docstring), ali ovaj CORE modul namerno ne
        # zavisi od `apps` na modulskom nivou (isti duh kao
        # core/domains/filmium/search/hybrid_retriever.py).
        try:
            from apps.api.dependencies import get_filmium_service

            service = get_filmium_service()
        except Exception as error:  # noqa: BLE001 — tolerantno
            return {"error": f"FilmiumService nije dostupan: {error}"}
        return cron.start(service)

    def live_status(self) -> dict | None:
        try:
            state = cron.status()
        except Exception:  # noqa: BLE001
            return None
        if not isinstance(state, dict):
            return None
        status = state.get("status") or "idle"
        finished_at = state.get("updated_at") if status in ("done", "stopped") else None
        return {
            "status": status,
            "started_at": state.get("started_at"),
            "finished_at": finished_at,
            "progress": {
                "done": state.get("done_count", 0),
                "total": state.get("total"),
                "message": f"kursor {state.get('cursor', 0)}/{state.get('total', 0)}",
            },
            "result": {
                "error_count": state.get("error_count", 0),
                "errors": state.get("errors", []),
            },
        }

    def live_stop(self) -> dict | None:
        try:
            state = cron.stop()
        except Exception:  # noqa: BLE001
            return None
        if not isinstance(state, dict):
            return None
        return self.live_status() or {"status": state.get("status", "stopped")}
