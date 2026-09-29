from dataclasses import dataclass

from core.domains.filmium.library_models import MediaFileRole
from core.domains.filmium.library_root_scanner import (
    LibraryRootScanResult,
)
from core.domains.filmium.subtitle_repair_queue_models import (
    SubtitleRepairQueueStatus,
)
from core.domains.filmium.subtitle_repair_queue_service import (
    SubtitleRepairQueueService,
)
from core.domains.filmium.subtitle_repair_service import (
    SubtitleRepairService,
)

# ==========          SAZETAK SKENIRANJA PREVODA          ==========

@dataclass(frozen=True)
class SubtitleScanSummary:
    """Rezultat automatske analize prevoda jedne biblioteke."""

    discovered_count: int = 0
    inspected_count: int = 0
    clean_count: int = 0
    needs_repair_count: int = 0
    queued_for_attention_count: int = 0
    unsupported_count: int = 0
    warnings: tuple[str, ...] = ()


# ==========          INTEGRACIJA SA SKENEROM          ==========

class SubtitleScanService:
    """Analizira SRT rezultate postojeceg biblioteckog skenera."""

    def __init__(
        self,
        repair_service: SubtitleRepairService,
        queue_service: SubtitleRepairQueueService,
    ) -> None:
        self._repair_service = repair_service
        self._queue_service = queue_service

    def scan_library_result(
        self,
        result: LibraryRootScanResult,
    ) -> SubtitleScanSummary:
        """Analizira prevode bez prekidanja glavnog skeniranja."""

        discovered_count = 0
        inspected_count = 0
        clean_count = 0
        needs_repair_count = 0
        queued_for_attention_count = 0
        unsupported_count = 0
        warnings: list[str] = []

        for entry in result.entries:
            if entry.scan_result is None:
                continue

            for scanned_file in entry.scan_result.detected_files:
                if scanned_file.role is not MediaFileRole.SUBTITLE:
                    continue

                discovered_count += 1

                if scanned_file.path.suffix.casefold() != ".srt":
                    unsupported_count += 1
                    continue

                try:
                    prepared = self._repair_service.prepare(
                        scanned_file.path
                    )
                    inspected_count += 1

                    if not prepared.inspection.needs_repair:
                        clean_count += 1
                        continue

                    needs_repair_count += 1
                    existing_item = self._queue_service.find_by_path(
                        str(prepared.file_path)
                    )
                    queue_item = self._queue_service.enqueue_if_needed(
                        prepared
                    )

                    if (
                        queue_item is not None
                        and queue_item.status
                        is SubtitleRepairQueueStatus.PENDING
                        and (
                            existing_item is None
                            or existing_item.source_sha256
                            != prepared.source_sha256
                        )
                    ):
                        queued_for_attention_count += 1
                except (OSError, ValueError, RuntimeError) as error:
                    warnings.append(
                        f"Prevod nije moguce analizirati "
                        f"'{scanned_file.path.name}': {error}"
                    )

        return SubtitleScanSummary(
            discovered_count=discovered_count,
            inspected_count=inspected_count,
            clean_count=clean_count,
            needs_repair_count=needs_repair_count,
            queued_for_attention_count=(
                queued_for_attention_count
            ),
            unsupported_count=unsupported_count,
            warnings=tuple(warnings),
        )