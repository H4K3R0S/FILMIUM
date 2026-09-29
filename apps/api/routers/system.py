"""Zdravlje zavisnosti ćelije: status, sažetak i (opciona) instalacija.

Isti ugovor kao CORE `/api/v1/system/dependencies` — GUI dependency indikator
u dnu sidebar-a čita ovaj ruter. Registar zavisnosti je u
`core/foundation/dependencies.py` (po domenu), pa se ćelija sama opisuje.
"""

from fastapi import APIRouter, HTTPException

from apps.api.schemas.system import (
    DependencyStatusResponse,
    InstallJobResponse,
    SystemDependenciesResponse,
)
from core.foundation.dependencies import (
    evaluate_dependencies,
    overall_status,
)
from core.foundation.installer import (
    get_install_status,
    start_install,
)

router = APIRouter(
    prefix="/api/v1/system",
    tags=["System"],
)


# ==========          ZDRAVLJE ZAVISNOSTI          ==========

@router.get("/dependencies", response_model=SystemDependenciesResponse)
def get_system_dependencies() -> SystemDependenciesResponse:
    """Vraća status svih zavisnosti i sažeti nivo problema."""

    statuses = evaluate_dependencies()

    return SystemDependenciesResponse(
        status=overall_status(statuses),
        dependencies=[
            DependencyStatusResponse.from_status(status)
            for status in statuses
        ],
    )


# ==========          INSTALACIJA ZAVISNOSTI          ==========

@router.post(
    "/dependencies/{key}/install",
    response_model=InstallJobResponse,
)
def install_dependency(key: str) -> InstallJobResponse:
    """Pokreće instalaciju alata po ključu (skripta iz servera)."""

    try:
        job = start_install(key)
    except KeyError:
        raise HTTPException(
            status_code=404,
            detail=f"Nema automatske instalacije za '{key}'.",
        )
    except RuntimeError as error:
        raise HTTPException(status_code=409, detail=str(error))

    return InstallJobResponse.from_job(job)


@router.get("/install/status", response_model=InstallJobResponse)
def install_status() -> InstallJobResponse:
    """Status trenutnog install posla (za polling iz GUI-ja)."""

    return InstallJobResponse.from_job(get_install_status())
