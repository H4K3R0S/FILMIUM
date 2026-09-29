import logging
from dataclasses import replace
from datetime import date

from core.domains.filmium.activity_models import (
    ActivityEntityType,
    ActivityEventType,
)
from core.domains.filmium.activity_service import ActivityService
from core.domains.filmium.artwork_models import ArtworkType
from core.domains.filmium.artwork_repository import ArtworkRepository
from core.domains.filmium.asset_service import (
    MediaAssetService,
    MediaAssetType,
    MediaAssetValidationError,
)
from core.domains.filmium.genre_rules import normalize_genres
from core.domains.filmium.media_source_repository import (
    MediaSourceRepository,
)
from core.domains.filmium.models import MediaItem, MediaItemCreate
from core.domains.filmium.repository import MediaRepository

# ==========          FILMIUM LOGGER          ==========

logger = logging.getLogger("core")



# ==========          FILMIUM GREŠKE          ==========

class FilmiumValidationError(ValueError):
    """Greška koja označava neispravne FILMIUM podatke."""


class MediaItemNotFoundError(LookupError):
    """Greška koja označava da FILMIUM sadržaj ne postoji."""


# ==========          FILMIUM SERVICE          ==========

def _validate_create_item(
    item: MediaItemCreate,
    title: str,
    original_title: str | None,
    notes: str | None,
    genres: tuple,
) -> None:
    """Provere pre čuvanja; diže FilmiumValidationError na prvi prekršaj."""

    if len(genres) > 20:
        raise FilmiumValidationError(
            "Jedan sadržaj ne može imati više od 20 žanrova."
        )

    if not title:
        raise FilmiumValidationError(
            "Naslov FILMIUM sadržaja je obavezan."
        )

    if len(title) > 300:
        raise FilmiumValidationError(
            "Naslov ne može imati više od 300 karaktera."
        )

    if original_title and len(original_title) > 300:
        raise FilmiumValidationError(
            "Originalni naslov ne može imati više od 300 karaktera."
        )

    maximum_release_year = date.today().year + 10  # noqa: DTZ011

    if (
        item.release_year is not None
        and not 1888 <= item.release_year <= maximum_release_year
    ):
        raise FilmiumValidationError(
            "Godina izdanja nije u dozvoljenom opsegu."
        )

    if (
        item.runtime_minutes is not None
        and not 1 <= item.runtime_minutes <= 10_000
    ):
        raise FilmiumValidationError(
            "Trajanje sadržaja mora biti između 1 i 10000 minuta."
        )

    if item.rating is not None and not 1 <= item.rating <= 10:
        raise FilmiumValidationError(
            "Ocena mora biti između 1 i 10."
        )

    if notes and len(notes) > 10_000:
        raise FilmiumValidationError(
            "Beleška ne može imati više od 10000 karaktera."
        )


def _build_clean_item(
    item: MediaItemCreate,
    title: str,
    original_title: str | None,
    notes: str | None,
    genres: tuple,
) -> MediaItemCreate:
    """Nova, očišćena MediaItemCreate instanca (strip opcionih polja)."""

    return MediaItemCreate(
        title=title,
        original_title=original_title,
        media_type=item.media_type,
        release_year=item.release_year,
        runtime_minutes=item.runtime_minutes,
        watch_status=item.watch_status,
        rating=item.rating,
        notes=notes,
        genres=genres,
        is_favorite=item.is_favorite,
        english_title=(item.english_title or "").strip() or None,
        english_description=(item.english_description or "").strip() or None,
        content_category=item.content_category,
        cast_names=tuple(item.cast_names or ()),
        studio=(item.studio or "").strip() or None,
        director=(item.director or "").strip() or None,
        keywords=tuple(item.keywords or ()),
        collection=(item.collection or "").strip() or None,
        is_synchronized=item.is_synchronized,
        editor_settings=item.editor_settings or {},
        tmdb_id=item.tmdb_id,
    )


class FilmiumService:
    """Sprovodi poslovna pravila FILMIUM kataloga."""


