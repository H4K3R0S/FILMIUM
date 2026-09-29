# ==========          FILMIUM BULK CRON — API          ==========
"""Start/stop/status za pozadinski masovni auto-update (/update-filmium)."""

from typing import Annotated

from fastapi import APIRouter, Depends

from apps.api.dependencies import get_filmium_service
from core.domains.filmium import auto_update_cron as cron
from core.domains.filmium.service import FilmiumService

router = APIRouter(prefix="/api/v1/filmium/auto-update", tags=["filmium-cron"])

FilmiumServiceDependency = Annotated[FilmiumService, Depends(get_filmium_service)]


@router.get("/status")
def cron_status() -> dict:
    """Trenutno stanje bulk posla (idle/running/done/stopped + progres)."""

    return cron.status()


@router.post("/start")
def cron_start(service: FilmiumServiceDependency) -> dict:
    """Napravi listu svih filmova/serija i pokreni pozadinski posao."""

    return cron.start(service)


@router.post("/stop")
def cron_stop() -> dict:
    """Zaustavi posao i ugasi proces ako radi."""

    return cron.stop()
