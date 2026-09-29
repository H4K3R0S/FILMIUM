from core.domains.filmium.asset_service import (
    MediaAssetService,
    MediaAssetType,
)
from core.domains.filmium.models import MediaItem
from core.domains.filmium.repository import MediaRepository
from core.domains.filmium.service import MediaItemNotFoundError

# ==========          MEDIA VISUAL SERVICE          ==========

class MediaVisualService:
    """
    Upravlja vezom FILMIUM sadržaja i njegovih vizuelnih asseta.

    Servis orkestrira čuvanje datoteke i ažuriranje baze. API zato
    ne pristupa direktno filesystem-u niti repository sloju.
    """

    def __init__(
        self,
        repository: MediaRepository,
        asset_service: MediaAssetService,
    ) -> None:
        """
        Inicijalizuje servis vizuelnih asseta.

        Args:
            repository: Repository FILMIUM sadržaja.
            asset_service: Servis za bezbedno čuvanje slika.
        """

        self._repository = repository
        self._asset_service = asset_service

    def save_media_asset(
        self,
        item_id: int,
        asset_type: MediaAssetType,
        content: bytes,
    ) -> MediaItem:
        """
        Čuva sliku i povezuje je sa FILMIUM sadržajem.

        Args:
            item_id: ID sadržaja kome slika pripada.
            asset_type: Tip slike, poster ili backdrop.
            content: Binarni sadržaj slike.

        Returns:
            Ažurirani FILMIUM sadržaj.

        Raises:
            MediaItemNotFoundError: Ako sadržaj ne postoji.
        """

        current_item = self._repository.get_by_id(item_id)

        if current_item is None:
            raise MediaItemNotFoundError(
                f"FILMIUM sadržaj sa ID-em {item_id} ne postoji."
            )

        relative_path = self._asset_service.save_asset(
            item_id=item_id,
            asset_type=asset_type,
            content=content,
        )

        poster_path = current_item.poster_path
        backdrop_path = current_item.backdrop_path

        if asset_type is MediaAssetType.POSTER:
            poster_path = relative_path
        elif asset_type is MediaAssetType.BACKDROP:
            backdrop_path = relative_path

        updated_item = self._repository.set_visual_assets(
            item_id=item_id,
            poster_path=poster_path,
            backdrop_path=backdrop_path,
        )

        if updated_item is None:
            self._asset_service.delete_asset(relative_path)

            raise MediaItemNotFoundError(
                f"FILMIUM sadržaj sa ID-em {item_id} ne postoji."
            )

        return updated_item

    def delete_media_asset(
        self,
        item_id: int,
        asset_type: MediaAssetType,
    ) -> MediaItem:
        """
        Uklanja sliku i njenu vezu sa FILMIUM sadržajem.

        Args:
            item_id: ID sadržaja čija se slika uklanja.
            asset_type: Tip slike koji treba ukloniti.

        Returns:
            Ažurirani FILMIUM sadržaj.

        Raises:
            MediaItemNotFoundError: Ako sadržaj ne postoji.
        """

        current_item = self._repository.get_by_id(item_id)

        if current_item is None:
            raise MediaItemNotFoundError(
                f"FILMIUM sadržaj sa ID-em {item_id} ne postoji."
            )

        poster_path = current_item.poster_path
        backdrop_path = current_item.backdrop_path

        if asset_type is MediaAssetType.POSTER:
            removed_path = poster_path
            poster_path = None
        else:
            removed_path = backdrop_path
            backdrop_path = None

        updated_item = self._repository.set_visual_assets(
            item_id=item_id,
            poster_path=poster_path,
            backdrop_path=backdrop_path,
        )

        if updated_item is None:
            raise MediaItemNotFoundError(
                f"FILMIUM sadržaj sa ID-em {item_id} ne postoji."
            )

        self._asset_service.delete_asset(removed_path)

        return updated_item