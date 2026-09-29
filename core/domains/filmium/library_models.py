from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from core.domains.filmium.models import MediaType

# ==========          STATUS VLASNISTVA          ==========

class MediaOwnershipStatus(StrEnum):
    """Odredjuje da li korisnik poseduje video datoteku."""

    OWNED = "owned"
    CATALOG_ONLY = "catalog_only"


# ==========          STATUS BIBLIOTEKE          ==========

class LibraryRootStatus(StrEnum):
    """Opisuje dostupnost korena jedne lokalne biblioteke."""

    AVAILABLE = "available"
    OFFLINE = "offline"
    DISABLED = "disabled"


# ==========          STATUS DATOTEKE          ==========

class MediaFileStatus(StrEnum):
    """Opisuje trenutno stanje indeksirane datoteke."""

    AVAILABLE = "available"
    OFFLINE = "offline"
    MISSING = "missing"


# ==========          ULOGA DATOTEKE          ==========

class MediaFileRole(StrEnum):
    """Podrzane uloge datoteka unutar filmskog direktorijuma."""

    VIDEO = "video"
    POSTER = "poster"
    BACKDROP = "backdrop"
    WALLPAPER = "wallpaper"
    FANART = "fanart"
    TRAILER = "trailer"
    SUBTITLE = "subtitle"
    MANIFEST = "manifest"
    UNKNOWN = "unknown"


# ==========          PREVOD U MANIFESTU          ==========

@dataclass(frozen=True)
class SubtitleManifest:
    """Relativna putanja i jezik jednog prevoda."""

    path: str
    language: str
    label: str | None = None


# ==========          SLIKA U MANIFESTU          ==========

@dataclass(frozen=True)
class ArtworkManifest:
    """Prenosiva referenca ka wallpaper ili fanart slici."""

    path: str
    label: str | None = None
    is_primary: bool = False


# ==========          DATOTEKE U MANIFESTU          ==========

@dataclass(frozen=True)
class MediaFilesManifest:
    """Relativne putanje prenosivih datoteka jednog sadrzaja."""

    video: str | None = None
    poster: str | None = None
    backdrop: str | None = None
    trailer: str | None = None
    subtitles: tuple[SubtitleManifest, ...] = ()
    wallpapers: tuple[ArtworkManifest, ...] = ()
    fanart: tuple[ArtworkManifest, ...] = ()


# ==========          SEZONE I EPIZODE (MANIFEST)          ==========

@dataclass(frozen=True)
class EpisodeManifest:
    """Jedna epizoda u serijskom manifestu."""

    episode_number: int
    title: str | None = None


@dataclass(frozen=True)
class SeasonManifest:
    """Jedna sezona sa svojim epizodama."""

    season_number: int
    name: str | None = None
    episodes: tuple[EpisodeManifest, ...] = ()


# ==========          FILMIUM INFO MANIFEST          ==========

@dataclass(frozen=True)
class FilmiumInfoManifest:
    """Prenosivi podaci sacuvani u filmium_info.json datoteci."""

    title: str
    media_type: MediaType
    release_year: int | None
    schema_version: int = 2
    original_title: str | None = None
    runtime_minutes: int | None = None
    description: str | None = None
    genres: tuple[str, ...] = ()
    studio: str | None = None
    franchise: str | None = None
    franchise_order: int | None = None
    ownership_status: MediaOwnershipStatus = (
        MediaOwnershipStatus.OWNED
    )
    # Kategorija sadržaja: "regular" (Film), "animated" (Anime) ili
    # "domestic" (Domaći) — biblioteka po ovome zna gde sadržaj pripada.
    # NAPOMENA: podatak iz toggla Titlovano/Sinhronizovano se NE upisuje u
    # manifest — on je lična oznaka i čuva se samo u bazi.
    content_category: str = "regular"
    files: MediaFilesManifest = MediaFilesManifest()
    # Opciono: sezone/epizode (za serije). Prazno za filmove. Aditivno polje
    # — stari manifesti bez njega se učitavaju kao prazno (bez promene verzije).
    seasons: tuple[SeasonManifest, ...] = ()


# ==========          PRONADJENA DATOTEKA          ==========

@dataclass(frozen=True)
class ScannedMediaFile:
    """Datoteka koju je skener prepoznao u izvornom folderu."""

    path: Path
    role: MediaFileRole
    size_bytes: int
    language: str | None = None


# ==========          REZULTAT SKENIRANJA          ==========

@dataclass(frozen=True)
class MediaFolderScanResult:
    """Rezultat bezbednog skeniranja jednog filmskog foldera."""

    directory: Path
    title: str
    release_year: int | None
    manifest: FilmiumInfoManifest
    detected_files: tuple[ScannedMediaFile, ...] = ()
    warnings: tuple[str, ...] = ()

    @property
    def can_import(self) -> bool:
        """Vraca True kada skeniranje nema blokirajuca upozorenja."""

        return not self.warnings


# ==========          AKCIJA ORGANIZACIJE          ==========

class OrganizationActionType(StrEnum):
    """Podrzane nedestruktivne stavke plana organizacije."""

    CREATE_DIRECTORY = "create_directory"
    MOVE_FILE = "move_file"
    WRITE_MANIFEST = "write_manifest"


@dataclass(frozen=True)
class OrganizationAction:
    """Jedna predlozena promena koja jos nije izvrsena."""

    action_type: OrganizationActionType
    destination: Path
    reason: str
    source: Path | None = None


# ==========          PLAN ORGANIZACIJE          ==========

@dataclass(frozen=True)
class MediaOrganizationPlan:
    """Pregled promena koje FILMIUM predlaze pre potvrde korisnika."""

    source_directory: Path
    target_directory: Path
    manifest: FilmiumInfoManifest
    detected_files: tuple[ScannedMediaFile, ...] = ()
    actions: tuple[OrganizationAction, ...] = ()
    warnings: tuple[str, ...] = ()
    # Meka upozorenja (npr. fajl već na odredištu pri re-skenu) — prikazuju
    # se informativno, ali NE blokiraju potvrdu uvoza.
    soft_warnings: tuple[str, ...] = ()

    @property
    def has_changes(self) -> bool:
        """Vraca True kada plan sadrzi bar jednu filesystem akciju."""

        return bool(self.actions)

    @property
    def can_apply(self) -> bool:
        """Vraca True kada plan nema upozorenja koja blokiraju potvrdu."""

        return not self.warnings