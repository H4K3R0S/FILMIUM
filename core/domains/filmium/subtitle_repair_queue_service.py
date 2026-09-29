from core.domains.filmium.subtitle_repair_models import (
    PreparedSubtitleRepair,
)
from core.domains.filmium.subtitle_repair_queue_models import (
    SubtitleRepairQueueCreate,
    SubtitleRepairQueueItem,
    SubtitleRepairQueueStatus,
)
from core.domains.filmium.subtitle_repair_queue_repository import (
    SubtitleRepairQueueRepository,
)

# ==========          GRESKE REDA POPRAVKE          ==========

class SubtitleRepairQueueNotFoundError(LookupError):
    """Oznacava da trazena stavka reda ne postoji."""


class SubtitleRepairQueueValidationError(ValueError):
    """Oznacava neispravne podatke automatskog nalaza."""


# ==========          SERVIS REDA POPRAVKE          ==========

class SubtitleRepairQueueService:
    """Automatski dodaje lose prevode i cuva korisnicke odluke."""

    def __init__(
        self,
        repository: SubtitleRepairQueueRepository,
    ) -> None:
        self._repository = repository

    def enqueue_if_needed(
        self,
        prepared: PreparedSubtitleRepair,
        media_id: int | None = None,
        source_id: int | None = None,
    ) -> SubtitleRepairQueueItem | None:
        """Dodaje samo prevod za koji inspektor trazi popravku."""

        if not prepared.inspection.needs_repair:
            return None

        confidence = prepared.inspection.language_confidence

        if not 0 <= confidence <= 1:
            raise SubtitleRepairQueueValidationError(
                "Pouzdanost jezika mora biti izmedju 0 i 1."
            )

        return self._repository.upsert(
            SubtitleRepairQueueCreate(
                media_id=media_id,
                source_id=source_id,
                file_path=str(prepared.file_path),
                file_name=prepared.file_path.name,
                source_sha256=prepared.source_sha256,
                detected_encoding=(
                    prepared.inspection.detected_encoding
                ),
                detected_language_code=(
                    prepared.inspection.detected_language_code
                ),
                language_confidence=confidence,
                issue_count=len(prepared.inspection.issues),
            )
        )

    def list_items(
        self,
        status: SubtitleRepairQueueStatus | None = None,
    ) -> tuple[SubtitleRepairQueueItem, ...]:
        """Vraca stavke za Uploads odeljak Popravi prevod."""

        return self._repository.list_items(status)

    def get_item(
        self,
        item_id: int,
    ) -> SubtitleRepairQueueItem:
        """Vraca jednu stavku ili prijavljuje da ne postoji."""

        item = self._repository.get(item_id)

        if item is None:
            raise SubtitleRepairQueueNotFoundError(
                f"Stavka popravke prevoda sa ID-em {item_id} ne postoji."
            )

        return item


    def find_by_path(
        self,
        file_path: str,
    ) -> SubtitleRepairQueueItem | None:
        """Vraca raniju odluku za putanju, ako postoji."""

        return self._repository.get_by_path(file_path)

    

    def set_status(
        self,
        item_id: int,
        status: SubtitleRepairQueueStatus,
    ) -> SubtitleRepairQueueItem:
        """Menja odluku korisnika za jednu stavku."""

        updated = self._repository.set_status(
            item_id,
            SubtitleRepairQueueStatus(status),
        )

        if updated is None:
            raise SubtitleRepairQueueNotFoundError(
                f"Stavka popravke prevoda sa ID-em {item_id} ne postoji."
            )

        return updated

    def clear_scan_results(self, confirmed: bool) -> int:
        """Brise samo privremene rezultate nakon izricite potvrde."""

        if not confirmed:
            raise SubtitleRepairQueueValidationError(
                "Brisanje rezultata skeniranja mora biti potvrdjeno."
            )

        return self._repository.clear_scan_results()
