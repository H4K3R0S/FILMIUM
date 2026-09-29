from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status

from apps.api.dependencies import (
    get_subtitle_repair_queue_service,
    get_subtitle_repair_service,
)
from apps.api.schemas.filmium_subtitles import (
    SubtitleEditPreviewRequest,
    SubtitleInspectionResponse,
    SubtitleInspectRequest,
    SubtitleManualSaveRequest,
    SubtitleManualSaveResponse,
    SubtitleQueueStatusRequest,
    SubtitleRepairQueueResponse,
    SubtitleRepairRequest,
    SubtitleRepairResultResponse,
)
from core.domains.filmium.subtitle_inspector_service import (
    SubtitleInspectionValidationError,
)
from core.domains.filmium.subtitle_repair_models import (
    SubtitleRepairApplyRequest,
)
from core.domains.filmium.subtitle_repair_queue_models import (
    SubtitleRepairQueueStatus,
)
from core.domains.filmium.subtitle_repair_queue_service import (
    SubtitleRepairQueueNotFoundError,
    SubtitleRepairQueueService,
    SubtitleRepairQueueValidationError,
)
from core.domains.filmium.subtitle_repair_service import (
    SubtitleRepairConfirmationError,
    SubtitleRepairConflictError,
    SubtitleRepairNotSafeError,
    SubtitleRepairService,
    SubtitleRepairValidationError,
)

router = APIRouter(
    prefix="/api/v1/filmium/subtitles",
    tags=["FILMIUM Subtitles"],
)

RepairServiceDependency = Annotated[
    SubtitleRepairService,
    Depends(get_subtitle_repair_service),
]
QueueServiceDependency = Annotated[
    SubtitleRepairQueueService,
    Depends(get_subtitle_repair_queue_service),
]


# ==========          ANALIZA          ==========

@router.post(
    "/inspect",
    response_model=SubtitleInspectionResponse,
)
def inspect_subtitle(
    request: SubtitleInspectRequest,
    repair_service: RepairServiceDependency,
    queue_service: QueueServiceDependency,
) -> SubtitleInspectionResponse:
    """Analizira prevod i po potrebi ga dodaje u trajni red."""

    try:
        prepared = repair_service.prepare(Path(request.file_path))
        queue_item = queue_service.enqueue_if_needed(
            prepared,
            media_id=request.media_id,
            source_id=request.source_id,
        )
    except (
        SubtitleInspectionValidationError,
        SubtitleRepairValidationError,
    ) as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(error),
        ) from error

    return SubtitleInspectionResponse.from_domain(
        prepared,
        queue_item,
    )


# ==========          EDITOR MOD (AD-HOC PO PUTANJI)          ==========

@router.post(
    "/edit/preview",
    response_model=SubtitleInspectionResponse,
)
def preview_subtitle_for_edit(
    request: SubtitleEditPreviewRequest,
    repair_service: RepairServiceDependency,
) -> SubtitleInspectionResponse:
    """Učitava bilo koji SRT po putanji za pregled/editovanje (bez reda)."""

    try:
        prepared = repair_service.prepare(Path(request.file_path))
    except (
        SubtitleInspectionValidationError,
        SubtitleRepairValidationError,
    ) as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(error),
        ) from error

    return SubtitleInspectionResponse.from_domain(prepared, None)


@router.post(
    "/edit/save",
    response_model=SubtitleManualSaveResponse,
)
def save_edited_subtitle(
    request: SubtitleManualSaveRequest,
    repair_service: RepairServiceDependency,
) -> SubtitleManualSaveResponse:
    """Snima ručno izmenjen sadržaj u isti fajl (sha provera + backup)."""

    try:
        result = repair_service.save_edited(
            file_path=Path(request.file_path),
            source_sha256=request.source_sha256,
            content=request.content,
            confirmed=request.confirmed,
        )
    except SubtitleRepairConfirmationError as error:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(error),
        ) from error
    except SubtitleRepairConflictError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(error),
        ) from error
    except (
        SubtitleInspectionValidationError,
        SubtitleRepairValidationError,
        SubtitleRepairNotSafeError,
    ) as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(error),
        ) from error

    return SubtitleManualSaveResponse.from_domain(result)


@router.post("/transliterate")
def transliterate_subtitle(
    request: SubtitleEditPreviewRequest,
    repair_service: RepairServiceDependency,
) -> dict:
    """Prepoznaj pismo prevoda (latinica/ćirilica) i napravi drugo pismo u nov fajl."""

    try:
        return repair_service.transliterate(Path(request.file_path))
    except (
        SubtitleInspectionValidationError,
        SubtitleRepairValidationError,
    ) as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(error),
        ) from error


# ==========          RED POPRAVKE          ==========

