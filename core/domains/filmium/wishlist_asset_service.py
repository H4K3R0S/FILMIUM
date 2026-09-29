from pathlib import Path
from tempfile import NamedTemporaryFile

from core.domains.filmium.paths import FilmiumPaths, filmium_paths

# ==========          WISHLIST ASSET GREŠKE          ==========

class WishlistAssetValidationError(ValueError):
    """Greška koja označava neispravan wishlist asset."""


# Dozvoljene vrste asseta i njihova bazna imena datoteka.
_ASSET_KINDS = {
    "poster": "poster",
    "backdrop": "backdrop",
    "wallpaper": "wallpaper",
    "original_subtitle": "subtitle-original",
    "domestic_subtitle": "subtitle-domestic",
    "english_subtitle": "subtitle-english",
    "extra": "extra",
}

# Kolona repozitorijuma po vrsti asseta (extra ide u JSON listu, nije ovde).
ASSET_KIND_COLUMN = {
    "poster": "poster_path",
    "backdrop": "backdrop_path",
    "wallpaper": "wallpaper_path",
    "original_subtitle": "original_subtitle_path",
    "domestic_subtitle": "domestic_subtitle_path",
    "english_subtitle": "english_subtitle_path",
}

_IMAGE_EXTENSIONS = frozenset({"jpg", "jpeg", "png", "webp", "gif"})
_SUBTITLE_EXTENSIONS = frozenset({"srt", "sub", "ass", "ssa", "vtt"})
_MAXIMUM_FILE_SIZE = 25 * 1024 * 1024


# ==========          WISHLIST ASSET SERVICE          ==========

class WishlistAssetService:
    """
    Čuva datoteke liste za preuzimanje (slike i titlove).

    Servis sam bira lokaciju: ``assets/wishlist/<id>/<naziv>.<ext>``. Za
    „extra" sadržaj datoteke se ne prepisuju, već dobijaju jedinstven redni
    sufiks. Slike i titlovi se čuvaju bez izmene sadržaja.
    """

    def __init__(self, paths: FilmiumPaths | None = None) -> None:
        """Inicijalizuje wishlist asset servis."""

        self._paths = paths or filmium_paths

    def save(
        self,
        entry_id: int,
        kind: str,
        filename: str,
        content: bytes,
    ) -> str:
        """
        Čuva jednu wishlist datoteku i vraća relativnu POSIX putanju.

        Args:
            entry_id: ID stavke liste za preuzimanje.
            kind: Vrsta asseta (poster/backdrop/wallpaper/*_subtitle/extra).
            filename: Originalno ime (koristi se samo za ekstenziju).
            content: Binarni sadržaj datoteke.
        """

        if entry_id <= 0:
            raise WishlistAssetValidationError(
                "ID stavke mora biti pozitivan broj."
            )

        if kind not in _ASSET_KINDS:
            raise WishlistAssetValidationError(
                f"Nepoznata vrsta wishlist asseta: {kind}"
            )

        if not content:
            raise WishlistAssetValidationError(
                "Wishlist datoteka ne može biti prazna."
            )

        if len(content) > _MAXIMUM_FILE_SIZE:
            raise WishlistAssetValidationError(
                "Wishlist datoteka ne može biti veća od 25 MB."
            )

        extension = self._resolve_extension(kind, filename)

        target_directory = self._paths.wishlist / str(entry_id)
        target_directory.mkdir(parents=True, exist_ok=True)

        base_name = _ASSET_KINDS[kind]

        if kind == "extra":
            index = self._next_extra_index(target_directory)
            target_name = f"{base_name}-{index}.{extension}"
        else:
            self._remove_previous(target_directory, base_name)
            target_name = f"{base_name}.{extension}"

        target_path = target_directory / target_name
        self._write_atomically(target_path, content)

        return target_path.relative_to(self._paths.assets).as_posix()

    # ==========          POMOĆNE METODE          ==========

    @staticmethod
    def _resolve_extension(kind: str, filename: str) -> str:
        """Bira i proverava ekstenziju prema vrsti asseta."""

        extension = Path(filename).suffix.lower().lstrip(".") or "bin"
        is_subtitle_kind = kind.endswith("subtitle")

        if is_subtitle_kind:
            if extension not in _SUBTITLE_EXTENSIONS:
                raise WishlistAssetValidationError(
                    "Podržani formati titla su SRT, SUB, ASS, SSA i VTT."
                )
            return extension

        if kind in {"poster", "backdrop", "wallpaper"}:
            if extension not in _IMAGE_EXTENSIONS:
                raise WishlistAssetValidationError(
                    "Podržani formati slike su JPEG, PNG, WebP i GIF."
                )
            return extension

        # extra: dozvoli i sliku i titl.
        if extension in _IMAGE_EXTENSIONS or extension in _SUBTITLE_EXTENSIONS:
            return extension

        raise WishlistAssetValidationError(
            "Dodatni sadržaj mora biti slika ili titl."
        )

    @staticmethod
    def _next_extra_index(target_directory: Path) -> int:
        """Vraća sledeći redni broj za „extra" datoteku."""

        existing = list(target_directory.glob("extra-*"))
        return len(existing) + 1

    @staticmethod
    def _remove_previous(target_directory: Path, base_name: str) -> None:
        """Uklanja prethodnu verziju istog asseta (bilo koje ekstenzije)."""

        for previous in target_directory.glob(f"{base_name}.*"):
            if previous.is_file():
                previous.unlink()

    @staticmethod
    def _write_atomically(target_path: Path, content: bytes) -> None:
        """Upisuje datoteku preko privremene datoteke."""

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
            if temporary_path is not None and temporary_path.exists():
                temporary_path.unlink()
