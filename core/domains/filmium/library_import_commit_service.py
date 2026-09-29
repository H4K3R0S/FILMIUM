from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import datetime
from pathlib import Path
from typing import Protocol

from core.domains.filmium import tmdb_client
from core.domains.filmium.artwork_models import MediaArtwork
from core.domains.filmium.asset_service import MediaAssetType
from core.domains.filmium.library_category import movie_base_parts
from core.domains.filmium.library_executor import (
    FilmiumOrganizationExecutionError,
    execute_media_organization,
)
from core.domains.filmium.library_import_commit_helpers import (
    _build_media_create_payload,
    _delete_asset_safe,
)
from core.domains.filmium.library_import_models import (
    ImportMatchStatus,
    MediaImportPreview,
)
from core.domains.filmium.library_import_service import (
    LibraryImportPreviewError,
    LibraryImportRootNotFoundError,
    LibraryImportService,
)
from core.domains.filmium.library_manifest import FILMIUM_INFO_FILE_NAME
from core.domains.filmium.library_models import (
    FilmiumInfoManifest,
    MediaFileRole,
    MediaFileStatus,
    MediaFolderScanResult,
)
from core.domains.filmium.library_organizer import (
    FilmiumOrganizationPlanError,
    canonical_target_directory,
    plan_media_organization,
    prune_empty_directories,
)
from core.domains.filmium.library_root_repository import (
    LibraryRootRepository,
)
from core.domains.filmium.library_scanner import (
    FilmiumLibraryScanError,
    scan_media_directory,
)
from core.domains.filmium.media_source_models import (
    MediaFile,
    MediaFileCreate,
    MediaSource,
    MediaSourceCreate,
)
from core.domains.filmium.media_source_service import MediaSourceService
from core.domains.filmium.models import (
    MediaItem,
    MediaType,
)
from core.domains.filmium.repository import MediaRepository

# ==========          REZULTAT POTVRDJENOG UVOZA          ==========

@dataclass(frozen=True)
class MediaImportCommitResult:
    """Rezultat kompletno registrovanog FILMIUM uvoza."""

    media: MediaItem
    source: MediaSource
    artworks: tuple[MediaArtwork, ...]
    created_media: bool
    created_source: bool
    moved_file_count: int
    created_directory_count: int


# ==========          GRESKE POTVRDJENOG UVOZA          ==========

class LibraryImportCommitError(RuntimeError):
    """Oznacava odbijen ili nepotpuno registrovan uvoz."""


# ==========          ARTWORK SYNC UGOVOR          ==========

class ArtworkManifestSynchronizer(Protocol):
    """Minimalni ugovor potreban confirmed import servisu."""

    def sync_source_manifest(
        self,
        source: MediaSource,
        manifest: FilmiumInfoManifest,
    ) -> tuple[MediaArtwork, ...]:
        """Sinhronizuje slike jednog registrovanog izvora."""


# ==========          KATALOG VIZUELNI ASSETI          ==========

class CatalogVisualSynchronizer(Protocol):
    """Minimalni ugovor za GUI kopije primarnog postera i backdropa."""

    def save_media_asset(
        self,
        item_id: int,
        asset_type: MediaAssetType,
        content: bytes,
    ) -> MediaItem:
        """Čuva kontrolisanu GUI kopiju slike i ažurira katalog."""

    def delete_media_asset(
        self,
        item_id: int,
        asset_type: MediaAssetType,
    ) -> MediaItem:
        """Uklanja kontrolisanu GUI kopiju slike."""


# ==========          CONFIRMED IMPORT SERVICE          ==========

def _resolve_existing_media(media_repository, selected_id: int,
                            scan: MediaFolderScanResult):
    """Učitaj i proveri postojeći kataloški zapis (tip/godina moraju da se
    slažu sa skenom). Diže LibraryImportCommitError na neslaganje."""

    media = media_repository.get_by_id(selected_id)

    if media is None:
        raise LibraryImportCommitError(
            f"Izabrani FILMIUM sadrzaj sa ID-em {selected_id} "
            "vise ne postoji."
        )

    if media.media_type is not scan.manifest.media_type:
        raise LibraryImportCommitError(
            "Izabrani kataloski zapis ima drugi tip sadrzaja."
        )

    if (
        media.release_year is not None
        and scan.release_year is not None
        and media.release_year != scan.release_year
    ):
        raise LibraryImportCommitError(
            "Izabrani kataloski zapis ima drugu godinu izdanja."
        )

    return media


