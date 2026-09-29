"""
CORE runtime životni ciklus (Foundation).

Modeluje u kom je stanju backend runtime, od pokretanja do gašenja:

    STARTING → READY → (DEGRADED) → STOPPING → STOPPED
                     ↘ ERROR

- STARTING: runtime se podiže (import + provere pre nego što API prima zahteve).
- READY: sve kritične zavisnosti tu, sistem radi normalno.
- DEGRADED: radi, ali nešto važno nedostaje (npr. kritična zavisnost).
- STOPPING/STOPPED: uredno gašenje.
- ERROR: pokretanje nije uspelo.

Stanje izlaže `/api/v1/system/status`. Lifecycle je jedini promenljivi
foundation servis (ostalo su frozen snimci/konfiguracija).
"""

from datetime import datetime, timezone
from enum import StrEnum

from core.foundation.logging import core_logger

# ==========          STANJA          ==========

class RuntimeStatus(StrEnum):
    """Moguća stanja CORE runtime-a."""

    STARTING = "starting"
    READY = "ready"
    DEGRADED = "degraded"
    STOPPING = "stopping"
    STOPPED = "stopped"
    ERROR = "error"


# Stanja u kojima sistem prima i obrađuje zahteve.
_OPERATIONAL: frozenset[RuntimeStatus] = frozenset(
    {RuntimeStatus.READY, RuntimeStatus.DEGRADED}
)


# ==========          LIFECYCLE SERVIS          ==========

class RuntimeLifecycle:
    """
    Drži tekuće stanje runtime-a i beleži prelaze.

    Prelazi se ne blokiraju (radi jednostavnosti u 0.1), ali se svaki loguje sa
    vremenom i opcionim detaljem (npr. razlog DEGRADED/ERROR stanja).
    """

    def __init__(self) -> None:
        now = self._now()
        self._status = RuntimeStatus.STARTING
        self._detail: str | None = None
        self._started_at = now
        self._updated_at = now

    # ----------          POMOĆNO          ----------

    @staticmethod
    def _now() -> str:
        """Trenutni UTC trenutak kao ISO 8601 string."""

        return datetime.now(timezone.utc).isoformat()

    def _transition(
        self,
        status: RuntimeStatus,
        detail: str | None = None,
    ) -> None:
        """Postavlja novo stanje, osvežava vreme i loguje prelaz."""

        self._status = status
        self._detail = detail
        self._updated_at = self._now()

        if detail:
            core_logger.info("Runtime stanje: %s (%s)", status.value, detail)
        else:
            core_logger.info("Runtime stanje: %s", status.value)

    # ----------          ČITANJE          ----------

    @property
    def status(self) -> RuntimeStatus:
        """Tekuće stanje runtime-a."""

        return self._status

    @property
    def detail(self) -> str | None:
        """Opcioni opis (razlog) tekućeg stanja."""

        return self._detail

    @property
    def started_at(self) -> str:
        """Trenutak kad je lifecycle napravljen (podizanje runtime-a)."""

        return self._started_at

    @property
    def updated_at(self) -> str:
        """Trenutak poslednjeg prelaza stanja."""

        return self._updated_at

    @property
    def is_operational(self) -> bool:
        """True ako sistem prima zahteve (READY ili DEGRADED)."""

        return self._status in _OPERATIONAL

    # ----------          PRELAZI          ----------

    def mark_starting(self) -> None:
        """Runtime se podiže."""

        self._transition(RuntimeStatus.STARTING)

    def mark_ready(self) -> None:
        """Runtime je spreman i radi normalno."""

        self._transition(RuntimeStatus.READY)

    def mark_degraded(self, detail: str) -> None:
        """Runtime radi, ali sa poznatim ograničenjem."""

        self._transition(RuntimeStatus.DEGRADED, detail)

    def mark_stopping(self) -> None:
        """Runtime počinje uredno gašenje."""

        self._transition(RuntimeStatus.STOPPING)

    def mark_stopped(self) -> None:
        """Runtime je ugašen."""

        self._transition(RuntimeStatus.STOPPED)

    def mark_error(self, detail: str) -> None:
        """Pokretanje ili rad runtime-a nije uspeo."""

        self._transition(RuntimeStatus.ERROR, detail)


# ==========          ODLUKA PRI STARTU          ==========

def resolve_startup_status(
    dependency_level: str,
) -> tuple[RuntimeStatus, str | None]:
    """
    Bira READY ili DEGRADED na osnovu nivoa zavisnosti (`overall_status`).

    Args:
        dependency_level: "ok", "warning" ili "critical".

    Returns:
        Par (stanje, detalj). "critical" → DEGRADED sa razlogom, inače READY.
    """

    if dependency_level == "critical":
        return (
            RuntimeStatus.DEGRADED,
            "Nedostaju kritične zavisnosti.",
        )

    return (RuntimeStatus.READY, None)


# ==========          SINGLETON          ==========

runtime_lifecycle = RuntimeLifecycle()
