from typing import Any

from core.domains.filmium.activity_models import (
    ActivityCreate,
    ActivityEntityType,
    ActivityEventType,
    ActivityItem,
)
from core.domains.filmium.activity_repository import ActivityRepository

# ==========          FILMIUM ACTIVITY GREŠKE          ==========

class ActivityValidationError(ValueError):
    """Greška koja označava neispravan activity zahtev."""


# ==========          FILMIUM ACTIVITY SERVICE          ==========

class ActivityService:
    """Sprovodi pravila FILMIUM istorije aktivnosti."""

    def __init__(self, repository: ActivityRepository) -> None:
        """
        Inicijalizuje activity servis.

        Args:
            repository: Repository koji trajno čuva događaje.
        """

        self._repository = repository

    def record_event(
        self,
        event_type: ActivityEventType,
        entity_type: ActivityEntityType,
        entity_id: int,
        title: str,
        metadata: dict[str, Any] | None = None,
    ) -> ActivityItem:
        """
        Validira i trajno beleži FILMIUM događaj.

        Args:
            event_type: Vrsta događaja koji se dogodio.
            entity_type: Vrsta objekta na koji se događaj odnosi.
            entity_id: ID objekta.
            title: Naziv objekta u trenutku događaja.
            metadata: Opcioni dodatni podaci događaja.

        Returns:
            Trajno sačuvani activity zapis.

        Raises:
            ActivityValidationError: Ako podaci nisu ispravni.
        """

        normalized_title = title.strip()

        if entity_id <= 0:
            raise ActivityValidationError(
                "Activity entity ID mora biti pozitivan broj."
            )

        if not normalized_title:
            raise ActivityValidationError(
                "Activity naslov je obavezan."
            )

        if len(normalized_title) > 300:
            raise ActivityValidationError(
                "Activity naslov ne može imati više od 300 karaktera."
            )

        return self._repository.create(
            ActivityCreate(
                event_type=event_type,
                entity_type=entity_type,
                entity_id=entity_id,
                title=normalized_title,
                metadata=dict(metadata or {}),
            )
        )

    def list_recent_events(
        self,
        limit: int = 100,
    ) -> list[ActivityItem]:
        """
        Vraća najnovije FILMIUM događaje.

        Args:
            limit: Najveći broj događaja koji treba vratiti.

        Returns:
            Događaji poređani od najnovijeg ka najstarijem.

        Raises:
            ActivityValidationError: Ako limit nije dozvoljen.
        """

        if not 1 <= limit <= 500:
            raise ActivityValidationError(
                "Activity limit mora biti između 1 i 500."
            )

        return self._repository.list_recent(limit)