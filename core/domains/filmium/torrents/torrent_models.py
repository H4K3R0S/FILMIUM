# ========== MODELI TORRENT MODULA ==========
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

# Kategorija u qBittorrent-u. Modul vidi i dira isključivo torrente iz nje.
QBIT_CATEGORY = "FILMIUM"

DEFAULT_UNSELECTED_EXTENSIONS: tuple[str, ...] = (
    ".nfo", ".txt", ".url", ".jpg", ".png", ".sfv",
)


# ========== STATUSI ==========
class TorrentStatus(str, Enum):
    DETECTED = "detected"                    # zabeležen, još nije poslat klijentu
    METADATA_FETCHING = "metadata_fetching"  # čeka metapodatke (magnet)
    AWAITING_APPROVAL = "awaiting_approval"  # lista fajlova spremna, čeka korisnika
    DOWNLOADING = "downloading"
    PAUSED = "paused"
    COMPLETED = "completed"
    ERROR = "error"


# ========== FAJL UNUTAR TORRENTA ==========
@dataclass(frozen=True)
class TorrentFileEntry:
    file_index: int
    path: str
    size_bytes: int = 0
    selected: bool = True
    # Napredak pojedinačnog fajla (0.0-1.0). Živ podatak iz klijenta; u
    # bazi se NE pamti, pa iz repozitorijuma uvek stiže kao 0.0.
    progress: float = 0.0


# ========== METAPODACI ==========
@dataclass(frozen=True)
class TorrentMetadata:
    info_hash: str
    name: str
    total_bytes: int = 0
    files: tuple[TorrentFileEntry, ...] = ()
    has_metadata: bool = False


# ========== PROGRES ==========
@dataclass(frozen=True)
class TorrentProgress:
    info_hash: str
    name: str = ""               # ime iz klijenta (prazno dok nema metapodataka)
    total_bytes: int = 0         # ukupna veličina torrenta u bajtovima
    progress: float = 0.0        # 0.0 - 1.0
    download_rate: int = 0       # bajtova u sekundi
    upload_rate: int = 0
    eta_seconds: int | None = None
    seeds: int = 0
    peers: int = 0
    is_finished: bool = False
    is_paused: bool = False
    error_message: str | None = None


# ========== ZAPIS TORRENTA ==========
@dataclass
class TorrentEntry:
    info_hash: str
    name: str
    source: str
    source_kind: str = "magnet"   # "magnet" ili "file"
    status: TorrentStatus = TorrentStatus.DETECTED
    save_path: str = ""
    total_bytes: int = 0
    added_at: datetime = field(default_factory=datetime.now)
    completed_at: datetime | None = None
    error_message: str | None = None
    # Kopija .torrent fajla unutar CORE-a; prazno kad kopije nema
    # (magnet link, ili izvor koji pri dodavanju nije bio čitljiv).
    archived_path: str = ""


# ========== PRONAĐEN .torrent FAJL ==========
# Pročitan lokalno, iz samog fajla — qBittorrent za ovo nije potreban.

@dataclass(frozen=True)
class DiscoveredFile:
    file_index: int
    path: str
    size_bytes: int = 0


@dataclass(frozen=True)
class DiscoveredTorrent:
    """Jedna kartica na stranici Torrenti: šta u fajlu piše i šta se s njim desilo."""

    source_path: str
    info_hash: str
    name: str
    total_bytes: int = 0
    files: tuple[DiscoveredFile, ...] = ()
    # Status već dodatog torrenta, ili `None` dok stoji samo kao fajl.
    status: TorrentStatus | None = None
    # Da li je korisnik ovaj torrent već poslao ka uvozu u biblioteku.
    handed_to_library: bool = False


# ========== ZDRAVLJE ENGINE-a ==========
@dataclass(frozen=True)
class EngineHealth:
    available: bool
    version: str | None = None
    message: str | None = None


# ========== PODEŠAVANJA ==========
@dataclass
class TorrentSettings:
    host: str = "127.0.0.1"
    port: int = 8080
    username: str = ""
    password: str = ""
    # Više nadziranih foldera; .torrent fajlovi iz svih njih se nude
    # na stranici Torrenti kao pronađeni, pre nego što išta krene.
    watch_folders: tuple[str, ...] = ()
    download_path: str = ""
    max_download_kbs: int = 0
    max_upload_kbs: int = 0
    max_active: int = 3
    auto_start: bool = True
    seed_after_complete: bool = False
    delete_source_torrent: bool = False
    unselected_extensions: tuple[str, ...] = DEFAULT_UNSELECTED_EXTENSIONS
