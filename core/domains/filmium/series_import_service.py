"""Uvoz serije: organizacija na disku + registracija u FILMIUM katalog."""

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from core.domains.filmium import tmdb_client
from core.domains.filmium.asset_service import MediaAssetService
from core.domains.filmium.episode_repository import EpisodeRepository
from core.domains.filmium.library_category import (
    series_base_parts,
)
from core.domains.filmium.library_import_models import (
    MediaTechnicalInfo,
)
from core.domains.filmium.library_manifest import (
    FILMIUM_INFO_FILE_NAME,
)
from core.domains.filmium.library_root_repository import (
    LibraryRootRepository,
)
from core.domains.filmium.media_finders import (
    find_video_files,
)
from core.domains.filmium.media_source_service import MediaSourceService
from core.domains.filmium.models import (
    MediaType,
)
from core.domains.filmium.repository import MediaRepository
from core.domains.filmium.season_repository import SeasonRepository
from core.domains.filmium.series_import_helpers import (
    _ensure_thumb_safe,
    _infer_content_mode,
    _title_identity,
    fetch_series_enrichment,
)
from core.domains.filmium.series_import_refresh import _SeriesRefreshMixin
from core.domains.filmium.series_organizer import (
    cleanup_source_directory,
    execute_series_organization,
    plan_series_organization,
)
from core.domains.filmium.series_scanner import (
    SeriesScanResult,
    scan_series_directory,
    scan_series_library,
)
from core.domains.filmium.series_visual_sync import apply_series_artwork

# ==========          GREŠKE          ==========

class SeriesImportError(RuntimeError):
    """Označava seriju koju nije moguće bezbedno uvesti."""


# ==========          REZULTAT          ==========

@dataclass(frozen=True)
class SeriesImportResult:
    media_id: int
    series_title: str
    target_directory: str
    season_count: int
    episode_count: int
    created_media: bool


@dataclass
class LibraryRefreshResult:
    """Sažetak osvežavanja biblioteke serija."""

    scanned_series: int = 0
    new_series: int = 0
    posters_added: int = 0
    backdrops_added: int = 0
    season_posters_added: int = 0
    season_backdrops_added: int = 0
    seasons_added: int = 0
    episodes_added: int = 0
    manifests_written: int = 0
    removed_series: int = 0
    movie_folders_scanned: int = 0
    movie_sources_added: int = 0
    errors: int = 0


# ==========          TMDB OBOGAĆIVANJE          ==========

