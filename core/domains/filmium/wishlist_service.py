from collections.abc import Iterable

from core.domains.filmium.wishlist_models import (
    CatalogMatchTarget,
    WishlistEntry,
    WishlistEntryCreate,
)
from core.domains.filmium.wishlist_repository import (
    WishlistRepository,
)


def _normalize_title(value: str) -> str:
    """Svodi naslov na slova/brojeve (bez razmaka, interpunkcije, veličine)."""

    return "".join(
        character for character in value.casefold() if character.isalnum()
    )


# ==========          WISHLIST GREŠKE          ==========

class WishlistValidationError(ValueError):
    """Greška koja označava neispravne podatke liste za preuzimanje."""


class WishlistNotFoundError(LookupError):
    """Greška koja označava da stavka liste za preuzimanje ne postoji."""


_MEDIA_TYPES = frozenset({"movie", "series"})
_CATEGORIES = frozenset({"regular", "domestic", "animated"})


# ==========          WISHLIST SERVICE          ==========

class WishlistService:
    """Sprovodi poslovna pravila FILMIUM liste za preuzimanje."""

    def __init__(self, repository: WishlistRepository) -> None:
        """Inicijalizuje servis liste za preuzimanje."""

        self._repository = repository

    def create_entry(
        self,
        entry: WishlistEntryCreate,
    ) -> WishlistEntry:
        """Validira i kreira novu stavku liste za preuzimanje."""

        return self._repository.create(self._normalize(entry))

    def list_entries(self) -> list[WishlistEntry]:
        """Vraća sve stavke liste za preuzimanje."""

        return self._repository.list_all()

    def get_entry(self, entry_id: int) -> WishlistEntry:
        """Vraća jednu stavku liste za preuzimanje."""

        entry = self._repository.get_by_id(entry_id)

        if entry is None:
            raise WishlistNotFoundError(
                f"Stavka liste za preuzimanje sa ID-em {entry_id} ne postoji."
            )

        return entry

    def delete_entry(self, entry_id: int) -> None:
        """Briše stavku liste za preuzimanje."""

        if not self._repository.delete(entry_id):
            raise WishlistNotFoundError(
                f"Stavka liste za preuzimanje sa ID-em {entry_id} ne postoji."
            )

    def set_asset_path(
        self,
        entry_id: int,
        column: str,
        relative_path: str,
    ) -> WishlistEntry:
        """Beleži putanju jednog asseta (poster/backdrop/prevod...)."""

        entry = self._repository.set_asset_path(
            entry_id,
            column,
            relative_path,
        )

        if entry is None:
            raise WishlistNotFoundError(
                f"Stavka liste za preuzimanje sa ID-em {entry_id} ne postoji."
            )

        return entry

    def append_extra_asset(
        self,
        entry_id: int,
        relative_path: str,
    ) -> WishlistEntry:
        """Dodaje putanju dodatnog sadržaja u listu."""

        entry = self._repository.append_extra_asset(entry_id, relative_path)

        if entry is None:
            raise WishlistNotFoundError(
                f"Stavka liste za preuzimanje sa ID-em {entry_id} ne postoji."
            )

        return entry

    # ==========          POKLAPANJE SA BIBLIOTEKOM          ==========

    def reconcile_against_catalog(
        self,
        catalog: Iterable[CatalogMatchTarget],
    ) -> list[WishlistEntry]:
        """
        Uklanja iz liste za preuzeti naslove koji su ušli u biblioteku.

        Poklapanje je namerno konzervativno:
        - ako stavka ima TMDB ID → poklapa se samo po istom TMDB ID-u
          (nezavisno od jezika naslova, bez lažnih pogodaka);
        - ako nema TMDB ID → po normalizovanom naslovu i istoj godini.

        Returns:
            Lista uklonjenih stavki (za obaveštenje korisniku).
        """

        targets = list(catalog)

        catalog_tmdb_ids = {
            target.tmdb_id
            for target in targets
            if target.tmdb_id is not None
        }

        catalog_title_years: set[tuple[str, int]] = set()
        for target in targets:
            if target.release_year is None:
                continue
            for title in target.titles:
                if title:
                    catalog_title_years.add(
                        (_normalize_title(title), target.release_year)
                    )

        removed: list[WishlistEntry] = []

        for entry in self._repository.list_all():
            if self._is_in_catalog(
                entry,
                catalog_tmdb_ids,
                catalog_title_years,
            ) and self._repository.delete(entry.id):
                removed.append(entry)

        return removed

    @staticmethod
    def _is_in_catalog(
        entry: WishlistEntry,
        catalog_tmdb_ids: set[int],
        catalog_title_years: set[tuple[str, int]],
    ) -> bool:
        """Da li je stavka liste za preuzeti već u biblioteci."""

        if entry.tmdb_id is not None:
            return entry.tmdb_id in catalog_tmdb_ids

        if entry.release_year is None:
            return False

        key = (_normalize_title(entry.title), entry.release_year)
        return key in catalog_title_years

    # ==========          VALIDACIJA          ==========

    @staticmethod
    def _normalize(
        entry: WishlistEntryCreate,
    ) -> WishlistEntryCreate:
        """Normalizuje i proverava podatke stavke."""

        title = entry.title.strip()

        if not title:
            raise WishlistValidationError(
                "Naslov za listu za preuzimanje je obavezan."
            )

        if len(title) > 300:
            raise WishlistValidationError(
                "Naslov ne može imati više od 300 karaktera."
            )

        if entry.media_type not in _MEDIA_TYPES:
            raise WishlistValidationError(
                "Tip mora biti 'movie' ili 'series'."
            )

        if entry.content_category not in _CATEGORIES:
            raise WishlistValidationError(
                "Kategorija mora biti 'regular', 'domestic' ili 'animated'."
            )

        year = entry.release_year
        if year is not None and not (1888 <= year <= 9999):
            raise WishlistValidationError(
                "Godina mora biti između 1888 i 9999."
            )

        return WishlistEntryCreate(
            title=title,
            release_year=year,
            media_type=entry.media_type,
            content_category=entry.content_category,
            is_subtitled=entry.is_subtitled,
            is_synchronized=entry.is_synchronized,
            tmdb_id=entry.tmdb_id,
            english_overview=(entry.english_overview or "").strip() or None,
            local_overview=(entry.local_overview or "").strip() or None,
        )
