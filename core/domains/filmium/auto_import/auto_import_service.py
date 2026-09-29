# ========== AUTO-IMPORT SERVICE ==========
# Povezuje CORE file_monitor (mehanizam) sa FILMIUM pravilima. Detektuje nove
# video fajlove, opciono ih proverava (KALIMA), i vodi ih do potvrde uvoza.
from __future__ import annotations

import os
from collections.abc import Callable

from core.domains.filmium.auto_import.auto_import_models import (
    AutoImportRule,
    AutoImportRuleCreate,
    DetectedFile,
    DetectedFileStatus,
    SecurityStatus,
)
from core.domains.filmium.auto_import.auto_import_repository import (
    AutoImportRepository,
)
from core.domains.filmium.auto_import.file_classifier import file_matches_rule
from core.system.file_monitor import FileEvent, FileMonitorService

# Injektabilni tipovi: sigurnosni skener (KALIMA) i uvoznik (postojeći ImportService)
SecurityScanner = Callable[[str], SecurityStatus]
Importer = Callable[[DetectedFile], None]


# ========== SERVIS ==========
class AutoImportService:
    """Upravlja pravilima auto-uvoza i procesira detektovane fajlove."""

    def __init__(self, repository: AutoImportRepository,
                 file_monitor: FileMonitorService | None = None,
                 security_scanner: SecurityScanner | None = None,
                 importer: Importer | None = None) -> None:
        self._repo = repository
        self._monitor = file_monitor
        self._security = security_scanner
        self._importer = importer
        self._rules_by_folder: dict[str, AutoImportRule] = {}
        if self._monitor is not None:
            self._monitor.register_callback("created", self._on_created)

    # ---------- praćeni folderi ----------
    def add_monitored_folder(self, rule: AutoImportRuleCreate) -> AutoImportRule:
        created = self._repo.create_rule(rule)
        path = os.path.abspath(created.folder_path)
        self._rules_by_folder[path] = created
        self._repo.add_monitored_folder(path, created.id)
        if self._monitor is not None:
            self._monitor.start_monitoring(path, recursive=True)
        return created

    def remove_monitored_folder(self, folder_path: str) -> None:
        path = os.path.abspath(folder_path)
        self._rules_by_folder.pop(path, None)
        self._repo.remove_monitored_folder(path)
        if self._monitor is not None:
            self._monitor.stop_monitoring(path)

    def get_monitored_folders(self) -> list[dict]:
        return self._repo.list_monitored_folders()

    def resume_persisted(self) -> int:
        """Učita perzistirana pravila i pokrene praćenje (posle restarta app-a).

        Ne kreira nove redove u bazi — samo puni memorijsku mapu i pali monitor
        za već sačuvane foldere. Idempotentno (start_monitoring čuva duplikate).
        """
        count = 0
        for rule in self._repo.list_rules():
            path = os.path.abspath(rule.folder_path)
            self._rules_by_folder[path] = rule
            if self._monitor is not None:
                self._monitor.start_monitoring(path, recursive=True)
            count += 1
        return count

    # ---------- detekcija ----------
    def _on_created(self, event: FileEvent) -> None:
        if event.is_directory:
            return
        rule = self._rule_for_path(event.src_path)
        if rule is None:
            return
        self.queue_for_scan(event.src_path, rule)

    def _rule_for_path(self, file_path: str) -> AutoImportRule | None:
        path = os.path.abspath(file_path)
        best: AutoImportRule | None = None
        for folder, rule in self._rules_by_folder.items():
            if (path.startswith(folder + os.sep) or os.path.dirname(path) == folder) and (
                best is None or len(folder) > len(best.folder_path)
            ):
                best = rule
        return best

    def queue_for_scan(self, file_path: str, rule: AutoImportRule,
                       size_bytes: int | None = None) -> DetectedFile | None:
        # Filtriraj po tipu/veličini.
        if not file_matches_rule(file_path, rule, size_bytes=size_bytes):
            return None

        try:
            size = size_bytes if size_bytes is not None else os.path.getsize(file_path)
        except OSError:
            size = size_bytes or 0

        security = SecurityStatus.UNKNOWN
        # Opciona KALIMA provera pre uvoza.
        if rule.security_scan and self._security is not None:
            security = self._security(file_path)
            if security in (SecurityStatus.SUSPICIOUS, SecurityStatus.MALWARE):
                return self._repo.upsert_detected(DetectedFile(
                    file_path=os.path.abspath(file_path), file_size=size,
                    rule_id=rule.id, status=DetectedFileStatus.REJECTED,
                    security_status=security,
                ))

        detected = DetectedFile(
            file_path=os.path.abspath(file_path), file_size=size, rule_id=rule.id,
            status=DetectedFileStatus.READY, security_status=security,
        )
        stored = self._repo.upsert_detected(detected)

        # Automatski uvoz ako je pravilo tako podešeno i imamo uvoznik.
        if rule.auto_import and self._importer is not None:
            return self.confirm_import(stored.id)
        return stored

    # ---------- lista / potvrda ----------
    def get_detected_files(self, status: DetectedFileStatus | None = None) -> list[DetectedFile]:
        return self._repo.list_detected(status)

    def confirm_import(self, file_id: int) -> DetectedFile | None:
        detected = self._repo.get_detected(file_id)
        if detected is None:
            return None
        if self._importer is not None:
            self._importer(detected)
        return self._repo.update_detected_status(file_id, DetectedFileStatus.IMPORTED)

    def reject_import(self, file_id: int) -> DetectedFile | None:
        return self._repo.update_detected_status(file_id, DetectedFileStatus.REJECTED)