class LibraryImportCommitService:
    """Koordinise potvrdu, filesystem, katalog, izvor i slike."""

    def __init__(
        self,
        preview_service: LibraryImportService,
        root_repository: LibraryRootRepository,
        media_repository: MediaRepository,
        media_source_service: MediaSourceService,
        artwork_sync_service: ArtworkManifestSynchronizer,
        media_visual_service: CatalogVisualSynchronizer | None = None,
    ) -> None:
        self._preview_service = preview_service
        self._root_repository = root_repository
        self._media_repository = media_repository
        self._media_source_service = media_source_service
        self._artwork_sync_service = artwork_sync_service
        self._media_visual_service = media_visual_service

    def confirm_import(
        self,
        library_root_id: int,
        relative_directory: str,
        *,
        confirmed: bool = False,
        target_media_id: int | None = None,
        target_library_root_id: int | None = None,
        override_title: str | None = None,
        override_release_year: int | None = None,
        override_genres: tuple[str, ...] | None = None,
        on_progress: Callable[[int, int, int, int], None] | None = None,
        conflict_mode: str = "fail",
        content_mode: str = "regular",
        synchronized: bool = False,
    ) -> MediaImportCommitResult:
        """Izvrsava prethodno pregledan uvoz samo uz jasnu potvrdu.

        ``conflict_mode``: ``"fail"`` (podrazumevano), ``"skip"`` (dodaj samo
        nove fajlove) ili ``"overwrite"`` (prepiši postojeće).
        ``content_mode``: ``"regular"`` (standardna kategorija),
        ``"animated"`` (<koren>/Animirano/Filmovi) ili ``"domestic"``
        (<koren>/Domaci/Filmovi).
        """

        if not confirmed:
            raise LibraryImportCommitError(
                "Uvoz nije eksplicitno potvrdjen."
            )

        try:
            preview = self._preview_service.preview_import(
                library_root_id,
                relative_directory,
            )
        except (
            LibraryImportPreviewError,
            LibraryImportRootNotFoundError,
        ) as error:
            raise LibraryImportCommitError(str(error)) from error

        self._validate_preview(preview, target_media_id)
        root = self._root_repository.get(library_root_id)

        if root is None:
            raise LibraryImportCommitError(
                "Registrovana FILMIUM biblioteka vise ne postoji."
            )

        target_root = root

        if (
            target_library_root_id is not None
            and target_library_root_id != library_root_id
        ):
            target_root = self._root_repository.get(target_library_root_id)

            if target_root is None:
                raise LibraryImportCommitError(
                    "Izabrana ciljna FILMIUM biblioteka ne postoji."
                )

        root_path = Path(root.path)
        target_root_path = Path(target_root.path)
        source_directory = (
            root_path
            if preview.relative_directory == "."
            else root_path.joinpath(
                *Path(preview.relative_directory).parts
            )
        )

        # Film iz „kolekcije": relativna putanja pokazuje na VIDEO fajl →
        # skeniraj SAMO taj film (roditeljski folder + video_reference), da se
        # ostali filmovi u istom folderu ne pipnu.
        video_reference: str | None = None
        if source_directory.is_file():
            video_reference = source_directory.name
            source_directory = source_directory.parent

        try:
            initial_scan = scan_media_directory(
                source_directory, video_reference
            )

            # Rutiranje u kategorijski folder ispod korena ciljne biblioteke:
            # svaki potvrđen uvoz ide u <koren>/<kategorija>/Filmovi/<Naslov (Godina)>
            # (regular=Strano, domestic=Domace, animated=Animirano).
            category_parts = movie_base_parts(content_mode)
            organization_root = target_root_path.joinpath(*category_parts)
            organization_root.mkdir(parents=True, exist_ok=True)
            plan_target = None

            # Postojeći ciljni folder iz ranijih testova može imati samo
            # prazne poddirektorijume (npr. „ostalo"). Oni ne smeju da
            # blokiraju uvoz — uklanjamo praznu hijerarhiju pre plana.
            # Folder sa stvarnim fajlovima ostaje (to je slučaj duplikata).
            prune_empty_directories(
                canonical_target_directory(initial_scan, organization_root)
            )

            plan = plan_media_organization(
                initial_scan,
                organization_root,
                target_directory=plan_target,
            )

            # Kategorija (Film/Anime/Domaći) ide u filmium_info.json da bi
            # biblioteka znala gde sadržaj pripada. Toggle Titlovano/SINH se
            # NE upisuje u manifest.
            plan = replace(
                plan,
                manifest=replace(
                    plan.manifest, content_category=content_mode
                ),
            )

            if not plan.can_apply:
                raise LibraryImportCommitError(
                    "Plan organizacije ima blokirajuce upozorenje: "
                    + "; ".join(plan.warnings)
                )

            execution = execute_media_organization(
                plan,
                confirmed=True,
                on_progress=on_progress,
                conflict_mode=conflict_mode,
            )
            final_scan = scan_media_directory(
                execution.target_directory
            )
        except (
            FilmiumLibraryScanError,
            FilmiumOrganizationPlanError,
            FilmiumOrganizationExecutionError,
            OSError,
        ) as error:
            raise LibraryImportCommitError(str(error)) from error

        media: MediaItem | None = None
        source: MediaSource | None = None
        previous_source: MediaSource | None = None
        created_media = False
        created_source = False

        try:
            media, created_media = self._resolve_media(
                preview.match_status,
                preview.matching_media_ids,
                target_media_id,
                final_scan,
                preview.genres,
                override_title=override_title,
                override_release_year=override_release_year,
                override_genres=override_genres,
                content_mode=content_mode,
                synchronized=synchronized,
            )
            relative_target = execution.target_directory.relative_to(
                target_root_path
            ).as_posix()
            files = self._source_files(final_scan)
            previous_source = self._find_existing_source(
                media.id,
                target_root.id,
                relative_target,
            )

            if previous_source is None:
                source = self._media_source_service.create_media_source(
                    MediaSourceCreate(
                        media_id=media.id,
                        library_root_id=target_root.id,
                        root_path_snapshot=str(target_root_path),
                        relative_directory=relative_target,
                        manifest_path=FILMIUM_INFO_FILE_NAME,
                        files=files,
                    )
                )
                created_source = True
            else:
                source = self._media_source_service.replace_media_files(
                    previous_source.id,
                    files,
                )
                source = (
                    self._media_source_service
                    .set_media_source_availability(
                        source.id,
                        MediaFileStatus.AVAILABLE,
                    )
                )

            artworks = self._artwork_sync_service.sync_source_manifest(
                source,
                final_scan.manifest,
            )
            media = self._sync_catalog_visual_assets(
                media,
                final_scan,
            )
        except Exception as error:
            self._compensate_database(
                media,
                source,
                previous_source,
                created_media,
                created_source,
            )
            raise LibraryImportCommitError(
                "Fajlovi su bezbedno organizovani, ali registracija u "
                "FILMIUM bazi nije uspela. Uvoz moze ponovo da se pokrene: "
                f"{error}"
            ) from error

        # Persistentne sličice (.thumb) za sve video fajlove — best-effort (ne ruši commit).
        self._generate_library_thumbnails(final_scan)

        return MediaImportCommitResult(
            media=media,
            source=source,
            artworks=artworks,
            created_media=created_media,
            created_source=created_source,
            moved_file_count=execution.moved_file_count,
            created_directory_count=execution.created_directory_count,
        )

    def _sync_catalog_visual_assets(
        self,
        media: MediaItem,
        scan: MediaFolderScanResult,
    ) -> MediaItem:
        """
        Pravi male managed kopije primarnih slika za postojeći GUI API.

        Originali ostaju u folderu filma i artwork registru. Kopiraju se
        samo poster i backdrop, nikada video, trailer, wallpaper ili fanart.
        Ručno postavljene managed slike imaju prednost i ne prepisuju se.
        """

        if self._media_visual_service is None:
            return media

        visual_references = (
            (
                MediaAssetType.POSTER,
                media.poster_path,
                scan.manifest.files.poster,
            ),
            (
                MediaAssetType.BACKDROP,
                media.backdrop_path,
                scan.manifest.files.backdrop,
            ),
        )
        updated_media = media
        saved_types: list[MediaAssetType] = []

        try:
            for asset_type, current_path, source_reference in (
                visual_references
            ):
                if current_path is not None:
                    continue

                source_path = None

                if source_reference is not None:
                    candidate = scan.directory.joinpath(
                        *source_reference.split("/")
                    )
                    if candidate.is_file():
                        source_path = candidate

                # Fallback: manifest ne navodi sliku, ali ona stoji pored filma
                # (npr. „Naslov (Godina) - poster.jpg"). Keširaj i tada, da
                # svaki uvezen film odmah dobije malu keš sliku za prikaz.
                if source_path is None:
                    suffix = (
                        "poster"
                        if asset_type is MediaAssetType.POSTER
                        else "backdrop"
                    )
                    for pattern in (
                        f"* - {suffix}.*",
                        f"*-{suffix}.*",
                        f"*{suffix}.*",
                    ):
                        matches = sorted(
                            path
                            for path in scan.directory.glob(pattern)
                            if path.is_file()
                        )
                        if matches:
                            source_path = matches[0]
                            break

                if source_path is None:
                    continue

                updated_media = (
                    self._media_visual_service.save_media_asset(
                        item_id=media.id,
                        asset_type=asset_type,
                        content=source_path.read_bytes(),
                    )
                )
                saved_types.append(asset_type)
        except Exception:
            # Uklanja samo managed kopije napravljene u ovom pokušaju.
            for saved_type in reversed(saved_types):
                _delete_asset_safe(
                    self._media_visual_service, media.id, saved_type
                )

            raise

        return updated_media

    @staticmethod
    def _validate_preview(
        preview: MediaImportPreview,
        target_media_id: int | None,
    ) -> None:
        if preview.unrecognized_genres:
            raise LibraryImportCommitError(
                "Pre potvrde ukloni nepoznate zanrove: "
                + ", ".join(preview.unrecognized_genres)
            )

        if preview.match_status is ImportMatchStatus.AMBIGUOUS:
            if target_media_id not in preview.matching_media_ids:
                raise LibraryImportCommitError(
                    "Izaberi jedan od ponudjenih kataloskih zapisa."
                )

            blockers = tuple(
                warning
                for warning in preview.blocking_warnings
                if "vise mogucih podudaranja" not in warning.casefold()
            )
        else:
            blockers = preview.blocking_warnings

        if (
            preview.match_status is ImportMatchStatus.EXISTING
            and target_media_id is not None
            and target_media_id not in preview.matching_media_ids
        ):
            raise LibraryImportCommitError(
                "Izabrani zapis nije podudaranje ponudjeno u preview-u."
            )

        if blockers:
            raise LibraryImportCommitError(
                "Uvoz ima blokirajuce upozorenje: "
                + "; ".join(blockers)
            )

    @staticmethod
    def _generate_library_thumbnails(scan) -> None:
        """Best-effort: persistentne .thumb sličice za sve video fajlove (film + epizode).
        Nikad ne ruši commit — sličice su opcione (ffmpeg fali/greška → preskoči)."""
        try:
            from core.domains.filmium.media_thumbnail import ensure_thumbnail
            for file in scan.detected_files:
                if file.role is MediaFileRole.VIDEO:
                    try:
                        ensure_thumbnail(file.path)
                    except Exception:  # noqa: BLE001, S110
                        pass
        except Exception:  # noqa: BLE001, S110
            pass

    def _resolve_media(
        self,
        match_status: ImportMatchStatus,
        matching_media_ids: tuple[int, ...],
        target_media_id: int | None,
        scan: MediaFolderScanResult,
        genres: tuple[str, ...],
        *,
        override_title: str | None = None,
        override_release_year: int | None = None,
        override_genres: tuple[str, ...] | None = None,
        content_mode: str = "regular",
        synchronized: bool = False,
    ) -> tuple[MediaItem, bool]:
        selected_id = target_media_id

        if selected_id is None and match_status is ImportMatchStatus.EXISTING:
            selected_id = matching_media_ids[0]

        if selected_id is not None:
            return _resolve_existing_media(
                self._media_repository, selected_id, scan
            ), False

        manifest = scan.manifest
        effective_title = override_title or manifest.title
        effective_release_year = (
            override_release_year
            if override_release_year is not None
            else manifest.release_year
        )
        effective_genres = (
            override_genres
            if override_genres is not None
            else genres
        )

        # TMDB provera/dopuna: izvorni + engleski naslov/opis, glumci,
        # keywords, kolekcija. Lokalni `title` (folder/override) i žanrovi
        # ostaju netaknuti; TMDB samo puni prazna polja. Commit-gate: ako
        # ima konekcije čeka pun TMDB (sinhrono), bez konekcije nastavlja
        # sa trenutnim podacima (offline). Radi i za filmove i za serije.
        enrichment = self._enrich_for_commit(
            manifest.media_type,
            effective_title,
            effective_release_year,
        )

        payload = _build_media_create_payload(
            manifest, enrichment, effective_title, effective_release_year,
            effective_genres, content_mode, synchronized,
        )
        return self._media_repository.create(payload), True


    @staticmethod
    def _enrich_for_commit(
        media_type: MediaType,
        title: str,
        release_year: int | None,
    ):
        """Commit-gate TMDB dopuna: čeka pun TMDB ako ima konekcije.

        Sinhron poziv (blokira dok se ne učita). Bez konekcije ili bez
        podudaranja vraća ``None`` i uvoz nastavlja sa trenutnim podacima
        (offline fallback). Serija → ``enrich_series``, film → ``enrich_movie``.
        """

        if not tmdb_client.is_tmdb_available():
            return None

        if media_type is MediaType.SERIES:
            return tmdb_client.enrich_series(title, release_year)

        return tmdb_client.enrich_movie(title, release_year)

    @staticmethod
    def _source_files(
        scan: MediaFolderScanResult,
    ) -> tuple[MediaFileCreate, ...]:
        items: list[MediaFileCreate] = []
        subtitle_languages = {
            subtitle.path.casefold(): subtitle.language
            for subtitle in scan.manifest.files.subtitles
        }

        for file in scan.detected_files:
            modified_at = datetime.fromtimestamp(  # noqa: DTZ006
                file.path.stat().st_mtime
            )
            relative_path = file.path.relative_to(
                scan.directory
            ).as_posix()
            language = file.language

            # Završni manifest je autoritativan za jezik prevoda.
            # Naziv fajla je samo pomoćna metoda prepoznavanja i ne
            # sme da poništi već sačuvanu oznaku poput "und".
            if (
                file.role is MediaFileRole.SUBTITLE
                and language is None
            ):
                language = subtitle_languages.get(
                    relative_path.casefold(),
                    "und",
                )

            items.append(
                MediaFileCreate(
                    role=file.role,
                    relative_path=relative_path,
                    language=language,
                    size_bytes=file.size_bytes,
                    modified_at=modified_at,
                )
            )

        return tuple(items)

    def _find_existing_source(
        self,
        media_id: int,
        library_root_id: int,
        relative_directory: str,
    ) -> MediaSource | None:
        wanted = relative_directory.casefold()

        for source in self._media_source_service.list_media_sources(
            media_id
        ):
            if (
                source.library_root_id == library_root_id
                and source.relative_directory.casefold() == wanted
            ):
                return source

        return None

    def _compensate_database(
        self,
        media: MediaItem | None,
        source: MediaSource | None,
        previous_source: MediaSource | None,
        created_media: bool,
        created_source: bool,
    ) -> None:
        """Vraca samo DB promene; organizovane datoteke se ne rizikuju."""

        try:
            if created_source and source is not None:
                self._media_source_service.delete_media_source(source.id)
            elif previous_source is not None:
                self._media_source_service.replace_media_files(
                    previous_source.id,
                    tuple(
                        self._file_create(item)
                        for item in previous_source.files
                    ),
                )
                self._media_source_service.set_media_source_availability(
                    previous_source.id,
                    previous_source.availability_status,
                )
        except Exception:  # noqa: BLE001, S110
            # Originalna greska ostaje autoritativna za pozivaoca.
            pass

        if created_media and media is not None:
            try:
                self._media_repository.delete(media.id)
            except Exception:  # noqa: BLE001, S110
                pass

    @staticmethod
    def _file_create(item: MediaFile) -> MediaFileCreate:
        return MediaFileCreate(
            role=item.role,
            relative_path=item.relative_path,
            language=item.language,
            size_bytes=item.size_bytes,
            modified_at=item.modified_at,
            file_status=item.file_status,
        )
