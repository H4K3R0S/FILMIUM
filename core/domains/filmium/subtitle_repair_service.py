import hashlib
import os
import shutil
import tempfile
from datetime import datetime
from itertools import zip_longest
from pathlib import Path

from core.domains.filmium.subtitle_inspector_models import (
    SubtitleIssueType,
)
from core.domains.filmium.subtitle_inspector_service import (
    SubtitleInspectorService,
)
from core.domains.filmium.subtitle_repair_models import (
    PreparedSubtitleRepair,
    SubtitleRepairApplyRequest,
    SubtitleRepairApplyResult,
)

# ==========          GRESKE POPRAVKE          ==========

class SubtitleRepairValidationError(ValueError):
    """Oznacava neispravan zahtev ili putanju prevoda."""


class SubtitleRepairConfirmationError(PermissionError):
    """Oznacava pokusaj upisa bez eksplicitne potvrde korisnika."""


class SubtitleRepairConflictError(RuntimeError):
    """Oznacava da je datoteka promenjena posle pregleda."""


class SubtitleRepairNotSafeError(RuntimeError):
    """Oznacava problem koji se ne sme automatski pogadjati."""


# ==========          SUBTITLE REPAIR SERVICE          ==========

class SubtitleRepairService:
    """Pravi backup i atomski upisuje samo potvrdjenu popravku."""

    def __init__(
        self,
        inspector: SubtitleInspectorService | None = None,
    ) -> None:
        self._inspector = inspector or SubtitleInspectorService()

    def prepare(
        self,
        file_path: Path,
    ) -> PreparedSubtitleRepair:
        """Analizira trenutnu verziju datoteke i vezuje je za hash."""

        normalized_path = self._validate_path(file_path)
        content = normalized_path.read_bytes()
        inspection = self._inspector.inspect(
            content,
            normalized_path.name,
        )
        preview = self._inspector.create_repair_preview(inspection)

        return PreparedSubtitleRepair(
            file_path=normalized_path,
            source_sha256=self._sha256(content),
            inspection=inspection,
            preview=preview,
        )

    def apply(
        self,
        request: SubtitleRepairApplyRequest,
    ) -> SubtitleRepairApplyResult:
        """Posle potvrde pravi backup i menja original atomskim upisom."""

        if not request.confirmed:
            raise SubtitleRepairConfirmationError(
                "Popravka prevoda mora biti eksplicitno potvrdjena."
            )

        prepared = request.prepared
        file_path = self._validate_path(prepared.file_path)
        current_content = file_path.read_bytes()
        current_sha256 = self._sha256(current_content)

        if current_sha256 != prepared.source_sha256:
            raise SubtitleRepairConflictError(
                "Datoteka je promenjena nakon pregleda. "
                "Ponovite analizu pre popravke."
            )

        self._ensure_repair_is_safe(prepared)
        repaired_content = prepared.preview.repaired_text.encode("utf-8")

        if repaired_content == current_content:
            raise SubtitleRepairValidationError(
                "Pregled ne sadrzi promenu koju treba upisati."
            )

        backup_path = self._create_backup_path(file_path)
        shutil.copy2(file_path, backup_path)

        try:
            self._atomic_write(file_path, repaired_content)
        except Exception:
            if backup_path.exists():
                shutil.copy2(backup_path, file_path)
            raise

        return SubtitleRepairApplyResult(
            file_path=file_path,
            backup_path=backup_path,
            source_sha256=current_sha256,
            repaired_sha256=self._sha256(repaired_content),
            output_encoding="utf-8",
            changed_lines=len(prepared.preview.changes),
        )

    def save_edited(
        self,
        file_path: Path,
        source_sha256: str,
        content: str,
        confirmed: bool,
    ) -> SubtitleRepairApplyResult:
        """
        „Editor" mod: upisuje ručno izmenjen sadržaj u isti fajl.

        Ista bezbednosna pravila kao popravka — obavezna potvrda, provera da
        fajl nije promenjen posle učitavanja (sha), .bak backup i atomski upis.
        """

        if not confirmed:
            raise SubtitleRepairConfirmationError(
                "Snimanje izmene prevoda mora biti eksplicitno potvrdjeno."
            )

        path = self._validate_path(file_path)
        current_content = path.read_bytes()
        current_sha256 = self._sha256(current_content)

        if current_sha256 != source_sha256:
            raise SubtitleRepairConflictError(
                "Datoteka je promenjena nakon učitavanja. "
                "Ponovo otvorite prevod pre snimanja."
            )

        new_content = content.encode("utf-8")
        if new_content == current_content:
            raise SubtitleRepairValidationError(
                "Nema izmene koju treba sačuvati."
            )

        old_lines = current_content.decode(
            "utf-8", errors="replace"
        ).splitlines()
        new_lines = content.splitlines()
        changed_lines = sum(
            1
            for old, new in zip_longest(old_lines, new_lines)
            if old != new
        )

        backup_path = self._create_backup_path(path)
        shutil.copy2(path, backup_path)

        try:
            self._atomic_write(path, new_content)
        except Exception:
            if backup_path.exists():
                shutil.copy2(backup_path, path)
            raise

        return SubtitleRepairApplyResult(
            file_path=path,
            backup_path=backup_path,
            source_sha256=current_sha256,
            repaired_sha256=self._sha256(new_content),
            output_encoding="utf-8",
            changed_lines=changed_lines,
        )

    def transliterate(self, file_path: Path) -> dict:
        """Napravi drugo pismo (latinica↔ćirilica) prevoda u novi fajl."""
        from core.domains.filmium.subtitle_transliterate import (
            transliterate_subtitle_file,
        )

        normalized = self._validate_path(file_path)
        return transliterate_subtitle_file(normalized)

    @staticmethod
    def _validate_path(file_path: Path) -> Path:
        path = Path(file_path)

        if path.is_symlink():
            raise SubtitleRepairValidationError(
                "Simbolicke veze nisu dozvoljene za popravku prevoda."
            )

        if not path.exists() or not path.is_file():
            raise SubtitleRepairValidationError(
                "Datoteka prevoda ne postoji."
            )

        if path.suffix.lower() != ".srt":
            raise SubtitleRepairValidationError(
                "Popravka trenutno podrzava samo SRT datoteke."
            )

        return path.resolve()

    @staticmethod
    def _ensure_repair_is_safe(
        prepared: PreparedSubtitleRepair,
    ) -> None:
        unsafe_types = {
            SubtitleIssueType.REPLACEMENT_CHARACTER,
            SubtitleIssueType.SUSPICIOUS_CHARACTER,
        }

        if any(
            issue.issue_type in unsafe_types
            for issue in prepared.inspection.issues
        ):
            raise SubtitleRepairNotSafeError(
                "Prevod sadrzi nepovratno izgubljene ili sumnjive "
                "znakove. Potrebna je rucna provera."
            )

    @staticmethod
    def _create_backup_path(file_path: Path) -> Path:
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")  # noqa: DTZ005

        return file_path.with_name(
            f"{file_path.name}.filmium-backup-{timestamp}.bak"
        )

    @staticmethod
    def _atomic_write(
        file_path: Path,
        content: bytes,
    ) -> None:
        temporary_path: Path | None = None

        try:
            with tempfile.NamedTemporaryFile(
                mode="wb",
                dir=file_path.parent,
                prefix=f".{file_path.stem}-",
                suffix=".filmium-tmp",
                delete=False,
            ) as temporary_file:
                temporary_file.write(content)
                temporary_file.flush()
                os.fsync(temporary_file.fileno())
                temporary_path = Path(temporary_file.name)

            os.replace(temporary_path, file_path)
        finally:
            if (
                temporary_path is not None
                and temporary_path.exists()
            ):
                temporary_path.unlink()

    @staticmethod
    def _sha256(content: bytes) -> str:
        return hashlib.sha256(content).hexdigest()
