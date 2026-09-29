from core.domains.filmium.activity_repository import (
    ActivityRepository,
)
from core.domains.filmium.activity_service import ActivityService
from core.domains.filmium.artwork_repository import ArtworkRepository
from core.domains.filmium.artwork_sync_service import ArtworkSyncService
from core.domains.filmium.asset_service import MediaAssetService
from core.domains.filmium.collection_repository import (
    CollectionRepository,
)
from core.domains.filmium.collection_service import CollectionService
from core.domains.filmium.episode_repository import EpisodeRepository
from core.domains.filmium.ignored_directory_repository import (
    IgnoredDirectoryRepository,
)
from core.domains.filmium.library_date_repository import (
    LibraryDateRepository,
)
from core.domains.filmium.library_date_service import LibraryDateService
from core.domains.filmium.library_import_commit_service import (
    LibraryImportCommitService,
)
from core.domains.filmium.library_import_service import (
    LibraryImportService,
)
from core.domains.filmium.library_root_repository import (
    LibraryRootRepository,
)
from core.domains.filmium.library_root_service import LibraryRootService
from core.domains.filmium.localization_repository import (
    LocalizationRepository,
)
from core.domains.filmium.localization_service import LocalizationService
from core.domains.filmium.media_source_repository import (
    MediaSourceRepository,
)
from core.domains.filmium.media_source_service import MediaSourceService
from core.domains.filmium.repository import MediaRepository
from core.domains.filmium.season_repository import SeasonRepository
from core.domains.filmium.series_import_service import (
    SeriesImportService,
)
from core.domains.filmium.service import FilmiumService
from core.domains.filmium.share_repository import ShareRepository
from core.domains.filmium.share_service import ShareService
from core.domains.filmium.share_transfer_service import (
    ShareTransferService,
)
from core.domains.filmium.subtitle_inspector_service import (
    SubtitleInspectorService,
)
from core.domains.filmium.subtitle_repair_queue_repository import (
    SubtitleRepairQueueRepository,
)
from core.domains.filmium.subtitle_repair_queue_service import (
    SubtitleRepairQueueService,
)
from core.domains.filmium.subtitle_repair_service import (
    SubtitleRepairService,
)
from core.domains.filmium.subtitle_scan_service import (
    SubtitleScanService,
)
from core.domains.filmium.visual_service import MediaVisualService
from core.domains.filmium.wishlist_asset_service import (
    WishlistAssetService,
)
from core.domains.filmium.wishlist_repository import WishlistRepository
from core.domains.filmium.wishlist_service import WishlistService
from core.foundation.lifecycle import RuntimeLifecycle, runtime_lifecycle

# ==========          FOUNDATION DEPENDENCIES          ==========

def get_runtime_lifecycle() -> RuntimeLifecycle:
    """Vraca CORE runtime lifecycle (stanje sistema)."""

    return runtime_lifecycle


# ==========          FILMIUM REPOSITORIES          ==========

_media_repository = MediaRepository()
_collection_repository = CollectionRepository()
_wishlist_repository = WishlistRepository()
_activity_repository = ActivityRepository()
_library_root_repository = LibraryRootRepository()
_ignored_directory_repository = IgnoredDirectoryRepository()
_season_repository = SeasonRepository()
_episode_repository = EpisodeRepository()
_media_source_repository = MediaSourceRepository()
_artwork_repository = ArtworkRepository()
_share_repository = ShareRepository()
_localization_repository = LocalizationRepository()
_library_date_repository = LibraryDateRepository()
_subtitle_repair_queue_repository = SubtitleRepairQueueRepository()


# ==========          FILMIUM ASSET SERVICES          ==========

_media_asset_service = MediaAssetService(
    media_source_repository=_media_source_repository,
    artwork_repository=_artwork_repository,
)

_media_visual_service = MediaVisualService(
    _media_repository,
    _media_asset_service,
)

_artwork_sync_service = ArtworkSyncService(
    _artwork_repository
)


# ==========          FILMIUM SERVICES          ==========

_activity_service = ActivityService(_activity_repository)

_filmium_service = FilmiumService(
    _media_repository,
    _activity_service,
    _media_asset_service,
    _artwork_repository,
    _media_source_repository,
)

_collection_service = CollectionService(
    _collection_repository,
    _media_repository,
    _activity_service,
)

_wishlist_service = WishlistService(_wishlist_repository)

_wishlist_asset_service = WishlistAssetService()

_media_source_service = MediaSourceService(
    _media_source_repository,
    _media_repository,
    _library_root_repository,
    _artwork_sync_service,
)

