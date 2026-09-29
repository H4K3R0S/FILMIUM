from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any

# ==========          TIPOVI ACTIVITY DOGAĐAJA          ==========

class ActivityEventType(StrEnum):
    """Definiše događaje koje FILMIUM istorija može da zabeleži."""

    MEDIA_CREATED = "media_created"
    MEDIA_UPDATED = "media_updated"
    MEDIA_DELETED = "media_deleted"
    FAVORITE_ADDED = "favorite_added"
    FAVORITE_REMOVED = "favorite_removed"
    COLLECTION_CREATED = "collection_created"
    COLLECTION_DELETED = "collection_deleted"
    COLLECTION_MEDIA_ADDED = "collection_media_added"
    COLLECTION_MEDIA_REMOVED = "collection_media_removed"


class ActivityEntityType(StrEnum):
    """Definiše tip objekta na koji se activity događaj odnosi."""

    MEDIA = "media"
    COLLECTION = "collection"


# ==========          ACTIVITY MODEL ZA KREIRANJE          ==========

@dataclass(frozen=True)
class ActivityCreate:
    """Predstavlja novi događaj pre čuvanja u bazi."""

    event_type: ActivityEventType
    entity_type: ActivityEntityType
    entity_id: int
    title: str
    metadata: dict[str, Any] = field(default_factory=dict)


# ==========          SAČUVANI ACTIVITY MODEL          ==========

@dataclass(frozen=True)
class ActivityItem:
    """Predstavlja jedan trajno sačuvani FILMIUM događaj."""

    id: int
    event_type: ActivityEventType
    entity_type: ActivityEntityType
    entity_id: int
    title: str
    metadata: dict[str, Any]
    created_at: datetime