class SeriesImportService(_SeriesRefreshMixin):
    """Koordinira skeniranje, organizaciju i registraciju serije."""

    def __init__(
        self,
        media_repository: MediaRepository,
        season_repository: SeasonRepository,
        episode_repository: EpisodeRepository,
        root_repository: LibraryRootRepository | None = None,
        asset_service: MediaAssetService | None = None,
        media_source_service: MediaSourceService | None = None,
    ) -> None:
        self._media_repository = media_repository
        self._season_repository = season_repository
        self._episode_repository = episode_repository
        self._root_repository = root_repository
        self._asset_service = asset_service
        self._media_source_service = media_source_service

    # ==========          ULAZ IZ BIBLIOTEKE          ==========

    def preview(
        self,
        root_id: int,
        relative_directory: str,
    ) -> SeriesScanResult:
        """Skenira folder biblioteke i vraća strukturu serije."""

        return scan_series_directory(
            self._resolve_directory(root_id, relative_directory)
        )

    def preview_library(
        self,
        root_id: int,
        relative_directory: str,
    ) -> tuple[Path, list[tuple[str, SeriesScanResult]]]:
        """Skenira folder koji može sadržati VIŠE serija.

        Vraća (koren biblioteke, lista (relativni folder serije, rezultat)).
        Ako je izabran folder jedne serije, lista ima jednu stavku.
        """

        root = self._require_repository().get(root_id)
        if root is None:
            raise SeriesImportError(
                "Registrovana FILMIUM biblioteka ne postoji."
            )

        root_path = Path(root.path).resolve(strict=False)
        base = self._resolve_directory(root_id, relative_directory)

        results: list[tuple[str, SeriesScanResult]] = []
        for scan in scan_series_library(base):
            try:
                relative = (
                    scan.directory.resolve(strict=False)
                    .relative_to(root_path)
                    .as_posix()
                )
            except ValueError:
                relative = relative_directory
            results.append((relative or ".", scan))

        return root_path, results

    def probe_episode(
        self,
        root_id: int,
        source: str,
    ) -> MediaTechnicalInfo | None:
        """Čita tehničke podatke epizode (ffprobe) po putanji od korena."""

        from core.domains.filmium.media_probe import probe_video_file

        video = self._resolve_file(root_id, source)
        return probe_video_file(video)

    def episode_thumbnail(self, root_id: int, source: str) -> Path | None:
        """Vraća putanju sličice epizode (ffmpeg, keširano) ili ``None``."""

        from core.domains.filmium.media_thumbnail import (
            generate_episode_thumbnail,
        )

        video = self._resolve_file(root_id, source)
        return generate_episode_thumbnail(video)

    def reveal_file(self, root_id: int, relative_source: str) -> bool:
        """Otvara sistemski menadžer fajlova na lokaciji fajla u korenu."""

        from core.domains.filmium.reveal_path import reveal_in_file_manager

        target = self._resolve_file(root_id, relative_source)
        return reveal_in_file_manager(target)

    def replace_file(
        self,
        root_id: int,
        relative_target: str,
        source_path: str,
    ) -> bool:
        """Prekopira izabrani fajl preko postojećeg (npr. zamena slike)."""

        import shutil

        target = self._resolve_file(root_id, relative_target)
        source = Path(source_path)

        if not source.is_file():
            raise SeriesImportError("Izabrani fajl ne postoji.")

        try:
            shutil.copyfile(source, target)
        except OSError as error:
            raise SeriesImportError(
                f"Zamena fajla nije uspela: {error}"
            ) from error

        return True

    def resolve_media_file(self, root_id: int, relative_source: str) -> Path:
        """Javno rešavanje putanje fajla (za stream/reprodukciju)."""

        return self._resolve_file(root_id, relative_source)

    def resolve_playable_video(
        self, root_id: int, relative_source: str
    ) -> Path:
        """Kao ``resolve_media_file``, ali ako tačan fajl ne postoji traži
        bilo koji video u istom folderu (tolerancija na malu razliku putanje).
        """

        try:
            return self._resolve_file(root_id, relative_source)
        except SeriesImportError:
            pass

        root = self._require_repository().get(root_id)
        if root is None:
            raise SeriesImportError(
                "Registrovana FILMIUM biblioteka ne postoji."
            )

        root_path = Path(root.path).resolve(strict=False)
        normalized = relative_source.strip().replace("\\", "/")
        parent = PurePosixPath(normalized).parent

        if parent.is_absolute() or ".." in parent.parts:
            raise SeriesImportError("Fajl izlazi iz registrovane biblioteke.")

        dir_path = root_path.joinpath(*parent.parts).resolve(strict=False)
        try:
            dir_path.relative_to(root_path)
        except ValueError as error:
            raise SeriesImportError(
                "Fajl izlazi iz registrovane biblioteke."
            ) from error

        if dir_path.is_dir():
            videos = find_video_files(dir_path)
            if videos:
                return videos[0]

        raise SeriesImportError("Video fajl nije pronađen.")

    def _resolve_file(self, root_id: int, relative_source: str) -> Path:
        """Bezbedno rešava putanju fajla unutar registrovanog korena."""

        root = self._require_repository().get(root_id)
        if root is None:
            raise SeriesImportError(
                "Registrovana FILMIUM biblioteka ne postoji."
            )

        root_path = Path(root.path).resolve(strict=False)
        normalized = relative_source.strip().replace("\\", "/")
        relative = PurePosixPath(normalized)

        if relative.is_absolute() or ".." in relative.parts:
            raise SeriesImportError("Fajl izlazi iz registrovane biblioteke.")

        candidate = root_path.joinpath(*relative.parts).resolve(strict=False)

        try:
            candidate.relative_to(root_path)
        except ValueError as error:
            raise SeriesImportError(
                "Fajl izlazi iz registrovane biblioteke."
            ) from error

        if not candidate.is_file():
            raise SeriesImportError("Izabrani fajl ne postoji.")

        return candidate

    def import_from_library(
        self,
        root_id: int,
        relative_directory: str,
        *,
        target_library_root_id: int | None = None,
        confirmed: bool = False,
        on_progress: Callable[[int, int, int, int], None] | None = None,
        content_mode: str = "regular",
        synchronized: bool = False,
    ) -> SeriesImportResult:
        """Uvozi seriju iz foldera biblioteke u izabranu (ili glavnu)."""

        source = self._resolve_directory(root_id, relative_directory)
        target_root_id = self._resolve_target_root_id(
            root_id,
            target_library_root_id,
        )
        target_root = self._require_repository().get(target_root_id)

        if target_root is None:
            raise SeriesImportError(
                "Ciljna FILMIUM biblioteka ne postoji."
            )

        return self.import_series(
            source,
            Path(target_root.path),
            confirmed=confirmed,
            on_progress=on_progress,
            content_mode=content_mode,
            synchronized=synchronized,
        )

    def _resolve_target_root_id(
        self,
        root_id: int,
        target_library_root_id: int | None,
    ) -> int:
        if target_library_root_id is not None:
            return target_library_root_id

        main = next(
            (
                root
                for root in self._require_repository().list_all()
                if root.is_main
            ),
            None,
        )
        return main.id if main is not None else root_id

    def _resolve_directory(
        self,
        root_id: int,
        relative_directory: str,
    ) -> Path:
        root = self._require_repository().get(root_id)

        if root is None:
            raise SeriesImportError(
                "Registrovana FILMIUM biblioteka ne postoji."
            )

        root_path = Path(root.path).resolve(strict=False)
        normalized = relative_directory.strip().replace("\\", "/")
        relative = PurePosixPath(normalized)

        if relative.is_absolute() or ".." in relative.parts:
            raise SeriesImportError(
                "Folder izlazi iz registrovane biblioteke."
            )

        candidate = root_path.joinpath(*relative.parts).resolve(
            strict=False
        )

        try:
            candidate.relative_to(root_path)
        except ValueError as error:
            raise SeriesImportError(
                "Folder izlazi iz registrovane biblioteke."
            ) from error

        if not candidate.is_dir():
            raise SeriesImportError("Izabrani folder ne postoji.")

        return candidate

    def _require_repository(self) -> LibraryRootRepository:
        if self._root_repository is None:
            raise SeriesImportError(
                "Repozitorijum biblioteka nije konfigurisan."
            )

        return self._root_repository

    def _resolve_scan(self, source: Path) -> SeriesScanResult:
        """Vraća skeniranje serije koje ČUVA spajanje razbacanih sezona.

        Pregled koristi ``scan_series_library`` (spaja sezone iz susednih
        foldera), pa i uvoz mora isto — inače bi se uvezla samo sezona iz
        jednog foldera. Skenira roditelja i bira seriju čiji je folder baš
        izabrani; ako je nema, tretira sam folder kao seriju.
        """

        source = source.resolve(strict=False)
        parent = source.parent

        try:
            candidates = scan_series_library(parent)
        except OSError:
            candidates = []

        for candidate in candidates:
            if candidate.directory.resolve(strict=False) == source:
                return candidate

        return scan_series_directory(source)

    def import_series(
        self,
        source_directory: Path,
        library_root: Path,
        *,
        confirmed: bool = False,
        on_progress: Callable[[int, int, int, int], None] | None = None,
        content_mode: str = "regular",
        synchronized: bool = False,
    ) -> SeriesImportResult:
        if not confirmed:
            raise SeriesImportError("Uvoz serije nije potvrđen.")

        scan = self._resolve_scan(Path(source_directory))

        if not any(season.episodes for season in scan.seasons):
            raise SeriesImportError(
                "U folderu nije prepoznata nijedna epizoda."
            )

        # Serija ide u <koren>/<kategorija>/Serije
        # (regular=Strano, domestic=Domace, animated=Animirano).
        library_base = Path(library_root).joinpath(
            *series_base_parts(content_mode)
        )
        library_base.mkdir(parents=True, exist_ok=True)
        plan = plan_series_organization(scan, library_base)
        execution = execute_series_organization(
            plan, confirmed=True, on_progress=on_progress
        )

        # TMDB provera/dopuna naslova/opisa (izvorni/engleski/lokalni).
        title_enrichment = tmdb_client.enrich_series(
            scan.title, getattr(scan, "year", None)
        )
        media, created = self._resolve_series(
            scan.title, title_enrichment, content_mode, synchronized
        )

        # TMDB: lokalizovana imena sezona/epizoda (sr → hr → bs → en).
        enrichment = fetch_series_enrichment(scan)

        season_count = 0
        episode_count = 0

        for season in scan.seasons:
            db_season = self._season_repository.ensure(
                media.id,
                season.season_number,
                name=enrichment.season_name(season.season_number)
                or season.name,
            )
            season_count += 1

            for episode in season.episodes:
                self._episode_repository.ensure(
                    db_season.id,
                    episode.episode_number,
                    title=(
                        enrichment.episode_title(
                            season.season_number, episode.episode_number
                        )
                        or episode.title
                    ),
                )
                episode_count += 1

        # Slike serije + po sezoni: skenira organizovani folder (iste skripte
        # kao upload) i registruje managed kopije. Best-effort.
        if self._asset_service is not None:
            try:
                apply_series_artwork(
                    execution.target_directory,
                    media.id,
                    asset_service=self._asset_service,
                    season_repository=self._season_repository,
                    media_repository=self._media_repository,
                    enrichment=title_enrichment,
                )
            except Exception:  # noqa: BLE001, S110
                pass

        # Registruje video/prevode epizoda (za sličice i reprodukciju).
        final_scan = self._resolve_scan(execution.target_directory)
        self._register_series_source(final_scan, media.id)

        # Upis filmium_info.json za seriju (ime, opis, sezone/epizode).
        # Manifest je pomoćni — neuspeh ne sme da sruši uspešan uvoz.
        self._write_series_manifest(
            execution.target_directory, scan, media, enrichment
        )

        # Čišćenje izvora: .bak backupi prevoda, prazni poddirektorijumi i
        # sam izvorni folder serije. Best-effort — ne ruši uspešan uvoz.
        cleanup_source_directory(
            Path(source_directory), keep=execution.target_directory
        )

        return SeriesImportResult(
            media_id=media.id,
            series_title=scan.title,
            target_directory=str(execution.target_directory),
            season_count=season_count,
            episode_count=episode_count,
            created_media=created,
        )

    # ==========          OSVEŽAVANJE BIBLIOTEKE          ==========

    def refresh_library(self) -> LibraryRefreshResult:
        """Skenira sve registrovane biblioteke i dopunjava bazu.

        Za svaku seriju u biblioteci: dopuni poster/backdrop (serija + po
        sezoni) iz novih slika, registruje nove sezone/epizode, i ako
        filmium_info.json nedostaje — regeneriše ga. Nove serije koje već
        stoje u biblioteci se registruju u mestu (bez reorganizacije).
        """

        result = LibraryRefreshResult()
        repo = self._require_repository()
        seen_media_ids: set[int] = set()
        scanned_any_base = False

        for root in repo.list_all():
            root_path = Path(root.path).resolve(strict=False)
            if not root_path.is_dir():
                continue

            # Cilja poznate baze serija umesto celog diska (izbegava
            # sistemske foldere i nepotrebno skeniranje filmova).
            bases = [
                root_path / "Strano" / "Serije",
                root_path / "Animirano" / "Serije",
                root_path / "Domace" / "Serije",
                # Stare lokacije (pre migracije strukture) — tolerancija.
                root_path / "Serije",
                root_path / "Domaci" / "Serije",
            ]
            scan_bases = [base for base in bases if base.is_dir()]
            if not scan_bases:
                scan_bases = [root_path]

            for base in scan_bases:
                scanned_any_base = True
                for scan in scan_series_library(base):
                    if not any(season.episodes for season in scan.seasons):
                        continue
                    result.scanned_series += 1
                    try:
                        media_id = self._refresh_single_series(
                            scan, root_path, result
                        )
                        if media_id is not None:
                            seen_media_ids.add(media_id)
                    except Exception:  # noqa: BLE001
                        result.errors += 1

        # Izvori filmova (video + prevodi) — DB-vođeno, nezavisno od korena.
        try:
            self._refresh_movies(result)
        except Exception:  # noqa: BLE001
            result.errors += 1

        # Prune: serije koje su u bazi ali ih više nema na disku (npr.
        # premešten/preimenovan folder) se uklanjaju. Samo ako je bar jedna
        # biblioteka uspešno skenirana — da se ne brišu serije sa offline
        # diska.
        if scanned_any_base and result.scanned_series > 0:
            for media in self._media_repository.list_all():
                if (
                    media.media_type is MediaType.SERIES
                    and media.id not in seen_media_ids
                ) and self._media_repository.delete(media.id):
                    result.removed_series += 1

        return result

    def refresh_media(self, media_id: int) -> LibraryRefreshResult:
        """Osvežava samo folder jedne serije (dugme na stranici detalja)."""

        result = LibraryRefreshResult()
        media = self._media_repository.get_by_id(media_id)

        if media is None:
            return result

        repo = self._require_repository()

        # Film: registruje/azurira izvor (video + prevodi) iz njegovog foldera.
        if media.media_type is MediaType.MOVIE:
            try:
                self._refresh_movies(result, media_id)
            except Exception:  # noqa: BLE001
                result.errors += 1
            return result

        wanted = _title_identity(media.title)

        for root in repo.list_all():
            root_path = Path(root.path).resolve(strict=False)
            if not root_path.is_dir():
                continue

            bases = [
                root_path / "Strano" / "Serije",
                root_path / "Animirano" / "Serije",
                root_path / "Domace" / "Serije",
                # Stare lokacije (pre migracije strukture) — tolerancija.
                root_path / "Serije",
                root_path / "Domaci" / "Serije",
            ]
            scan_bases = [base for base in bases if base.is_dir()] or [
                root_path
            ]

            for base in scan_bases:
                for scan in scan_series_library(base):
                    if _title_identity(scan.title) != wanted:
                        continue
                    if not any(
                        season.episodes for season in scan.seasons
                    ):
                        continue
                    result.scanned_series += 1
                    try:
                        self._refresh_single_series(scan, root_path, result)
                    except Exception:  # noqa: BLE001
                        result.errors += 1
                    return result

        return result

    def _refresh_single_series(
        self,
        scan: SeriesScanResult,
        root_path: Path,
        result: LibraryRefreshResult,
    ) -> int | None:
        """Osvežava jednu seriju iz biblioteke (u mestu). Vraća media ID."""

        content_mode = _infer_content_mode(scan.directory, root_path)

        media, created = self._resolve_series(
            scan.title, None, content_mode, False
        )
        if created:
            result.new_series += 1

        # Nove sezone/epizode (idempotentno preko ensure).
        for season in scan.seasons:
            existing_season = self._season_repository.get_by_number(
                media.id, season.season_number
            )
            db_season = self._season_repository.ensure(
                media.id, season.season_number, name=season.name
            )
            if existing_season is None:
                result.seasons_added += 1

            for episode in season.episodes:
                existed = (
                    self._episode_repository.get_by_number(
                        db_season.id, episode.episode_number
                    )
                    if hasattr(self._episode_repository, "get_by_number")
                    else None
                )
                self._episode_repository.ensure(
                    db_season.id,
                    episode.episode_number,
                    title=episode.title,
                )
                if existed is None:
                    result.episodes_added += 1

        # Slike (serija + po sezoni) iz lokalnih fajlova.
        if self._asset_service is not None:
            sync = apply_series_artwork(
                scan.directory,
                media.id,
                asset_service=self._asset_service,
                season_repository=self._season_repository,
                media_repository=self._media_repository,
            )
            result.posters_added += int(sync.media_poster)
            result.backdrops_added += int(sync.media_backdrop)
            result.season_posters_added += sync.season_posters
            result.season_backdrops_added += sync.season_backdrops

        # Video/prevodi epizoda (za sličice i reprodukciju).
        self._register_series_source(scan, media.id)

        # Persistentne .thumb sličice svih epizoda — best-effort (ne ruši uvoz).
        for _season in scan.seasons:
            for _episode in _season.episodes:
                _ensure_thumb_safe(_episode.video_path)

        # Regeneracija filmium_info.json ako nedostaje.
        manifest_path = scan.directory / FILMIUM_INFO_FILE_NAME
        if not manifest_path.is_file():
            refreshed = self._media_repository.get_by_id(media.id) or media
            self._write_series_manifest(scan.directory, scan, refreshed)
            result.manifests_written += 1

        return media.id