_library_import_service = LibraryImportService(
    _library_root_repository,
    _media_repository,
)

_library_import_commit_service = LibraryImportCommitService(
    _library_import_service,
    _library_root_repository,
    _media_repository,
    _media_source_service,
    _artwork_sync_service,
    _media_visual_service,
)

_share_service = ShareService(_share_repository)

_share_transfer_service = ShareTransferService(
    _media_source_repository,
)

_localization_service = LocalizationService(
    _localization_repository
)

_library_date_service = LibraryDateService(
    _library_date_repository
)

_subtitle_inspector_service = SubtitleInspectorService()

_subtitle_repair_service = SubtitleRepairService(
    _subtitle_inspector_service
)

_subtitle_repair_queue_service = SubtitleRepairQueueService(
    _subtitle_repair_queue_repository
)

_subtitle_scan_service = SubtitleScanService(
    _subtitle_repair_service,
    _subtitle_repair_queue_service,
)

_library_root_service = LibraryRootService(
    _library_root_repository,
    _subtitle_scan_service,
    _media_repository,
    _media_source_service,
    _ignored_directory_repository,
)

_series_import_service = SeriesImportService(
    _media_repository,
    _season_repository,
    _episode_repository,
    _library_root_repository,
    _media_asset_service,
    _media_source_service,
)


# ==========          API DEPENDENCIES          ==========

def get_filmium_service() -> FilmiumService:
    """Vraca FILMIUM media servis koji API koristi."""

    return _filmium_service


def get_collection_service() -> CollectionService:
    """Vraca FILMIUM collection servis koji API koristi."""

    return _collection_service


def get_activity_service() -> ActivityService:
    """Vraca FILMIUM activity servis koji API koristi."""

    return _activity_service


def get_wishlist_service() -> WishlistService:
    """Vraca servis liste „za preuzeti"."""

    return _wishlist_service


def get_wishlist_asset_service() -> WishlistAssetService:
    """Vraca servis datoteka liste „za preuzeti"."""

    return _wishlist_asset_service


def get_media_visual_service() -> MediaVisualService:
    """Vraca servis za upravljanje posterima i backdrop slikama."""

    return _media_visual_service


def get_media_asset_service() -> MediaAssetService:
    """Vraca servis za pristup FILMIUM vizuelnim datotekama."""

    return _media_asset_service


def get_library_root_service() -> LibraryRootService:
    """Vraca servis registrovanih FILMIUM biblioteka."""

    return _library_root_service


def get_media_source_service() -> MediaSourceService:
    """Vraca servis fizickih izvora FILMIUM sadrzaja."""

    return _media_source_service


def get_library_import_service() -> LibraryImportService:
    """Vraca servis nedestruktivnog pregleda uvoza."""

    return _library_import_service


def get_library_import_commit_service() -> LibraryImportCommitService:
    """Vraca servis koji izvrsava eksplicitno potvrdjen uvoz."""

    return _library_import_commit_service


def get_series_import_service() -> SeriesImportService:
    """Vraca servis za pregled i uvoz serija."""

    return _series_import_service


def get_season_repository() -> SeasonRepository:
    """Vraca repozitorijum sezona (za prikaz epizoda na detaljima)."""

    return _season_repository


def get_episode_repository() -> EpisodeRepository:
    """Vraca repozitorijum epizoda."""

    return _episode_repository


def get_media_source_repository() -> MediaSourceRepository:
    """Vraca repozitorijum izvora sadržaja (za putanje epizoda)."""

    return _media_source_repository


def get_library_root_repository() -> LibraryRootRepository:
    """Vraca repozitorijum registrovanih biblioteka (za putanje epizoda)."""

    return _library_root_repository


def get_share_service() -> ShareService:
    """Vraca servis opste FILMIUM funkcije Podeli."""

    return _share_service


def get_share_transfer_service() -> ShareTransferService:
    """Vraca servis koji stvarno kopira sadrzaj na izabranu lokaciju."""

    return _share_transfer_service


def get_localization_service() -> LocalizationService:
    """Vraca servis porekla, jezika, titlova i sinhronizacija."""

    return _localization_service


def get_library_date_service() -> LibraryDateService:
    """Vraca servis korisnickog datuma ulaska u biblioteku."""

    return _library_date_service


def get_subtitle_repair_service() -> SubtitleRepairService:
    """Vraca servis pregleda i bezbedne popravke prevoda."""

    return _subtitle_repair_service


def get_subtitle_repair_queue_service() -> SubtitleRepairQueueService:
    """Vraca trajni red odeljka Popravi prevod."""

    return _subtitle_repair_queue_service
