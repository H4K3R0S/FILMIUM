"""Series import: refresh/register/movie-resolve mixin — izdvojeno radi veličine."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.domains.filmium.series_import_service import LibraryRefreshResult

"""Uvoz serije: organizacija na disku + registracija u FILMIUM katalog."""

from pathlib import Path

from core.domains.filmium import tmdb_client
from core.domains.filmium.library_manifest import (
    FILMIUM_INFO_FILE_NAME,
    FilmiumManifestError,
    write_filmium_manifest,
)
from core.domains.filmium.library_models import (
    EpisodeManifest,
    FilmiumInfoManifest,
    MediaFileRole,
    SeasonManifest,
)
from core.domains.filmium.library_scanner import (
    parse_media_folder_name,
)
from core.domains.filmium.media_finders import (
    find_subtitle_files,
    find_video_files,
    subtitle_language,
)
from core.domains.filmium.media_source_models import (
    MediaFileCreate,
    MediaSourceCreate,
)
from core.domains.filmium.models import (
    MediaItem,
    MediaItemCreate,
    MediaType,
)
from core.domains.filmium.series_import_helpers import (
    SeriesEnrichment,
    _append_extra_subtitles,
    _collect_episode_files,
    _title_identity,
    _upsert_media_source,
)
from core.domains.filmium.series_scanner import (
    _SKIP_DIRECTORIES,
    SeriesScanResult,
)

# ==========          GREŠKE          ==========



class _SeriesRefreshMixin:
    """Metode osvežavanja biblioteke i registracije izvora (koriste
    atribute/metode iz SeriesImportService preko self)."""

    def _refresh_movies(
        self,
        result: LibraryRefreshResult,
        only_media_id: int | None = None,
    ) -> None:
        """Registruje/azurira izvore filmova (video + prevodi).

        DB-vođeno: koristi putanju iz postojećeg media_source zapisa (koji
        upisuje uvoz). Ako film nema izvor, traži folder u bibliotekama po
        naslovu. Bez izvora film nema putanju videa → ne radi reprodukcija.
        """

        if self._media_source_service is None:
            return

        for media in self._media_repository.list_all():
            if media.media_type is not MediaType.MOVIE:
                continue
            if only_media_id is not None and media.id != only_media_id:
                continue
            try:
                self._refresh_one_movie(media, result)
            except Exception:  # noqa: BLE001
                result.errors += 1

    def _refresh_one_movie(
        self,
        media,
        result: LibraryRefreshResult,
    ) -> None:
        """Osvežava izvor jednog filma iz njegovog foldera."""

        located = self._locate_movie_folder(media)
        if located is None:
            return
        folder, root = located

        result.movie_folders_scanned += 1

        root_path = Path(root.path).resolve(strict=False)
        try:
            relative_directory = (
                folder.resolve(strict=False)
                .relative_to(root_path)
                .as_posix()
            )
        except ValueError:
            return

        files = self._movie_files(folder)
        if not any(f.role is MediaFileRole.VIDEO for f in files):
            return

        had_source = self._has_video_source(media.id)
        try:
            existing = self._media_source_service.list_media_sources(
                media.id
            )
            if existing:
                self._media_source_service.replace_media_files(
                    existing[0].id, tuple(files)
                )
            else:
                self._media_source_service.create_media_source(
                    MediaSourceCreate(
                        media_id=media.id,
                        library_root_id=root.id,
                        root_path_snapshot=str(root_path),
                        relative_directory=relative_directory,
                        manifest_path=FILMIUM_INFO_FILE_NAME,
                        files=tuple(files),
                    )
                )
            if not had_source:
                result.movie_sources_added += 1
        except Exception:  # noqa: BLE001, S110
            pass

    def _movie_files(self, folder: Path):
        """Video + prevodi (uklj. pod-foldere subs/titlovi) filma."""

        files: list[MediaFileCreate] = []
        folder = Path(folder)

        for video in find_video_files(folder):
            try:
                rel = Path(video).relative_to(folder).as_posix()
            except ValueError:
                continue
            try:
                size = Path(video).stat().st_size
            except OSError:
                size = 0
            files.append(
                MediaFileCreate(
                    role=MediaFileRole.VIDEO,
                    relative_path=rel,
                    size_bytes=size,
                )
            )

        known = set()
        for sub in find_subtitle_files(folder):
            try:
                rel = Path(sub).relative_to(folder).as_posix()
            except ValueError:
                continue
            if rel in known:
                continue
            known.add(rel)
            files.append(
                MediaFileCreate(
                    role=MediaFileRole.SUBTITLE,
                    relative_path=rel,
                    language=subtitle_language(sub) or "und",
                )
            )

        # Dedup po relativnoj putanji (jedinstveni ključ u bazi izvora).
        deduped: dict[str, MediaFileCreate] = {}
        for entry in files:
            deduped.setdefault(entry.relative_path, entry)
        return list(deduped.values())

    def _locate_movie_folder(self, media):
        """Vraća (folder, root) filma: prvo iz baze, pa pretraga po naslovu.

        Probaju se OBE baze (trenutni root + snapshot iz zapisa) jer se
        ``library_root_id`` i snapshot putanja mogu razlikovati po filmu.
        """

        try:
            sources = self._media_source_service.list_media_sources(media.id)
        except Exception:  # noqa: BLE001
            sources = ()

        for source in sources:
            bases: list[Path] = []
            if self._root_repository is not None and source.library_root_id:
                root = self._root_repository.get(source.library_root_id)
                if root is not None:
                    bases.append(Path(root.path))
            if source.root_path_snapshot:
                bases.append(Path(source.root_path_snapshot))

            rel = source.relative_directory
            for base in bases:
                candidate = base / rel
                if candidate.is_dir() and find_video_files(candidate):
                    # Streaming zahteva registrovani root (root_id).
                    owning = self._find_owning_root(candidate)
                    if owning is not None:
                        return candidate, owning

        # Pretraga po naslovu u bibliotekama (film bez izvora ili loša putanja).
        return self._search_movie_folder(media)

    def _search_movie_folder(self, media):
        if self._root_repository is None:
            return None

        wanted = {
            _title_identity(value)
            for value in (
                media.title,
                getattr(media, "original_title", None),
                getattr(media, "english_title", None),
            )
            if value
        }
        if not wanted:
            return None

        for root in self._root_repository.list_all():
            root_path = Path(root.path).resolve(strict=False)
            if not root_path.is_dir():
                continue
            bases = [
                root_path / "Strano" / "Filmovi",
                root_path / "Animirano" / "Filmovi",
                root_path / "Domace" / "Filmovi",
                # Stare lokacije (pre migracije strukture) — tolerancija.
                root_path / "Filmovi",
                root_path / "Crtani",
                root_path / "Crtani filmovi",
                root_path / "Domaci" / "Filmovi",
                root_path / "Domaci",
                root_path,
            ]
            for base in [b for b in bases if b.is_dir()]:
                hit = self._search_movie_in(base, wanted, depth=2)
                if hit is not None:
                    return hit, root
        return None

    def _search_movie_in(self, base: Path, wanted: set[str], depth: int):
        try:
            entries = sorted(base.iterdir())
        except OSError:
            return None

        for entry in entries:
            name = entry.name.casefold()
            if name in _SKIP_DIRECTORIES or name.startswith("$"):
                continue
            try:
                if not entry.is_dir():
                    continue
            except OSError:
                continue

            if find_video_files(entry):
                title, _year = parse_media_folder_name(entry.name)
                if (
                    _title_identity(title) in wanted
                    or _title_identity(entry.name) in wanted
                ):
                    return entry
            elif depth > 0:
                hit = self._search_movie_in(entry, wanted, depth - 1)
                if hit is not None:
                    return hit
        return None

    def _has_video_source(self, media_id: int) -> bool:
        """Da li film već ima registrovan izvor sa video fajlom."""

        if self._media_source_service is None:
            return False
        try:
            sources = self._media_source_service.list_media_sources(media_id)
        except Exception:  # noqa: BLE001
            return False
        for source in sources:
            for file in source.files:
                if file.role is MediaFileRole.VIDEO:
                    return True
        return False


    def _find_owning_root(self, directory: Path):
        """Vraća registrovanu biblioteku koja sadrži dati folder (najdublja)."""

        if self._root_repository is None:
            return None

        directory = directory.resolve(strict=False)
        best = None
        best_len = -1
        for root in self._root_repository.list_all():
            root_path = Path(root.path).resolve(strict=False)
            if directory == root_path or root_path in directory.parents:
                length = len(root_path.parts)
                if length > best_len:
                    best = root
                    best_len = length
        return best

    def _register_series_source(
        self,
        scan: SeriesScanResult,
        media_id: int,
    ) -> None:
        """Registruje/azurira media_source serije (video epizoda + prevodi).

        Bez ovoga epizode nemaju putanju videa, pa ne rade ni sličice
        (ffmpeg) ni reprodukcija.
        """

        if self._media_source_service is None:
            return

        directory = scan.directory.resolve(strict=False)
        root = self._find_owning_root(directory)
        if root is None:
            return

        root_path = Path(root.path).resolve(strict=False)
        try:
            relative_directory = directory.relative_to(root_path).as_posix()
        except ValueError:
            return

        files = _collect_episode_files(scan, directory)
        # Prevodi u pod-folderima (Sezona N/subs, titlovi...) koje skener
        # epizoda može da promaši.
        _append_extra_subtitles(directory, files)

        if not files:
            return

        _upsert_media_source(
            self._media_source_service, media_id, root, root_path,
            relative_directory, files,
        )


    def _write_series_manifest(
        self,
        target_directory: Path,
        scan: SeriesScanResult,
        media: MediaItem,
        enrichment: SeriesEnrichment | None = None,
    ) -> None:
        """Piše filmium_info.json serije (ime, opis, sezone/epizode)."""

        enrichment = enrichment or SeriesEnrichment()

        seasons = tuple(
            SeasonManifest(
                season_number=season.season_number,
                name=enrichment.season_name(season.season_number)
                or season.name,
                episodes=tuple(
                    EpisodeManifest(
                        episode_number=episode.episode_number,
                        title=(
                            enrichment.episode_title(
                                season.season_number, episode.episode_number
                            )
                            or episode.title
                        ),
                    )
                    for episode in season.episodes
                ),
            )
            for season in scan.seasons
        )
        manifest = FilmiumInfoManifest(
            title=scan.title,
            media_type=MediaType.SERIES,
            release_year=enrichment.year,
            description=(
                getattr(media, "description", None) or enrichment.overview
            ),
            genres=(
                tuple(getattr(media, "genres", ()) or ()) or enrichment.genres
            ),
            content_category=getattr(media, "content_category", "regular"),
            seasons=seasons,
        )
        try:
            write_filmium_manifest(
                Path(target_directory) / FILMIUM_INFO_FILE_NAME,
                manifest,
            )
        except FilmiumManifestError:
            # Manifest je pomoćni; ne rušimo uspešan uvoz zbog njega.
            pass

    def _resolve_series(
        self,
        title: str,
        enrichment: tmdb_client.MediaTitleEnrichment | None = None,
        content_mode: str = "regular",
        synchronized: bool = False,
    ) -> tuple[MediaItem, bool]:
        wanted = _title_identity(title)

        for item in self._media_repository.list_all():
            if (
                item.media_type is MediaType.SERIES
                and _title_identity(item.title) == wanted
            ):
                return item, False

        # `title` ostaje lokalni (folder); TMDB puni izvorni/engleski + opise.
        created = self._media_repository.create(
            MediaItemCreate(
                title=title,
                media_type=MediaType.SERIES,
                original_title=(
                    enrichment.original_title if enrichment else None
                ),
                english_title=(
                    enrichment.english_title if enrichment else None
                ),
                release_year=enrichment.year if enrichment else None,
                notes=enrichment.local_overview if enrichment else None,
                english_description=(
                    enrichment.english_overview if enrichment else None
                ),
                content_category=content_mode,
                cast_names=enrichment.cast_names if enrichment else (),
                studio=enrichment.studio if enrichment else None,
                director=enrichment.director if enrichment else None,
                is_synchronized=synchronized,
                tmdb_id=enrichment.tmdb_id if enrichment else None,
            )
        )
        return created, True
