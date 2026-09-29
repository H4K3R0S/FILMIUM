from datetime import datetime
from typing import Any

from pydantic import BaseModel

from core.domains.filmium.activity_models import (
    ActivityEntityType,
    ActivityEventType,
    ActivityItem,
)

# ==========          FILMIUM ACTIVITY API ODGOVOR          ==========

class ActivityItemResponse(BaseModel):
    """Predstavlja FILMIUM activity događaj koji API vraća."""

    id: int
    event_type: ActivityEventType
    entity_type: ActivityEntityType
    entity_id: int
    title: str
    metadata: dict[str, Any]
    created_at: datetime

    @classmethod
    def from_domain(
        cls,
        activity: ActivityItem,
    ) -> "ActivityItemResponse":
        """Pretvara domenski activity model u API odgovor."""

        return cls(
            id=activity.id,
            event_type=activity.event_type,
            entity_type=activity.entity_type,
            entity_id=activity.entity_id,
            title=activity.title,
            metadata=activity.metadata,
            created_at=activity.created_at,
        )