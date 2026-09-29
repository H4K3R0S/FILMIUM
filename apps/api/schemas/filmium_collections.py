from datetime import datetime

from pydantic import BaseModel, Field

from core.domains.filmium.models import (
    CollectionCreate,
    MediaCollection,
)

# ==========          COLLECTION API ZAHTEV          ==========

class CollectionCreateRequest(BaseModel):
    """Validira zahtev za kreiranje FILMIUM kolekcije."""

    name: str = Field(
        min_length=1,
        max_length=100,
    )
    description: str | None = Field(
        default=None,
        max_length=2_000,
    )

    def to_domain(self) -> CollectionCreate:
        """Pretvara API zahtev u FILMIUM domenski model."""

        return CollectionCreate(
            name=self.name,
            description=self.description,
        )


# ==========          COLLECTION API ODGOVOR          ==========

class CollectionResponse(BaseModel):
    """Predstavlja FILMIUM kolekciju koju API vraća GUI-ju."""

    id: int
    name: str
    description: str | None
    item_ids: tuple[int, ...]
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_domain(
        cls,
        collection: MediaCollection,
    ) -> "CollectionResponse":
        """Pretvara domensku kolekciju u API odgovor."""

        return cls(
            id=collection.id,
            name=collection.name,
            description=collection.description,
            item_ids=collection.item_ids,
            created_at=collection.created_at,
            updated_at=collection.updated_at,
        )