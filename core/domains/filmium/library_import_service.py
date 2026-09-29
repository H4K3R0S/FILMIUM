import re
import shutil
from pathlib import Path, PurePosixPath

from core.domains.filmium import tmdb_client
from core.domains.filmium.duplicate_compare import (
    DuplicateComparison,
    compare_directories,
)
from core.domains.filmium.library_category import movie_category_parts
from core.domains.filmium.library_import_models import (
    ImportMatchStatus,
    ImportPreviewAction,
    ImportPreviewFile,
    MediaImportPreview,
    MediaTechnicalInfo,
)
from core.domains.filmium.library_manifest import (
    FilmiumManifestError,
    normalize_manifest_path,
)
from core.domains.filmium.library_models import (
    MediaFileRole,
    MediaFolderScanResult,
)
from core.domains.filmium.library_organizer import (
    FilmiumOrganizationPlanError,
    canonical_target_directory,
    plan_media_organization,
)
from core.domains.filmium.library_root_repository import (
    LibraryRootRepository,
)
from core.domains.filmium.library_scanner import (
    VIDEO_EXTENSIONS,
    FilmiumLibraryScanError,
    scan_media_directory,
)
from core.domains.filmium.media_probe import probe_video_file
from core.domains.filmium.models import MediaItem, MediaType
from core.domains.filmium.repository import MediaRepository

# ==========          GRESKE IMPORT PREVIEW-A          ==========

class LibraryImportPreviewError(ValueError):
    """Oznacava kandidata koji nije moguce bezbedno pregledati."""


class LibraryImportRootNotFoundError(LookupError):
    """Oznacava da trazena registrovana biblioteka ne postoji."""


# ==========          IMPORT PREVIEW SERVICE          ==========

def _scan_and_plan(scan_dir: Path, video_reference, root_path: Path,
                   normalized_directory: str):
    """Skeniraj folder + napravi plan organizacije. Greške skena/plana/OS →
    LibraryImportPreviewError. Vraća (scan_result, organization_plan)."""

    try:
        scan_result = scan_media_directory(scan_dir, video_reference)
        organization_root = (
            root_path
            if normalized_directory == "."
            else scan_dir.parent
        )
        organization_plan = plan_media_organization(
            scan_result,
            organization_root,
            target_directory=(
                root_path
                if normalized_directory == "."
                else None
            ),
        )
    except (
        FilmiumLibraryScanError,
        FilmiumOrganizationPlanError,
        OSError,
    ) as error:
        raise LibraryImportPreviewError(str(error)) from error
    return scan_result, organization_plan


def _preview_description_year(scan_result, enrichment, movie_tmdb):
    """Opis i godina: lokalni podaci imaju prednost, pa TMDB dopuna. Vraća
    (description, release_year)."""

    description = (
        scan_result.manifest.description
        or (enrichment.local_overview if enrichment else None)
        or (enrichment.english_overview if enrichment else None)
        or (movie_tmdb.overview if movie_tmdb else None)
    )
    release_year = (
        scan_result.release_year
        or (enrichment.year if enrichment else None)
        or (movie_tmdb.year if movie_tmdb else None)
    )
    return description, release_year


def _preview_warnings(organization_plan, unknown_genres, match_status):
    """Sklopi upozorenja (meka + blokirajuća). Vraća (warnings, blocking)."""

    # Meka upozorenja (fajl već na odredištu pri re-skenu) prikazuju se,
    # ali NE ulaze u blocking_warnings — uvoz može da se potvrdi i sadržaj
    # se svejedno registruje u bazu.
    warnings = list(organization_plan.warnings) + list(
        organization_plan.soft_warnings
    )
    blocking_warnings = list(organization_plan.warnings)

    if unknown_genres:
        warnings.append(
            "Manifest sadrzi zanrove koji nisu aktivni u FILMIUM-u: "
            + ", ".join(unknown_genres)
        )

    if match_status is ImportMatchStatus.AMBIGUOUS:
        duplicate_warning = (
            "Pronadjeno je vise mogucih podudaranja u katalogu."
        )
        warnings.append(duplicate_warning)
        blocking_warnings.append(duplicate_warning)
    return warnings, blocking_warnings