# ==========          konstruktor          ==========
    def __init__(
        self,
        repository: MediaRepository,
        activity_service: ActivityService | None = None,
        asset_service: MediaAssetService | None = None,
        artwork_repository: ArtworkRepository | None = None,
        media_source_repository: MediaSourceRepository | None = None,
    ) -> None:
        """
        Inicijalizuje FILMIUM servis.

        Args:
            repository: Repository koji upravlja trajnim podacima.
            activity_service: Opcioni servis istorije aktivnosti.
            asset_service: Opcioni servis vizuelnih asseta.
        """

        self._repository = repository
        self._activity_service = activity_service
        self._asset_service = asset_service
        self._artwork_repository = artwork_repository
        self._media_source_repository = media_source_repository

    def create_media_item(self, item: MediaItemCreate) -> MediaItem:
        """
        Validira i dodaje novi sadržaj u FILMIUM katalog.

        Args:
            item: Podaci novog filma ili serije.

        Returns:
            Sačuvani FILMIUM sadržaj.

        Raises:
            FilmiumValidationError: Ako podaci nisu ispravni.
        """
        normalized_item = self._normalize_create_item(item)
        created_item = self._repository.create(normalized_item)

        if self._activity_service is not None:
            self._activity_service.record_event(
                event_type=ActivityEventType.MEDIA_CREATED,
                entity_type=ActivityEntityType.MEDIA,
                entity_id=created_item.id,
                title=created_item.title,
                metadata={
                    "media_type": created_item.media_type.value,
                    "release_year": created_item.release_year,
                },
            )
            

        return created_item
    
    




    def update_media_item(
        self,
        item_id: int,
        item: MediaItemCreate,
    ) -> MediaItem:
        """
        Validira i menja postojeći FILMIUM sadržaj.

        Raises:
            FilmiumValidationError: Ako novi podaci nisu ispravni.
            MediaItemNotFoundError: Ako sadržaj ne postoji.
        """
        normalized_item = self._normalize_create_item(item)

        # TMDB ID je „lepljiv": kada zahtev ne nosi tmdb_id (npr. obično
        # čuvanje iz editora), zadrži postojeći umesto da ga obrišeš na NULL.
        if normalized_item.tmdb_id is None:
            existing_item = self._repository.get_by_id(item_id)
            if existing_item is not None and existing_item.tmdb_id is not None:
                normalized_item = replace(
                    normalized_item,
                    tmdb_id=existing_item.tmdb_id,
                )

        updated_item = self._repository.update(
            item_id,
            normalized_item,
        )

        if updated_item is None:
            raise MediaItemNotFoundError(
                f"FILMIUM sadržaj sa ID-em {item_id} ne postoji."
            )
        
        if self._activity_service is not None:
            self._activity_service.record_event(
                event_type=ActivityEventType.MEDIA_UPDATED,
                entity_type=ActivityEntityType.MEDIA,
                entity_id=updated_item.id,
                title=updated_item.title,
                metadata={
                    "media_type": updated_item.media_type.value,
                },
            )


        return updated_item



    def set_favorite_status(
        self,
        item_id: int,
        is_favorite: bool,
    ) -> MediaItem:
        """
        Menja favorite status postojećeg FILMIUM sadržaja.

        Args:
            item_id: ID sadržaja koji se menja.
            is_favorite: Novi favorite status.

        Returns:
            Ažurirani FILMIUM sadržaj.

        Raises:
            MediaItemNotFoundError: Ako sadržaj ne postoji.
        """

        updated_item = self._repository.set_favorite_status(
            item_id,
            is_favorite,
        )

        if updated_item is None:
            raise MediaItemNotFoundError(
                f"FILMIUM sadržaj sa ID-em {item_id} ne postoji."
            )
        
        if self._activity_service is not None:
            event_type = (
                ActivityEventType.FAVORITE_ADDED
                if updated_item.is_favorite
                else ActivityEventType.FAVORITE_REMOVED
            )

            self._activity_service.record_event(
                event_type=event_type,
                entity_type=ActivityEntityType.MEDIA,
                entity_id=updated_item.id,
                title=updated_item.title,
                metadata={
                    "is_favorite": updated_item.is_favorite,
                },
            )

        return updated_item


    def update_keywords(
        self,
        item_id: int,
        keywords: tuple[str, ...],
        editor_settings: dict,
    ) -> MediaItem:
        """Menja SAMO ključne reči i editor_settings postojećeg sadržaja.

        Raises:
            MediaItemNotFoundError: Ako sadržaj ne postoji.
        """

        updated_item = self._repository.update_keywords(
            item_id,
            keywords,
            editor_settings,
        )

        if updated_item is None:
            raise MediaItemNotFoundError(
                f"FILMIUM sadržaj sa ID-em {item_id} ne postoji."
            )

        return updated_item


    def delete_media_item(self, item_id: int) -> None:
        """
        Briše postojeći FILMIUM sadržaj i beleži događaj.

        Raises:
            MediaItemNotFoundError: Ako sadržaj ne postoji.
        """

        existing_item = self._repository.get_by_id(item_id)

        if existing_item is None:
            raise MediaItemNotFoundError(
                f"FILMIUM sadržaj sa ID-em {item_id} ne postoji."
            )

        was_deleted = self._repository.delete(item_id)

        if not was_deleted:
            raise MediaItemNotFoundError(
                f"FILMIUM sadržaj sa ID-em {item_id} ne postoji."
            )
    
        # Datoteke čistimo tek nakon uspešnog brisanja DB zapisa.
        self._delete_media_assets(existing_item)

        if self._activity_service is not None:
            self._activity_service.record_event(
                event_type=ActivityEventType.MEDIA_DELETED,
                entity_type=ActivityEntityType.MEDIA,
                entity_id=existing_item.id,
                title=existing_item.title,
                metadata={
                    "media_type": existing_item.media_type.value,
                },
            )


    def _delete_media_assets(
        self,
        item: MediaItem,
    ) -> None:
        """
        Uklanja poster i backdrop obrisanog FILMIUM sadržaja.

        Greška filesystem čišćenja ne vraća obrisani DB zapis.
        Umesto toga se beleži upozorenje radi kasnije dijagnostike.
        """

        if self._asset_service is None:
            return

        for relative_path in (
            item.poster_path,
            item.backdrop_path,
        ):
            self._delete_asset_logged(relative_path)


    def _delete_asset_logged(self, relative_path) -> None:
        """Obriši managed asset; greška se loguje (ne prekida čišćenje)."""

        try:
            self._asset_service.delete_asset(relative_path)
        except (
            OSError,
            MediaAssetValidationError,
        ) as error:
            logger.warning(
                "Čišćenje FILMIUM asseta nije uspelo: %s",
                error,
            )

    def list_active_genres(self) -> tuple[str, ...]:
        """Vraća žanrove koji su dostupni za izbor u FILMIUM-u."""

        return self._repository.list_active_genres()


    def list_media_items(self) -> list[MediaItem]:
        """Vraća kompletan FILMIUM katalog."""

        return [
            self._with_source_visual_assets(item)
            for item in self._repository.list_all()
        ]

    def get_media_item(self, item_id: int) -> MediaItem:
        """
        Vraća jedan FILMIUM sadržaj po ID-u.

        Raises:
            MediaItemNotFoundError: Ako sadržaj ne postoji.
        """
        item = self._repository.get_by_id(item_id)

        if item is None:
            raise MediaItemNotFoundError(
                f"FILMIUM sadržaj sa ID-em {item_id} ne postoji."
            )

        return self._with_source_visual_assets(item)

    def _with_source_visual_assets(
        self,
        item: MediaItem,
    ) -> MediaItem:
        """
        Dopunjava katalog slikama koje žive u registrovanoj biblioteci.

        Managed upload/kopije ostaju prioritet. Ako ih nema, GUI dobija
        bezbednu ``source/<source_id>/...`` putanju ka primarnoj slici.
        """

        if (
            self._artwork_repository is None
            or self._media_source_repository is None
        ):
            return item

        poster_path = item.poster_path or self._cache_source_visual_path(
            item.id,
            ArtworkType.POSTER,
            MediaAssetType.POSTER,
        )
        backdrop_path = item.backdrop_path or self._cache_source_visual_path(
            item.id,
            ArtworkType.BACKDROP,
            MediaAssetType.BACKDROP,
        )

        if (
            poster_path == item.poster_path
            and backdrop_path == item.backdrop_path
        ):
            return item

        return MediaItem(
            id=item.id,
            title=item.title,
            media_type=item.media_type,
            original_title=item.original_title,
            release_year=item.release_year,
            runtime_minutes=item.runtime_minutes,
            watch_status=item.watch_status,
            rating=item.rating,
            notes=item.notes,
            created_at=item.created_at,
            updated_at=item.updated_at,
            genres=item.genres,
            is_favorite=item.is_favorite,
            poster_path=poster_path,
            backdrop_path=backdrop_path,
        )

    def _cache_source_visual_path(
        self,
        media_id: int,
        artwork_type: ArtworkType,
        asset_type: MediaAssetType,
    ) -> str | None:
        if self._asset_service is None:
            return self._source_visual_path(media_id, artwork_type)

        artworks = self._artwork_repository.list_for_media(
            media_id,
            artwork_type,
        )

        for artwork in artworks:
            if artwork.source_id is None:
                continue

            cached_path = self._asset_service.save_source_cache_asset(
                media_id,
                artwork.source_id,
                artwork.relative_path,
                asset_type,
            )

            if cached_path is None:
                continue

            current = self._repository.get_by_id(media_id)

            if current is None:
                return cached_path

            poster_path = current.poster_path
            backdrop_path = current.backdrop_path

            if asset_type is MediaAssetType.POSTER:
                poster_path = cached_path
            else:
                backdrop_path = cached_path

            self._repository.set_visual_assets(
                media_id,
                poster_path,
                backdrop_path,
            )

            return cached_path

        return None

    def _source_visual_path(
        self,
        media_id: int,
        artwork_type: ArtworkType,
    ) -> str | None:
        artworks = self._artwork_repository.list_for_media(
            media_id,
            artwork_type,
        )

        for artwork in artworks:
            if artwork.source_id is None:
                continue

            source = self._media_source_repository.get(
                artwork.source_id
            )

            if source is None:
                continue

            return (
                f"source/{artwork.source_id}/"
                f"{artwork.relative_path}"
            )

        return None

    def _normalize_create_item(
        self,
        item: MediaItemCreate,
    ) -> MediaItemCreate:
        """
        Normalizuje i proverava podatke pre čuvanja.

        Returns:
            Nova, očišćena instanca podataka za kreiranje.
        """
        title = item.title.strip()
        original_title = (item.original_title or "").strip() or None
        notes = (item.notes or "").strip() or None

        try:
            genres = normalize_genres(
                item.genres,
                self._repository.list_active_genres(),
            )
        except ValueError as error:
            raise FilmiumValidationError(str(error)) from error

        _validate_create_item(item, title, original_title, notes, genres)
        return _build_clean_item(item, title, original_title, notes, genres)
