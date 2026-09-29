from pathlib import Path

from core.foundation.paths import core_paths

# ==========          FILMIUM PUTANJE          ==========

class FilmiumPaths:
    """
    Centralizuje putanje koje pripadaju FILMIUM domenu.

    Ostali FILMIUM moduli treba da koriste ovaj objekat umesto
    ručnog sastavljanja putanja do postera i backdrop slika.
    """

    def __init__(
        self,
        data_path: Path | None = None,
    ) -> None:
        """
        Inicijalizuje FILMIUM putanje.

        Args:
            data_path: Opcioni osnovni data direktorijum.
                Koristi se prvenstveno u testovima.
        """

        self.data = data_path or core_paths.data

        self.root = self.data / "filmium"
        self.assets = self.root / "assets"
        self.posters = self.assets / "posters"
        self.backdrops = self.assets / "backdrops"
        self.wishlist = self.assets / "wishlist"

    def ensure_asset_dirs(self) -> None:
        """
        Kreira bezbedne direktorijume za FILMIUM vizuelne assete.

        Metoda ne kreira projektnu strukturu, već samo direktorijume
        koji su potrebni tokom rada aplikacije.
        """

        self.posters.mkdir(parents=True, exist_ok=True)
        self.backdrops.mkdir(parents=True, exist_ok=True)


# ==========          JAVNI FILMIUM PATH REGISTAR          ==========

filmium_paths = FilmiumPaths()