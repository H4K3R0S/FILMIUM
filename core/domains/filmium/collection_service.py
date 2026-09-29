import sqlite3

from core.domains.filmium.activity_models import (
    ActivityEntityType,
    ActivityEventType,
)
from core.domains.filmium.activity_service import ActivityService
from core.domains.filmium.collection_repository import (
    CollectionRepository,
)
from core.domains.filmium.models import (
    CollectionCreate,
    MediaCollection,
)
from core.domains.filmium.repository import MediaRepository
from core.domains.filmium.service import MediaItemNotFoundError

# ==========          COLLECTION GREŠKE          ==========

class CollectionValidationError(ValueError):
    """Greška koja označava neispravne podatke kolekcije."""


class CollectionNotFoundError(LookupError):
    """Greška koja označava da FILMIUM kolekcija ne postoji."""


# ==========          COLLECTION SERVICE          ==========

class CollectionService:
    """Sprovodi poslovna pravila FILMIUM kolekcija."""


# ==========          konstruktor          ==========
    def __init__(
        self,
        repository: CollectionRepository,
        media_repository: MediaRepository,
        activity_service: ActivityService | None = None,
    ) -> None:
        """
        Inicijalizuje servis kolekcija.

        Args:
            repository: Repository FILMIUM kolekcija.
            media_repository: Repository FILMIUM sadržaja.
            activity_service: Opcioni servis istorije aktivnosti.
        """

        self._repository = repository
        self._media_repository = media_repository
        self._activity_service = activity_service

    def create_collection(
        self,
        collection: CollectionCreate,
    ) -> MediaCollection:
        """Validira, kreira i beleži novu FILMIUM kolekciju."""

        normalized_collection = self._normalize_collection(collection)

        try:
            created_collection = self._repository.create(
                normalized_collection
            )
        except sqlite3.IntegrityError as error:
            raise CollectionValidationError(
                "FILMIUM kolekcija sa tim nazivom već postoji."
            ) from error

        if self._activity_service is not None:
            self._activity_service.record_event(
                event_type=ActivityEventType.COLLECTION_CREATED,
                entity_type=ActivityEntityType.COLLECTION,
                entity_id=created_collection.id,
                title=created_collection.name,
                metadata={
                    "description": created_collection.description,
                },
            )

        return created_collection

    def list_collections(self) -> list[MediaCollection]:
        """Vraća sve FILMIUM kolekcije."""

        return self._repository.list_all()

    def get_collection(
        self,
        collection_id: int,
    ) -> MediaCollection:
        """Vraća jednu FILMIUM kolekciju."""

        collection = self._repository.get_by_id(collection_id)

        if collection is None:
            raise CollectionNotFoundError(
                f"FILMIUM kolekcija sa ID-em {collection_id} ne postoji."
            )

        return collection

    def delete_collection(self, collection_id: int) -> None:
        """Briše FILMIUM kolekciju i beleži događaj."""

        existing_collection = self.get_collection(collection_id)

        was_deleted = self._repository.delete(collection_id)

        if not was_deleted:
            raise CollectionNotFoundError(
                f"FILMIUM kolekcija sa ID-em {collection_id} ne postoji."
            )

        if self._activity_service is not None:
            self._activity_service.record_event(
                event_type=ActivityEventType.COLLECTION_DELETED,
                entity_type=ActivityEntityType.COLLECTION,
                entity_id=existing_collection.id,
                title=existing_collection.name,
                metadata={
                    "item_count": len(existing_collection.item_ids),
                },
            )

    def add_media_item(
        self,
        collection_id: int,
        item_id: int,
    ) -> MediaCollection:
        """Dodaje sadržaj u kolekciju i beleži stvarnu promenu."""

        collection = self.get_collection(collection_id)
        media_item = self._media_repository.get_by_id(item_id)

        if media_item is None:
            raise MediaItemNotFoundError(
                f"FILMIUM sadržaj sa ID-em {item_id} ne postoji."
            )

        was_added = self._repository.add_item(
            collection_id,
            item_id,
        )

        if was_added and self._activity_service is not None:
            self._activity_service.record_event(
                event_type=(
                    ActivityEventType.COLLECTION_MEDIA_ADDED
                ),
                entity_type=ActivityEntityType.COLLECTION,
                entity_id=collection.id,
                title=collection.name,
                metadata={
                    "media_id": media_item.id,
                    "media_title": media_item.title,
                },
            )

        return self.get_collection(collection_id)

    def remove_media_item(
        self,
        collection_id: int,
        item_id: int,
    ) -> MediaCollection:
        """Uklanja sadržaj iz kolekcije i beleži stvarnu promenu."""

        collection = self.get_collection(collection_id)
        media_item = self._media_repository.get_by_id(item_id)

        was_removed = self._repository.remove_item(
            collection_id,
            item_id,
        )

        if (
            was_removed
            and media_item is not None
            and self._activity_service is not None
        ):
            self._activity_service.record_event(
                event_type=(
                    ActivityEventType.COLLECTION_MEDIA_REMOVED
                ),
                entity_type=ActivityEntityType.COLLECTION,
                entity_id=collection.id,
                title=collection.name,
                metadata={
                    "media_id": media_item.id,
                    "media_title": media_item.title,
                },
            )

        return self.get_collection(collection_id)
    # ==========          VALIDACIJA          ==========

    @staticmethod
    def _normalize_collection(
        collection: CollectionCreate,
    ) -> CollectionCreate:
        """Normalizuje i proverava podatke FILMIUM kolekcije."""

        name = collection.name.strip()
        description = (
            (collection.description or "").strip() or None
        )

        if not name:
            raise CollectionValidationError(
                "Naziv FILMIUM kolekcije je obavezan."
            )

        if len(name) > 100:
            raise CollectionValidationError(
                "Naziv kolekcije ne može imati više od 100 karaktera."
            )

        if description and len(description) > 2_000:
            raise CollectionValidationError(
                "Opis kolekcije ne može imati više od 2000 karaktera."
            )

        return CollectionCreate(
            name=name,
            description=description,
        )