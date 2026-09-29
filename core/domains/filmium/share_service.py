import sqlite3

from core.domains.filmium.share_models import (
    ShareProfile,
    ShareProfileCreate,
    ShareQueueItem,
    ShareQueueItemCreate,
    ShareTransferMode,
)
from core.domains.filmium.share_repository import ShareRepository

# ==========          GRESKE FUNKCIJE PODELI          ==========

class ShareValidationError(ValueError):
    """Oznacava neispravne podatke profila ili reda."""


class ShareProfileNotFoundError(LookupError):
    """Oznacava da trazeni profil ne postoji."""


class ShareQueueItemNotFoundError(LookupError):
    """Oznacava da trazena stavka reda ne postoji."""


class ShareMediaNotFoundError(LookupError):
    """Oznacava da trazeni FILMIUM sadrzaj ne postoji."""


class ShareConflictError(ValueError):
    """Oznacava duplirani profil ili film u istom redu."""


class ShareProfileDisabledError(ValueError):
    """Oznacava pokusaj dodavanja u neaktivan profil."""


# ==========          SHARE SERVICE          ==========

class ShareService:
    """Validira profile i upravlja redovima funkcije Podeli."""

    _INVALID_FOLDER_CHARACTERS = frozenset('<>:"/\\|?*')

    def __init__(self, repository: ShareRepository) -> None:
        self._repository = repository

    def create_profile(
        self,
        item: ShareProfileCreate,
    ) -> ShareProfile:
        """Pravi normalizovan profil za deljenje."""

        normalized = self._normalize_profile(item)

        try:
            return self._repository.create_profile(normalized)
        except sqlite3.IntegrityError as error:
            raise ShareConflictError(
                "Profil za deljenje sa tim nazivom vec postoji."
            ) from error

    def list_profiles(self) -> tuple[ShareProfile, ...]:
        """Vraca sve profile funkcije Podeli."""

        return self._repository.list_profiles()

    def get_profile(self, profile_id: int) -> ShareProfile:
        """Vraca profil ili prijavljuje da ne postoji."""

        profile = self._repository.get_profile(profile_id)

        if profile is None:
            raise ShareProfileNotFoundError(
                f"Profil za deljenje sa ID-em {profile_id} ne postoji."
            )

        return profile

    def update_profile(
        self,
        profile_id: int,
        item: ShareProfileCreate,
    ) -> ShareProfile:
        """Menja postojeci profil."""

        normalized = self._normalize_profile(item)

        try:
            updated = self._repository.update_profile(
                profile_id,
                normalized,
            )
        except sqlite3.IntegrityError as error:
            raise ShareConflictError(
                "Profil za deljenje sa tim nazivom vec postoji."
            ) from error

        if updated is None:
            raise ShareProfileNotFoundError(
                f"Profil za deljenje sa ID-em {profile_id} ne postoji."
            )

        return updated

    def delete_profile(self, profile_id: int) -> None:
        """Brise profil i njegov red."""

        if not self._repository.delete_profile(profile_id):
            raise ShareProfileNotFoundError(
                f"Profil za deljenje sa ID-em {profile_id} ne postoji."
            )

    def add_to_queue(
        self,
        item: ShareQueueItemCreate,
    ) -> ShareQueueItem:
        """Dodaje film u red aktivnog profila."""

        profile = self.get_profile(item.profile_id)

        if not profile.is_active:
            raise ShareProfileDisabledError(
                "Film nije moguce dodati u neaktivan profil."
            )

        if not self._repository.media_exists(item.media_id):
            raise ShareMediaNotFoundError(
                f"FILMIUM sadrzaj sa ID-em {item.media_id} ne postoji."
            )

        try:
            return self._repository.add_to_queue(
                item.profile_id,
                item.media_id,
                ShareTransferMode(item.transfer_mode),
            )
        except sqlite3.IntegrityError as error:
            raise ShareConflictError(
                "Film je vec dodat u red izabranog profila."
            ) from error

    def list_queue(
        self,
        profile_id: int,
    ) -> tuple[ShareQueueItem, ...]:
        """Vraca red nakon provere da profil postoji."""

        self.get_profile(profile_id)
        return self._repository.list_queue(profile_id)

    def change_transfer_mode(
        self,
        queue_item_id: int,
        transfer_mode: ShareTransferMode,
    ) -> ShareQueueItem:
        """Menja obim buduceg kopiranja jedne stavke."""

        updated = self._repository.set_transfer_mode(
            queue_item_id,
            ShareTransferMode(transfer_mode),
        )

        if updated is None:
            raise ShareQueueItemNotFoundError(
                f"Stavka za deljenje sa ID-em {queue_item_id} ne postoji."
            )

        return updated

    def remove_from_queue(self, queue_item_id: int) -> None:
        """Uklanja film iz reda bez izmene kataloga."""

        if not self._repository.remove_from_queue(queue_item_id):
            raise ShareQueueItemNotFoundError(
                f"Stavka za deljenje sa ID-em {queue_item_id} ne postoji."
            )

    @staticmethod
    def _optional_text(value: str | None) -> str | None:
        if value is None:
            return None

        return value.strip() or None

    @classmethod
    def _normalize_profile(
        cls,
        item: ShareProfileCreate,
    ) -> ShareProfileCreate:
        name = item.name.strip()
        destination_folder = item.default_destination_folder.strip()

        if not name:
            raise ShareValidationError(
                "Naziv profila ne sme biti prazan."
            )

        if len(name) > 100:
            raise ShareValidationError(
                "Naziv profila ne sme biti duzi od 100 znakova."
            )

        if (
            not destination_folder
            or destination_folder in {".", ".."}
            or any(
                character in cls._INVALID_FOLDER_CHARACTERS
                for character in destination_folder
            )
        ):
            raise ShareValidationError(
                "Odredisni folder mora biti bezbedan naziv jednog foldera."
            )

        if len(destination_folder) > 100:
            raise ShareValidationError(
                "Naziv odredisnog foldera ne sme biti duzi od 100 znakova."
            )

        return ShareProfileCreate(
            name=name,
            description=cls._optional_text(item.description),
            default_destination_folder=destination_folder,
            is_active=bool(item.is_active),
        )