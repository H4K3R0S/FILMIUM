# ========== ROUTER: FILMIUM AUTO-IMPORT ==========
# Izlaže postojeći AutoImportService: praćeni folderi + detektovani fajlovi.
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status

from apps.api.schemas.filmium_auto_import import (
    AutoImportRuleRequest,
    AutoImportRuleResponse,
    DetectedFileResponse,
    MonitoredFolderResponse,
)
from core.domains.filmium.auto_import import (
    AutoImportRuleCreate,
    AutoImportService,
    DetectedFileStatus,
)

router = APIRouter(
    prefix="/api/v1/filmium/auto-import",
    tags=["FILMIUM Auto-Import"],
)


# ==========          DEPENDENCY          ==========

def get_service() -> AutoImportService:
    # Lenjo: auto-import/file-monitor graf se gradi tek na prvi zahtev.
    from apps.api import auto_import_runtime

    return auto_import_runtime.get_service()


# ==========          PRAĆENI FOLDERI          ==========

@router.post("/folders", response_model=AutoImportRuleResponse,
             status_code=status.HTTP_201_CREATED)
def add_monitored_folder(
    payload: AutoImportRuleRequest,
    service: AutoImportService = Depends(get_service),
) -> AutoImportRuleResponse:
    """Dodaje folder za automatsko praćenje sa pravilom uvoza."""

    rule = service.add_monitored_folder(AutoImportRuleCreate(
        folder_path=payload.folder_path,
        file_types=payload.file_types,
        min_size_mb=payload.min_size_mb,
        auto_scan=payload.auto_scan,
        auto_import=payload.auto_import,
        target_library_id=payload.target_library_id,
        security_scan=payload.security_scan,
    ))
    return AutoImportRuleResponse.from_domain(rule)


@router.get("/folders", response_model=list[MonitoredFolderResponse])
def list_monitored_folders(
    service: AutoImportService = Depends(get_service),
) -> list[MonitoredFolderResponse]:
    """Vraća praćene foldere i njihov status."""

    return [MonitoredFolderResponse(**f) for f in service.get_monitored_folders()]


@router.delete("/folders", status_code=status.HTTP_204_NO_CONTENT)
def remove_monitored_folder(
    path: str = Query(..., min_length=1),
    service: AutoImportService = Depends(get_service),
) -> None:
    """Uklanja folder iz praćenja."""

    service.remove_monitored_folder(path)


# ==========          DETEKTOVANI FAJLOVI          ==========

@router.get("/detected", response_model=list[DetectedFileResponse])
def get_detected_files(
    status_filter: str | None = Query(default=None, alias="status"),
    service: AutoImportService = Depends(get_service),
) -> list[DetectedFileResponse]:
    """Vraća detektovane fajlove; opciono filtrirano po statusu."""

    parsed: DetectedFileStatus | None = None
    if status_filter is not None:
        try:
            parsed = DetectedFileStatus(status_filter)
        except ValueError as error:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=f"Nepoznat status: {status_filter}",
            ) from error

    return [DetectedFileResponse.from_domain(d) for d in service.get_detected_files(parsed)]


@router.post("/confirm/{file_id}", response_model=DetectedFileResponse)
def confirm_import(
    file_id: int,
    service: AutoImportService = Depends(get_service),
) -> DetectedFileResponse:
    """Potvrđuje uvoz detektovanog fajla."""

    result = service.confirm_import(file_id)
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail="Detektovani fajl nije pronađen.")
    return DetectedFileResponse.from_domain(result)


@router.post("/reject/{file_id}", response_model=DetectedFileResponse)
def reject_import(
    file_id: int,
    service: AutoImportService = Depends(get_service),
) -> DetectedFileResponse:
    """Odbacuje detektovani fajl."""

    result = service.reject_import(file_id)
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail="Detektovani fajl nije pronađen.")
    return DetectedFileResponse.from_domain(result)
