"""Šeme za zdravlje zavisnosti ćelije (dependency indikator + install).

Samostalna ćelija izlaže svoje zavisnosti isto kao CORE: status svake i
sažeti nivo problema, plus snimak install posla za polling iz GUI-ja.
"""

from pydantic import BaseModel

from core.foundation.dependencies import DependencyStatus

# ==========          STATUS JEDNE ZAVISNOSTI          ==========

class DependencyStatusResponse(BaseModel):
    key: str
    label: str
    kind: str
    severity: str
    installed: bool
    purpose: str
    install_hint: str
    installer: str

    @classmethod
    def from_status(
        cls,
        status: DependencyStatus,
    ) -> "DependencyStatusResponse":
        dependency = status.dependency

        return cls(
            key=dependency.key,
            label=dependency.label,
            kind=dependency.kind.value,
            severity=dependency.severity.value,
            installed=status.installed,
            purpose=dependency.purpose,
            install_hint=dependency.install_hint,
            installer=dependency.installer.value,
        )


# ==========          ZDRAVSTVENI PREGLED ZAVISNOSTI          ==========

class SystemDependenciesResponse(BaseModel):
    status: str
    dependencies: list[DependencyStatusResponse]


# ==========          INSTALL POSAO          ==========

class InstallJobResponse(BaseModel):
    """Snimak install posla za polling iz GUI-ja."""

    key: str | None
    status: str
    started_at: str | None
    returncode: int | None
    log: list[str]

    @classmethod
    def from_job(cls, job) -> "InstallJobResponse":
        return cls(
            key=job.key,
            status=job.status,
            started_at=job.started_at,
            returncode=job.returncode,
            log=job.log,
        )
