# ==========          FILMIUM JOBS — API          ==========
"""Jedinstveni jobs/cron API: `/api/v1/filmium/jobs` (v. core/cell/jobs.py i
UNAPREDJENJE/01-ARHITEKTURA/08-cron-i-skripte-sloj.md).

Tanak ruter: sva logika zivi u `core.domains.filmium.jobs.registry.REGISTRY`
(deljeni `core/cell/jobs.py` sloj). Nepoznat `job_id` -> 404.
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from core.domains.filmium.jobs.registry import REGISTRY

router = APIRouter(prefix="/api/v1/filmium", tags=["FILMIUM Jobs"])


def _require(job_id: str) -> None:
    if REGISTRY.get(job_id) is None:
        raise HTTPException(
            status_code=404, detail=f"posao '{job_id}' nije registrovan"
        )


@router.get("/jobs")
def list_jobs() -> list[dict]:
    """Lista registrovanih poslova: id, opis, raspored, poslednji run, status."""

    return REGISTRY.list()


@router.get("/jobs/{job_id}/status")
def job_status(job_id: str) -> dict:
    """Trenutno stanje posla (idle/running/done/stopped/error + progres)."""

    _require(job_id)
    return REGISTRY.status(job_id)


@router.post("/jobs/{job_id}/run-once")
def job_run_once(job_id: str) -> dict:
    """Pokrece posao SINHRONO — vraca se kad posao zavrsi (za kratke poslove)."""

    _require(job_id)
    return REGISTRY.run_once(job_id)


@router.post("/jobs/{job_id}/start")
def job_start(job_id: str) -> dict:
    """Pokrece posao u pozadinskoj niti (za duge poslove)."""

    _require(job_id)
    return REGISTRY.start(job_id)


@router.post("/jobs/{job_id}/stop")
def job_stop(job_id: str) -> dict:
    """Zaustavlja posao (kooperativno, ili preko `live_stop` za delegirane poslove)."""

    _require(job_id)
    return REGISTRY.stop(job_id)