def _build_import_preview(*, root, normalized_directory, scan_result, description,
                          release_year, active_genres, unknown_genres,
                          match_status, matches, organization_plan, warnings,
                          blocking_warnings, technical, suggested_genres,
                          enrichment, root_path, relative_display):
    """Sastavi MediaImportPreview iz izračunatih delova (čista gradnja)."""

    return MediaImportPreview(
        library_root_id=root.id,
        relative_directory=normalized_directory,
        title=scan_result.title,
        original_title=scan_result.manifest.original_title,
        media_type=scan_result.manifest.media_type,
        release_year=release_year,
        runtime_minutes=scan_result.manifest.runtime_minutes,
        description=description,
        genres=active_genres,
        unrecognized_genres=unknown_genres,
        studio=scan_result.manifest.studio,
        franchise=scan_result.manifest.franchise,
        franchise_order=scan_result.manifest.franchise_order,
        ownership_status=scan_result.manifest.ownership_status,
        match_status=match_status,
        matching_media_ids=tuple(item.id for item in matches),
        planned_target_directory=relative_display(
            organization_plan.target_directory,
            root_path,
        ),
        detected_files=tuple(
            ImportPreviewFile(
                relative_path=file.path.relative_to(
                    scan_result.directory
                ).as_posix(),
                role=file.role,
                size_bytes=file.size_bytes,
                language=file.language,
            )
            for file in scan_result.detected_files
        ),
        actions=tuple(
            ImportPreviewAction(
                action_type=action.action_type.value,
                source=(
                    None
                    if action.source is None
                    else relative_display(
                        action.source,
                        root_path,
                    )
                ),
                destination=relative_display(
                    action.destination,
                    root_path,
                ),
                reason=action.reason,
            )
            for action in organization_plan.actions
        ),
        warnings=tuple(dict.fromkeys(warnings)),
        blocking_warnings=tuple(
            dict.fromkeys(blocking_warnings)
        ),
        technical=technical,
        suggested_genres=suggested_genres,
        tmdb=enrichment,
    )


