import re
from enum import StrEnum
from io import BytesIO
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import ClassVar

try:
    from PIL import Image, ImageOps, UnidentifiedImageError
except ImportError:  # pragma: no cover - okruženje bez Pillow paketa
    Image = None
    ImageOps = None

    class UnidentifiedImageError(OSError):
        """Fallback kada Pillow nije instaliran."""

from core.domains.filmium.artwork_models import (
    ArtworkStorageKind,
    ArtworkType,
)
from core.domains.filmium.artwork_repository import ArtworkRepository
from core.domains.filmium.media_source_repository import (
    MediaSourceRepository,
)
from core.domains.filmium.paths import FilmiumPaths, filmium_paths

# ==========          TIP VIZUELNOG ASSETA          ==========

class MediaAssetType(StrEnum):
    """Podržani tipovi FILMIUM vizuelnih asseta."""

    POSTER = "poster"
    BACKDROP = "backdrop"


# ==========          ASSET GREŠKE          ==========

class MediaAssetValidationError(ValueError):
    """Greška koja označava neispravan vizuelni asset."""


# ==========          MEDIA ASSET SERVICE          ==========

class MediaAssetService:
    """
    Bezbedno čuva vizuelne assete FILMIUM sadržaja.

    Servis određuje krajnju putanju i naziv datoteke. Spoljni slojevi
    zato ne mogu proizvoljno da biraju lokaciju unutar sistema.
    """

    _MAXIMUM_FILE_SIZE = 20 * 1024 * 1024
    _MAXIMUM_DIMENSIONS: ClassVar = {
        MediaAssetType.POSTER: (500, 750),
        MediaAssetType.BACKDROP: (1280, 720),
    }

    # Prepoznaje samo tačan oblik javne putanje ka managed assetu,
    # npr. "posters/1955/poster.jpg" ili "backdrops/42/scene.jpg".
    # Bilo šta drugo (podfolderi, ne-brojevni ID) ne aktivira fallback
    # već zadržava dosadašnje ponašanje.
    _FALLBACK_PATTERN = re.compile(
        r"^(?P<kind>posters|backdrops)/(?P<media_id>\d+)/(?P<filename>[^/]+)$"
    )
    _FALLBACK_ARTWORK_TYPES: ClassVar = {
        "posters": ArtworkType.POSTER,
        "backdrops": ArtworkType.BACKDROP,
    }

    def __init__(
        self,
        paths: FilmiumPaths | None = None,
        media_source_repository: MediaSourceRepository | None = None,
        artwork_repository: ArtworkRepository | None = None,
    ) -> None:
        """
        Inicijalizuje servis vizuelnih asseta.

        Args:
            paths: Opcioni FILMIUM registar putanja za testiranje.
            artwork_repository: Opcioni registar slika. Kada je prisutan,
                omogućava fallback na izvornu sliku iz biblioteke ako
                managed kopija ne postoji na disku (vidi get_asset_path).
        """

        self._paths = paths or filmium_paths
        self._media_source_repository = media_source_repository
        self._artwork_repository = artwork_repository

    def save_asset(
        self,
        item_id: int,
        asset_type: MediaAssetType,
        content: bytes,
        variant: str | None = None,
    ) -> str:
        """
        Proverava i čuva jedan FILMIUM vizuelni asset.

        Args:
            item_id: ID FILMIUM sadržaja kome slika pripada.
            asset_type: Tip slike, poster ili backdrop.
            content: Binarni sadržaj slike.

        Returns:
            Relativna POSIX putanja sačuvane slike.

        Raises:
            MediaAssetValidationError: Ako podaci nisu bezbedni
                ili slika nije podržanog formata.
        """

        if item_id <= 0:
            raise MediaAssetValidationError(
                "ID FILMIUM sadržaja mora biti pozitivan broj."
            )

        if not content:
            raise MediaAssetValidationError(
                "FILMIUM vizuelni asset ne može biti prazan."
            )

        if len(content) > self._MAXIMUM_FILE_SIZE:
            raise MediaAssetValidationError(
                "FILMIUM vizuelni asset ne može biti veći od 20 MB."
            )

        content, extension = self._prepare_cache_asset(
            asset_type,
            content,
        )
        target_directory = self._get_target_directory(
            item_id,
            asset_type,
        )

        base_name = (
            asset_type.value
            if variant is None
            else f"{asset_type.value}-{variant}"
        )

        target_directory.mkdir(parents=True, exist_ok=True)
        self._remove_previous_asset(target_directory, base_name)

        target_path = (
            target_directory
            / f"{base_name}.{extension}"
        )

        self._write_atomically(target_path, content)

        return target_path.relative_to(
            self._paths.assets
        ).as_posix()

    def save_source_cache_asset(
        self,
        item_id: int,
        source_id: int,
        relative_path: str,
        asset_type: MediaAssetType,
    ) -> str | None:
        """Pravi managed preview/cache kopiju slike iz biblioteke."""

        source_path = self._resolve_source_asset_path(
            f"source/{source_id}/{relative_path}"
        )

        if source_path is None:
            return None

        return self.save_asset(
            item_id,
            asset_type,
            source_path.read_bytes(),
        )

    def delete_asset(
        self,
        relative_path: str | None,
    ) -> bool:
        """
        Briše FILMIUM asset određen kontrolisanom relativnom putanjom.

        Returns:
            True ako je datoteka obrisana, inače False.
        """

        if not relative_path:
            return False

        asset_path = self._resolve_asset_path(relative_path)

        if not asset_path.is_file():
            return False

        asset_path.unlink()

        return True

    def get_asset_path(
        self,
        relative_path: str,
    ) -> Path | None:
        """
        Vraća apsolutnu putanju postojećeg FILMIUM asseta.

        Putanja se najpre bezbednosno proverava kako ne bi mogla
        da izađe iz kontrolisanog FILMIUM assets direktorijuma.

        Returns:
            Putanja postojeće datoteke ili None ako ona ne postoji.
        """

        if relative_path.startswith("source/"):
            return self._resolve_source_asset_path(relative_path)

        asset_path = self._resolve_asset_path(relative_path)

        if asset_path.is_file():
            return asset_path

        return self._resolve_source_fallback_path(relative_path)

    def _resolve_source_fallback_path(
        self,
        relative_path: str,
    ) -> Path | None:
        """
        Kada MANAGED kopija ne postoji, pokušava da posluži IZVORNU sliku.

        Veliki broj FILMIUM stavki ima poster_path/backdrop_path koji
        upućuje na managed kopiju koja nikad nije napravljena — taj
        direktorijum jednostavno ne postoji na disku. Prava slika i
        dalje stoji pored filma na biblioteci (npr. na spoljnom disku)
        i indeksirana je u filmium_media_artworks kao storage_kind
        'source'. Umesto da GUI prikaže slomljenu sliku, servis ovde
        posegne za tim izvornim zapisom kao rezervom — ništa se ne
        kopira niti trajno menja, ovo je samo posluživanje na letu.
        """

        if self._artwork_repository is None:
            return None

        match = self._FALLBACK_PATTERN.match(relative_path)

        if match is None:
            return None

        artwork_type = self._FALLBACK_ARTWORK_TYPES[match.group("kind")]

        try:
            media_id = int(match.group("media_id"))
        except ValueError:
            return None

        artworks = self._artwork_repository.list_for_media(
            media_id,
            artwork_type,
        )

        for artwork in artworks:
            if artwork.storage_kind is not ArtworkStorageKind.SOURCE:
                continue

            if artwork.source_id is None:
                continue

            candidate = (
                f"source/{artwork.source_id}/"
                f"{Path(artwork.relative_path).as_posix()}"
            )

            try:
                resolved = self._resolve_source_asset_path(candidate)
            except MediaAssetValidationError:
                # Jedan neispravan zapis ne sme da obori ceo fallback -
                # nastavlja se na sledećeg kandidata.
                continue

            if resolved is not None:
                return resolved

        return None

    def _get_target_directory(
        self,
        item_id: int,
        asset_type: MediaAssetType,
    ) -> Path:
        """Vraća kontrolisani direktorijum za određeni asset."""

        if asset_type is MediaAssetType.POSTER:
            return self._paths.posters / str(item_id)

        if asset_type is MediaAssetType.BACKDROP:
            return self._paths.backdrops / str(item_id)

        raise MediaAssetValidationError(
            "Nepoznat tip FILMIUM vizuelnog asseta."
        )

    def _resolve_asset_path(self, relative_path: str) -> Path:
        """
        Pretvara relativnu asset putanju u bezbednu apsolutnu putanju.

        Sprečava izlazak iz FILMIUM assets direktorijuma korišćenjem
        delova putanje kao što je '..'.
        """

        assets_root = self._paths.assets.resolve()
        asset_path = (
            assets_root / Path(relative_path)
        ).resolve()

        if not asset_path.is_relative_to(assets_root):
            raise MediaAssetValidationError(
                "FILMIUM asset putanja nije bezbedna."
            )

        return asset_path

    def _resolve_source_asset_path(self, relative_path: str) -> Path | None:
        """
        Pretvara kontrolisanu source artwork putanju u fizičku datoteku.

        Format je ``source/<source_id>/<relative_artwork_path>``. Koren
        dolazi isključivo iz registrovanog media source zapisa.
        """

        if self._media_source_repository is None:
            return None

        parts = Path(relative_path).parts

        if len(parts) < 3 or parts[0] != "source":
            raise MediaAssetValidationError(
                "FILMIUM source asset putanja nije bezbedna."
            )

        try:
            source_id = int(parts[1])
        except ValueError as error:
            raise MediaAssetValidationError(
                "FILMIUM source asset ID nije ispravan."
            ) from error

        source = self._media_source_repository.get(source_id)

        if source is None:
            return None

        source_root = Path(source.root_path_snapshot).resolve()
        source_directory = (
            source_root
            if source.relative_directory == "."
            else source_root.joinpath(
                *Path(source.relative_directory).parts
            )
        ).resolve()
        asset_path = source_directory.joinpath(*parts[2:]).resolve()

        try:
            asset_path.relative_to(source_directory)
        except ValueError as error:
            raise MediaAssetValidationError(
                "FILMIUM source asset putanja nije bezbedna."
            ) from error

        if not asset_path.is_file() or asset_path.is_symlink():
            return None

        return asset_path

    @staticmethod
    def _detect_image_extension(content: bytes) -> str:
        """Prepoznaje podržani format slike iz njenog sadržaja."""

        if content.startswith(b"\xff\xd8\xff"):
            return "jpg"

        if content.startswith(b"\x89PNG\r\n\x1a\n"):
            return "png"

        if (
            len(content) >= 12
            and content.startswith(b"RIFF")
            and content[8:12] == b"WEBP"
        ):
            return "webp"

        raise MediaAssetValidationError(
            "Podržani formati slike su JPEG, PNG i WebP."
        )

    @classmethod
    def _prepare_cache_asset(
        cls,
        asset_type: MediaAssetType,
        content: bytes,
    ) -> tuple[bytes, str]:
        """
        Smanjuje validnu sliku u UI cache dimenzije.

        Kada Pillow nije dostupan ili sadržaj nije kompletna slika
        zadržava stari režim čuvanja prema prepoznatom headeru.
        """

        original_extension = cls._detect_image_extension(content)

        if Image is None or ImageOps is None:
            return content, original_extension

        try:
            with Image.open(BytesIO(content)) as image:
                prepared = ImageOps.exif_transpose(image)
                prepared.thumbnail(
                    cls._MAXIMUM_DIMENSIONS[asset_type],
                    Image.Resampling.LANCZOS,
                )

                if prepared.mode not in ("RGB", "L"):
                    prepared = prepared.convert("RGB")

                output = BytesIO()
                prepared.save(
                    output,
                    format="JPEG",
                    quality=82,
                    optimize=True,
                    progressive=True,
                )

                return output.getvalue(), "jpg"
        except (OSError, UnidentifiedImageError):
            return content, original_extension

    @staticmethod
    def _remove_previous_asset(
        target_directory: Path,
        base_name: str,
    ) -> None:
        """Uklanja prethodnu verziju istog vizuelnog asseta."""

        for extension in ("jpg", "png", "webp"):
            previous_path = (
                target_directory
                / f"{base_name}.{extension}"
            )

            if previous_path.is_file():
                previous_path.unlink()

    @staticmethod
    def _write_atomically(
        target_path: Path,
        content: bytes,
    ) -> None:
        """
        Upisuje asset preko privremene datoteke.

        Time se smanjuje mogućnost da prekid procesa ostavi delimično
        upisanu sliku na krajnjoj lokaciji.
        """

        temporary_path: Path | None = None

        try:
            with NamedTemporaryFile(
                mode="wb",
                dir=target_path.parent,
                prefix=f".{target_path.stem}-",
                suffix=".tmp",
                delete=False,
            ) as temporary_file:
                temporary_file.write(content)
                temporary_file.flush()
                temporary_path = Path(temporary_file.name)

            temporary_path.replace(target_path)
        finally:
            if (
                temporary_path is not None
                and temporary_path.exists()
            ):
                temporary_path.unlink()
