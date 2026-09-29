from core.domains.filmium.artwork_models import (
    ArtworkStorageKind,
    ArtworkType,
    MediaArtwork,
    MediaArtworkCreate,
)
from core.domains.filmium.artwork_repository import ArtworkRepository
from core.domains.filmium.library_models import (
    ArtworkManifest,
    FilmiumInfoManifest,
    MediaFileRole,
)
from core.domains.filmium.media_source_models import (
    MediaFile,
    MediaSource,
)

# ==========          GRESKE SINHRONIZACIJE          ==========

class ArtworkSyncError(ValueError):
    """Oznacava neslaganje manifesta i indeksiranog izvora."""


# ==========          ARTWORK SYNC SERVICE          ==========

class ArtworkSyncService:
    """Pretvara slike jednog izvora u FILMIUM artwork registry."""

    def __init__(self, repository: ArtworkRepository) -> None:
        self._repository = repository

    def sync_source_manifest(
        self,
        source: MediaSource,
        manifest: FilmiumInfoManifest,
    ) -> tuple[MediaArtwork, ...]:
        """Osvezava source slike bez menjanja managed kolekcije."""

        files_by_path = {
            item.relative_path.casefold(): item
            for item in source.files
        }
        items: list[MediaArtworkCreate] = []

        self._append_single(
            items,
            source,
            files_by_path,
            manifest.files.poster,
            MediaFileRole.POSTER,
            ArtworkType.POSTER,
        )
        self._append_single(
            items,
            source,
            files_by_path,
            manifest.files.backdrop,
            MediaFileRole.BACKDROP,
            ArtworkType.BACKDROP,
        )
        items.extend(
            self._collection_items(
                source,
                files_by_path,
                manifest.files.wallpapers,
                MediaFileRole.WALLPAPER,
                ArtworkType.WALLPAPER,
            )
        )
        items.extend(
            self._collection_items(
                source,
                files_by_path,
                manifest.files.fanart,
                MediaFileRole.FANART,
                ArtworkType.FANART,
            )
        )

        return self._repository.replace_for_source(
            source.media_id,
            source.id,
            tuple(items),
        )

    def _append_single(
        self,
        items: list[MediaArtworkCreate],
        source: MediaSource,
        files_by_path: dict[str, MediaFile],
        relative_path: str | None,
        expected_role: MediaFileRole,
        artwork_type: ArtworkType,
    ) -> None:
        if relative_path is None:
            return

        file = self._require_file(
            files_by_path,
            relative_path,
            expected_role,
        )
        items.append(
            self._create_item(
                source,
                file,
                artwork_type,
                label=None,
                is_primary=True,
                sort_order=0,
            )
        )

    def _collection_items(
        self,
        source: MediaSource,
        files_by_path: dict[str, MediaFile],
        artworks: tuple[ArtworkManifest, ...],
        expected_role: MediaFileRole,
        artwork_type: ArtworkType,
    ) -> tuple[MediaArtworkCreate, ...]:
        if not artworks:
            return ()

        selected_primary = next(
            (
                index
                for index, artwork in enumerate(artworks)
                if artwork.is_primary
            ),
            0,
        )
        items: list[MediaArtworkCreate] = []

        for index, artwork in enumerate(artworks):
            file = self._require_file(
                files_by_path,
                artwork.path,
                expected_role,
            )
            items.append(
                self._create_item(
                    source,
                    file,
                    artwork_type,
                    label=artwork.label,
                    is_primary=index == selected_primary,
                    sort_order=index,
                )
            )

        return tuple(items)

    @staticmethod
    def _require_file(
        files_by_path: dict[str, MediaFile],
        relative_path: str,
        expected_role: MediaFileRole,
    ) -> MediaFile:
        file = files_by_path.get(relative_path.casefold())

        if file is None:
            raise ArtworkSyncError(
                "Manifest slika nije pronadjena u indeksu izvora: "
                f"{relative_path}"
            )

        if file.role is not expected_role:
            raise ArtworkSyncError(
                f"Datoteka '{relative_path}' ima ulogu "
                f"'{file.role.value}', ocekuje se "
                f"'{expected_role.value}'."
            )

        return file

    @staticmethod
    def _create_item(
        source: MediaSource,
        file: MediaFile,
        artwork_type: ArtworkType,
        *,
        label: str | None,
        is_primary: bool,
        sort_order: int,
    ) -> MediaArtworkCreate:
        return MediaArtworkCreate(
            media_id=source.media_id,
            source_id=source.id,
            artwork_type=artwork_type,
            storage_kind=ArtworkStorageKind.SOURCE,
            relative_path=file.relative_path,
            label=label,
            file_size_bytes=file.size_bytes,
            is_primary=is_primary,
            sort_order=sort_order,
        )