class LibraryImportService:
    """Priprema import preview bez upisa i bez izmene filesystema."""

    def __init__(
        self,
        root_repository: LibraryRootRepository,
        media_repository: MediaRepository,
    ) -> None:
        self._root_repository = root_repository
        self._media_repository = media_repository

    def preview_import(
        self,
        root_id: int,
        relative_directory: str,
        *,
        include_tmdb: bool = False,
    ) -> MediaImportPreview:
        """Skenira izabrani folder i pravi plan koji jos nije izvrsen.

        ``include_tmdb`` uključuje punu TMDB dopunu (svi glumci, keywords,
        kolekcija, EN+SR opis) — mrežni, rate-limitovan poziv, zato je van
        podrazumevanog toka i traži ga bulk auto-obogaćivanje na sken.
        """

        root = self._root_repository.get(root_id)

        if root is None:
            raise LibraryImportRootNotFoundError(
                f"FILMIUM biblioteka sa ID-em {root_id} ne postoji."
            )

        if not root.is_enabled:
            raise LibraryImportPreviewError(
                "Iskljucena FILMIUM biblioteka ne moze biti uvezena."
            )

        normalized_directory = self._normalize_directory(
            relative_directory
        )
        root_path = Path(root.path)

        if not root_path.is_dir():
            raise LibraryImportPreviewError(
                "FILMIUM biblioteka trenutno nije dostupna."
            )

        scan_dir, video_reference = self._resolve_scan_target(
            root_path,
            normalized_directory,
        )
        scan_result, organization_plan = _scan_and_plan(
            scan_dir, video_reference, root_path, normalized_directory
        )

        matches = self._find_catalog_matches(scan_result)
        match_status = self._match_status(matches)
        technical = self._probe_main_video(scan_result)
        # TMDB dopuna filma: popunjava SAMO prazan opis/godinu. Žanrove NE
        # dira — FILMIUM ima kuriran (srpski) skup žanrova, a strani TMDB
        # žanrovi bi pali kao „nepoznati" i pokvarili rutiranje. Lokalni
        # podaci uvek imaju prednost.
        # Puna TMDB dopuna (svi glumci/keywords/kolekcija) samo na zahtev;
        # inače jeftin parcijalni match filma za prazan opis/godinu.
        enrichment = (
            self._enrich_full(scan_result) if include_tmdb else None
        )
        movie_tmdb = (
            None if include_tmdb
            else self._match_movie_if_needed(scan_result)
        )
        description, release_year = _preview_description_year(
            scan_result, enrichment, movie_tmdb
        )

        active_genres, unknown_genres = self._resolve_genres(
            scan_result.manifest.genres
        )
        suggested_genres = self._suggest_genres(
            scan_result,
            active_genres,
        )
        warnings, blocking_warnings = _preview_warnings(
            organization_plan, unknown_genres, match_status
        )

        return _build_import_preview(
            root=root,
            normalized_directory=normalized_directory,
            scan_result=scan_result,
            description=description,
            release_year=release_year,
            active_genres=active_genres,
            unknown_genres=unknown_genres,
            match_status=match_status,
            matches=matches,
            organization_plan=organization_plan,
            warnings=warnings,
            blocking_warnings=blocking_warnings,
            technical=technical,
            suggested_genres=suggested_genres,
            enrichment=enrichment,
            root_path=root_path,
            relative_display=self._relative_display,
        )


    @staticmethod
    def _enrich_full(scan_result):
        """Puna TMDB dopuna kandidata (film ili serija). Tolerantno.

        Vraća ``MediaTitleEnrichment`` sa svim poljima ili ``None`` ako
        TMDB nije dostupan / nema podudaranja.
        """

        if not tmdb_client.is_tmdb_available():
            return None

        title = scan_result.title
        year = scan_result.release_year

        if scan_result.manifest.media_type is MediaType.SERIES:
            return tmdb_client.enrich_series(title, year)

        return tmdb_client.enrich_movie(title, year)

    @staticmethod
    def _probe_main_video(
        scan_result: MediaFolderScanResult,
    ) -> MediaTechnicalInfo | None:
        """Čita tehničke podatke glavnog videa ako je alat dostupan."""

        video_file = next(
            (
                file
                for file in scan_result.detected_files
                if file.role is MediaFileRole.VIDEO
            ),
            None,
        )

        if video_file is None:
            return None

        return probe_video_file(video_file.path)

    @staticmethod
    def _normalize_directory(value: str) -> str:
        normalized_input = value.strip().replace("\\", "/")

        if normalized_input in {"", ".", "./"}:
            return "."

        try:
            normalized = normalize_manifest_path(
                normalized_input,
                "relative_directory",
            )
        except FilmiumManifestError as error:
            raise LibraryImportPreviewError(str(error)) from error

        if not PurePosixPath(normalized).parts:
            raise LibraryImportPreviewError(
                "Folder za import preview nije izabran."
            )

        return normalized

    def _resolve_scan_target(
        self,
        root_path: Path,
        normalized_directory: str,
    ) -> tuple[Path, str | None]:
        """
        Vraća (folder_za_skeniranje, video_reference).

        Ako relativna putanja pokazuje na VIDEO fajl (film iz „kolekcije"),
        skenira se roditeljski folder samo za taj film. Inače je to običan
        folder (``video_reference=None``).
        """

        candidate = self._candidate_path(root_path, normalized_directory)

        if (
            candidate.is_file()
            and candidate.suffix.casefold() in VIDEO_EXTENSIONS
        ):
            parent = candidate.parent
            try:
                parent.resolve(strict=False).relative_to(
                    root_path.resolve(strict=False)
                )
            except ValueError as error:
                raise LibraryImportPreviewError(
                    "Izabrani fajl izlazi iz registrovane biblioteke."
                ) from error
            return parent, candidate.name

        self._verify_candidate_path(candidate, root_path)
        return candidate, None

    @staticmethod
    def _candidate_path(
        root_path: Path,
        normalized_directory: str,
    ) -> Path:
        if normalized_directory == ".":
            return root_path

        return root_path.joinpath(
            *PurePosixPath(normalized_directory).parts
        )

    @staticmethod
    def _verify_candidate_path(
        candidate: Path,
        root_path: Path,
    ) -> None:
        try:
            candidate.resolve(strict=False).relative_to(
                root_path.resolve(strict=False)
            )
        except ValueError as error:
            raise LibraryImportPreviewError(
                "Izabrani folder izlazi iz registrovane biblioteke."
            ) from error

        if candidate.is_symlink():
            raise LibraryImportPreviewError(
                "Simbolicka veza ne moze biti kandidat za uvoz."
            )

        if not candidate.is_dir():
            raise LibraryImportPreviewError(
                f"Folder za uvoz ne postoji: {candidate.name}"
            )

    def compare_duplicate(
        self,
        root_id: int,
        relative_directory: str,
    ) -> DuplicateComparison:
        """
        Poredi skenirani folder sa postojećim kanonskim ciljnim folderom
        (duplikat detekcija: identično/slično/novo po fajlu).
        """

        root = self._root_repository.get(root_id)
        if root is None:
            raise LibraryImportRootNotFoundError(
                "Registrovana FILMIUM biblioteka ne postoji."
            )

        root_path = Path(root.path)
        normalized = self._normalize_directory(relative_directory)
        source, video_reference = self._resolve_scan_target(
            root_path, normalized
        )

        try:
            scan = scan_media_directory(source, video_reference)
        except FilmiumLibraryScanError as error:
            raise LibraryImportPreviewError(str(error)) from error

        # Ciljna biblioteka: glavni disk ako postoji, inače isti koren.
        target_root = next(
            (item for item in self._root_repository.list_all() if item.is_main),
            root,
        )
        category = movie_category_parts(scan.manifest.genres)
        organization_root = Path(target_root.path).joinpath(*category)
        target = canonical_target_directory(scan, organization_root)

        return compare_directories(source, target)

    def delete_source_directory(
        self,
        root_id: int,
        relative_directory: str,
    ) -> None:
        """
        Trajno briše skenirani izvorni folder sa diska (dugme „Uništi").

        Sigurnosne provere: folder mora biti UNUTAR registrovane biblioteke
        i ne sme biti sam koren. Simbolička veza se ne prati.
        """

        root = self._root_repository.get(root_id)
        if root is None:
            raise LibraryImportRootNotFoundError(
                "Registrovana FILMIUM biblioteka ne postoji."
            )

        root_path = Path(root.path)
        normalized = self._normalize_directory(relative_directory)

        if normalized == ".":
            raise LibraryImportPreviewError(
                "Koren biblioteke se ne može uništiti."
            )

        candidate = self._candidate_path(root_path, normalized)

        # Film iz „kolekcije": relativna putanja je VIDEO fajl → obriši samo
        # taj film (video + sidecar istog baznog naziva), ne ceo folder.
        if (
            candidate.is_file()
            and candidate.suffix.casefold() in VIDEO_EXTENSIONS
        ):
            from core.domains.filmium.movie_collection import (
                collection_sidecar_matches,
                parse_collection_entry,
            )

            parent = candidate.parent
            try:
                parent.resolve(strict=False).relative_to(
                    root_path.resolve(strict=False)
                )
            except ValueError as error:
                raise LibraryImportPreviewError(
                    "Izabrani fajl izlazi iz registrovane biblioteke."
                ) from error

            video_stem = candidate.stem
            parsed = parse_collection_entry(video_stem)
            order = parsed[0] if parsed is not None else -1
            for path in list(parent.iterdir()):
                if path.is_file() and collection_sidecar_matches(
                    path, video_stem, parent.name, order
                ):
                    try:
                        path.unlink()
                    except OSError:
                        pass
            return

        self._verify_candidate_path(candidate, root_path)

        if (
            candidate.resolve(strict=False)
            == root_path.resolve(strict=False)
        ):
            raise LibraryImportPreviewError(
                "Koren biblioteke se ne može uništiti."
            )

        try:
            shutil.rmtree(candidate)
        except OSError as error:
            raise LibraryImportPreviewError(
                f"Folder nije moguće uništiti: {error}"
            ) from error

    def _match_movie_if_needed(self, scan_result):
        """
        TMDB detalji filma kada lokalnom manifestu nešto nedostaje.

        Radi samo za filmove i samo ako je bar jedno polje (žanr/opis/
        godina) prazno. Tolerantno: bez TMDB-a vraća ``None``.
        """

        manifest = scan_result.manifest
        if manifest.media_type is not MediaType.MOVIE:
            return None

        needs = (
            not manifest.description
            or scan_result.release_year is None
        )
        if not needs or not tmdb_client.is_tmdb_available():
            return None

        return tmdb_client.match_movie(
            scan_result.title, scan_result.release_year
        )

    def _suggest_genres(
        self,
        scan: MediaFolderScanResult,
        own_genres: tuple[str, ...],
    ) -> tuple[str, ...]:
        """Predlaže žanrove iz postojećih filmova sličnog naslova.

        „Sličan" znači isti prvi značajni token naslova (npr. cela
        „Avengers" franšiza). Predlažu se samo aktivni FILMIUM žanrovi
        kojih kandidat već nema.
        """

        candidate_tokens = self._title_tokens(scan.title)

        if not candidate_tokens or len(candidate_tokens[0]) < 4:
            return ()

        first_token = candidate_tokens[0]
        own_keys = {genre.casefold() for genre in own_genres}
        active_by_key = {
            genre.casefold(): genre
            for genre in self._media_repository.list_active_genres()
        }
        suggested: dict[str, str] = {}

        for item in self._media_repository.list_all():
            item_tokens = self._title_tokens(item.title)

            if not item_tokens or item_tokens[0] != first_token:
                continue

            for genre in item.genres:
                key = genre.casefold()

                if key in own_keys or key not in active_by_key:
                    continue

                suggested.setdefault(key, active_by_key[key])

        return tuple(suggested.values())

    @staticmethod
    def _title_tokens(value: str) -> list[str]:
        """Deli naslov na reči, bez vodećih članova i završne godine."""

        articles = {"the", "a", "an"}
        words = [
            word
            for word in re.split(r"[^a-z0-9]+", value.casefold())
            if word
        ]

        while words and words[0] in articles:
            words.pop(0)

        if words and re.fullmatch(r"\d{4}", words[-1]):
            words.pop()

        return words

    def _find_catalog_matches(
        self,
        result: MediaFolderScanResult,
    ) -> tuple[MediaItem, ...]:
        wanted_titles = {
            self._title_identity(result.title),
        }

        if result.manifest.original_title:
            wanted_titles.add(
                self._title_identity(result.manifest.original_title)
            )

        matches: list[MediaItem] = []

        for item in self._media_repository.list_all():
            if item.media_type is not result.manifest.media_type:
                continue

            item_titles = {
                self._title_identity(item.title),
            }

            if item.original_title:
                item_titles.add(self._title_identity(item.original_title))

            if wanted_titles.isdisjoint(item_titles):
                continue

            if (
                result.release_year is not None
                and item.release_year is not None
                and result.release_year != item.release_year
            ):
                continue

            matches.append(item)

        return tuple(sorted(matches, key=lambda item: item.id))

    def _resolve_genres(
        self,
        genres: tuple[str, ...],
    ) -> tuple[tuple[str, ...], tuple[str, ...]]:
        active_by_key = {
            genre.casefold(): genre
            for genre in self._media_repository.list_active_genres()
        }
        active: dict[str, str] = {}
        unknown: dict[str, str] = {}

        for genre in genres:
            normalized = genre.strip()
            key = normalized.casefold()

            if key in active_by_key:
                canonical = active_by_key[key]
                active.setdefault(canonical.casefold(), canonical)
            elif normalized:
                unknown.setdefault(key, normalized)

        return (
            tuple(active.values()),
            tuple(unknown.values()),
        )

    @staticmethod
    def _match_status(
        matches: tuple[MediaItem, ...],
    ) -> ImportMatchStatus:
        if not matches:
            return ImportMatchStatus.NEW

        if len(matches) == 1:
            return ImportMatchStatus.EXISTING

        return ImportMatchStatus.AMBIGUOUS

    @staticmethod
    def _title_identity(value: str) -> str:
        return "".join(
            character
            for character in value.casefold()
            if character.isalnum()
        )

    @staticmethod
    def _relative_display(path: Path, root_path: Path) -> str:
        try:
            return path.relative_to(root_path).as_posix()
        except ValueError:
            return str(path)
