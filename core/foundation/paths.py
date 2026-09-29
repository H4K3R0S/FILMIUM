from pathlib import Path

# ==========          CORE PUTANJE          ==========

class CorePaths:
    """
    Centralni registar putanja CORE sistema.

    Ova klasa definiše najvažnije lokacije koje CORE koristi.
    Ostali moduli treba da koriste ovaj registar umesto hardkodovanih putanja.
    """

    def __init__(self, root_path: Path | None = None) -> None:
        """
        Inicijalizuje CORE putanje.

        Args:
            root_path: Opciona eksplicitna putanja do korena projekta.
                       Ako nije prosleđena, koren se automatski pronalazi.
        """
        self.root = root_path or self._detect_root()

        # Glavni projektni direktorijumi.
        self.apps = self.root / "apps"
        self.config = self.root / "config"
        self.core = self.root / "core"
        self.data = self.root / "data"
        self.docs = self.root / "docs"
        self.integrations = self.root / "integrations"
        self.legacy = self.root / "legacy"
        self.scripts = self.root / "scripts"
        self.tests = self.root / "tests"

        # CORE runtime direktorijumi.
        self.domains = self.core / "domains"
        self.logs = self.data / "logs"
        self.database_dir = self.data / "database"
        self.screenshots = self.data / "screenshots"
        self.editor_projects = self.screenshots / "projects"

        # Centralna SQLite baza CORE sistema.
        # Podrazumevana cell baza = domenska baza (NE vestigijalni "core.db"
        # iz doba kada je postojao CORE iznad domena; CORE vise ne postoji).
        # cell/paths.py ionako pregazi ovo sa manifest.database_path.
        self.core_database = self.data / "filmium.db"

    def _detect_root(self) -> Path:
        """
        Pronalazi koren CORE projekta na osnovu lokacije ovog fajla.

        Returns:
            Putanja do korena CORE projekta.
        """
        return Path(__file__).resolve().parents[2]

    def ensure_required_dirs(self) -> None:
        """
        Kreira bezbedne runtime direktorijume ako ne postoje.

        Ova metoda ne kreira kompletnu projektnu strukturu.
        """
        self.logs.mkdir(parents=True, exist_ok=True)
        self.database_dir.mkdir(parents=True, exist_ok=True)
        self.screenshots.mkdir(parents=True, exist_ok=True)
        self.editor_projects.mkdir(parents=True, exist_ok=True)


core_paths = CorePaths()