@router.get(
    "/repair-queue",
    response_model=list[SubtitleRepairQueueResponse],
)
def list_repair_queue(
    queue_service: QueueServiceDependency,
    queue_status: SubtitleRepairQueueStatus | None = Query(
        default=None,
        alias="status",
    ),
) -> list[SubtitleRepairQueueResponse]:
    """Vraca sve ili filtrirane stavke odeljka Popravi prevod."""

    return [
        SubtitleRepairQueueResponse.from_domain(item)
        for item in queue_service.list_items(queue_status)
    ]


@router.delete(
    "/repair-queue",
    response_model=dict[str, int],
)
def clear_repair_queue_scan_results(
    queue_service: QueueServiceDependency,
    confirmed: bool = Query(default=False),
) -> dict[str, int]:
    """Brise nalaze skeniranja bez brisanja prevoda i trajnih odluka."""

    try:
        deleted_count = queue_service.clear_scan_results(confirmed)
    except SubtitleRepairQueueValidationError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error),
        ) from error

    return {"deleted_count": deleted_count}


@router.get(
    "/repair-queue/{item_id}",
    response_model=SubtitleRepairQueueResponse,
)
def get_repair_queue_item(
    item_id: int,
    queue_service: QueueServiceDependency,
) -> SubtitleRepairQueueResponse:
    """Vraca jednu stavku reda."""

    try:
        item = queue_service.get_item(item_id)
    except SubtitleRepairQueueNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(error),
        ) from error

    return SubtitleRepairQueueResponse.from_domain(item)


@router.patch(
    "/repair-queue/{item_id}/status",
    response_model=SubtitleRepairQueueResponse,
)
def update_repair_queue_status(
    item_id: int,
    request: SubtitleQueueStatusRequest,
    queue_service: QueueServiceDependency,
) -> SubtitleRepairQueueResponse:
    """Cuva odluku: pregledano, odbaceno ili trajno ignorisano."""

    try:
        item = queue_service.set_status(item_id, request.status)
    except SubtitleRepairQueueNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(error),
        ) from error

    return SubtitleRepairQueueResponse.from_domain(item)


# ==========          PREGLED I POPRAVKA          ==========

@router.post(
    "/repair-queue/{item_id}/preview",
    response_model=SubtitleInspectionResponse,
)
def preview_queued_repair(
    item_id: int,
    repair_service: RepairServiceDependency,
    queue_service: QueueServiceDependency,
) -> SubtitleInspectionResponse:
    """Ponovo analizira stavku i prijavljuje promenu fajla."""

    try:
        queue_item = queue_service.get_item(item_id)
        prepared = repair_service.prepare(
            Path(queue_item.file_path)
        )
    except SubtitleRepairQueueNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(error),
        ) from error
    except (
        SubtitleInspectionValidationError,
        SubtitleRepairValidationError,
    ) as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(error),
        ) from error

    if prepared.source_sha256 != queue_item.source_sha256:
        queue_service.enqueue_if_needed(
            prepared,
            media_id=queue_item.media_id,
            source_id=queue_item.source_id,
        )
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Datoteka je promenjena od poslednje analize. "
                "Red je osvezen; otvorite novi pregled."
            ),
        )

    reviewed = queue_service.set_status(
        item_id,
        SubtitleRepairQueueStatus.REVIEWED,
    )
    return SubtitleInspectionResponse.from_domain(
        prepared,
        reviewed,
    )


@router.post(
    "/repair-queue/{item_id}/repair",
    response_model=SubtitleRepairResultResponse,
)
def repair_queued_subtitle(
    item_id: int,
    request: SubtitleRepairRequest,
    repair_service: RepairServiceDependency,
    queue_service: QueueServiceDependency,
) -> SubtitleRepairResultResponse:
    """Posle potvrde pravi backup i upisuje proverenu popravku."""

    try:
        queue_item = queue_service.get_item(item_id)
        prepared = repair_service.prepare(
            Path(queue_item.file_path)
        )

        if prepared.source_sha256 != queue_item.source_sha256:
            queue_service.enqueue_if_needed(
                prepared,
                media_id=queue_item.media_id,
                source_id=queue_item.source_id,
            )
            raise SubtitleRepairConflictError(
                "Datoteka je promenjena od poslednje analize."
            )

        result = repair_service.apply(
            SubtitleRepairApplyRequest(
                prepared=prepared,
                confirmed=request.confirmed,
            )
        )
        repaired_item = queue_service.set_status(
            item_id,
            SubtitleRepairQueueStatus.REPAIRED,
        )
    except SubtitleRepairQueueNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(error),
        ) from error
    except SubtitleRepairConfirmationError as error:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(error),
        ) from error
    except SubtitleRepairConflictError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(error),
        ) from error
    except (
        SubtitleInspectionValidationError,
        SubtitleRepairValidationError,
        SubtitleRepairNotSafeError,
    ) as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(error),
        ) from error

    return SubtitleRepairResultResponse.from_domain(
        result,
        repaired_item,
    )

