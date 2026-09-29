import re
from dataclasses import replace
from pathlib import Path

from core.domains.filmium.library_manifest import (
    FILMIUM_INFO_FILE_NAME,
)
from core.domains.filmium.library_models import (
    ArtworkManifest,
    FilmiumInfoManifest,
    MediaFileRole,
    MediaFilesManifest,
    MediaFolderScanResult,
    MediaOrganizationPlan,
    OrganizationAction,
    OrganizationActionType,
    SubtitleManifest,
)

# ==========          KANONSKI NAZIVI          ==========

WINDOWS_INVALID_CHARACTERS = re.compile(r'[<>:"/\\|?*]')
WINDOWS_RESERVED_NAMES = {
    "aux",
    "clock$",
    "con",
    "nul",
    "prn",
    *(f"com{index}" for index in range(1, 10)),
    *(f"lpt{index}" for index in range(1, 10)),
}


class FilmiumOrganizationPlanError(ValueError):
    """Oznacava zahtev iz kog nije moguce napraviti bezbedan plan."""


def _safe_name(value: str, fallback: str) -> str:
    """Pravi naziv bez znakova koji nisu dozvoljeni na Windowsu."""

    safe_value = WINDOWS_INVALID_CHARACTERS.sub(" ", value)
    safe_value = re.sub(r"\s+", " ", safe_value).strip(" .")

    if not safe_value:
        safe_value = fallback

    if safe_value.casefold() in WINDOWS_RESERVED_NAMES:
        safe_value = f"{safe_value}_"

    return safe_value


def _canonical_base(result: MediaFolderScanResult) -> str:
    title = _safe_name(result.title, "FILMIUM sadrzaj")

    if result.release_year is None:
        return title

    return f"{title} ({result.release_year})"


def canonical_target_directory(
    result: MediaFolderScanResult,
    library_root: Path,
) -> Path:
    """Kanonski ciljni folder (`<koren>/Naslov (Godina)`) za dati sadržaj."""

    return library_root / _canonical_base(result)


def prune_empty_directories(directory: Path) -> None:
    """
    Uklanja prazne poddirektorijume ciljnog foldera (npr. leftover „ostalo"
    iz ranijih testova) odozdo naviše. Folder sa stvarnim fajlovima ostaje
    netaknut — briše se samo prazna hijerarhija, da ne blokira uvoz.
    """

    if not directory.is_dir():
        return

    directories = sorted(
        (path for path in directory.rglob("*") if path.is_dir()),
        key=lambda path: len(path.parts),
        reverse=True,
    )
    for path in directories:
        _try_rmdir(path)


def _try_rmdir(path: Path) -> None:
    """Ukloni folder ako je prazan (nepostojeci/neprazan se tiho preskace)."""

    try:
        path.rmdir()  # uspeva samo ako je prazan
    except OSError:
        pass


def _canonical_extension(source: Path) -> str:
    """Zadrzava izvornu ekstenziju u ujednacenom malom obliku."""

    return source.suffix.casefold()


def _source_path(directory: Path, reference: str) -> Path:
    return directory.joinpath(*reference.split("/"))


def _same_path(first: Path, second: Path) -> bool:
    return first.resolve(strict=False) == second.resolve(strict=False)


# ==========          GRADITELJ PLANA          ==========

class _OrganizationPlanBuilder:
    """Sakuplja akcije, kolizije i nove relativne putanje."""

    def __init__(
        self,
        result: MediaFolderScanResult,
        library_root: Path,
        target_directory: Path | None = None,
    ) -> None:
        self.result = result
        self.base_name = _canonical_base(result)
        self.target_directory = (
            library_root / self.base_name
            if target_directory is None
            else target_directory
        )
        self.actions: list[OrganizationAction] = []
        self.warnings = list(result.warnings)
        # „Meka" upozorenja: fajl je već na odredištu (ili više fajlova cilja
        # isto odredište). NE blokiraju potvrdu — sadržaj se svejedno upiše u
        # bazu; postojeći fajl ostaje na disku (re-skan već organizovanog).
        self.soft_warnings: list[str] = []
        self.destinations: set[Path] = set()

    def add_directory(self, directory: Path, reason: str) -> None:
        if directory.is_dir():
            return

        if directory.exists():
            self.warnings.append(
                f"Odrediste postoji i nije folder: {directory}"
            )
            return

        self.actions.append(
            OrganizationAction(
                action_type=OrganizationActionType.CREATE_DIRECTORY,
                destination=directory,
                reason=reason,
            )
        )

    def add_file(
        self,
        reference: str | None,
        destination_relative: Path | None,
        reason: str,
    ) -> str | None:
        if reference is None or destination_relative is None:
            return None

        source = _source_path(self.result.directory, reference)
        destination = self.target_directory / destination_relative
        destination_key = destination.resolve(strict=False)

        if not source.is_file():
            self.warnings.append(
                f"Izvorna datoteka nije pronadjena: {reference}"
            )
            return destination_relative.as_posix()

        if destination_key in self.destinations:
            self.soft_warnings.append(
                f"Vise datoteka koristi isto odrediste: {destination}"
            )
            return destination_relative.as_posix()

        self.destinations.add(destination_key)

        if destination.exists() and not _same_path(source, destination):
            self.soft_warnings.append(
                f"Odredisna datoteka vec postoji: {destination}"
            )
            return destination_relative.as_posix()

        if not _same_path(source, destination):
            self.actions.append(
                OrganizationAction(
                    action_type=OrganizationActionType.MOVE_FILE,
                    source=source,
                    destination=destination,
                    reason=reason,
                )
            )

        return destination_relative.as_posix()


def _role_destination(
    base_name: str,
    source_reference: str | None,
    suffix: str,
) -> Path | None:
    if source_reference is None:
        return None

    extension = _canonical_extension(Path(source_reference))
    return Path(f"{base_name}{suffix}{extension}")


def _plan_subtitles(
    builder: _OrganizationPlanBuilder,
    manifest: FilmiumInfoManifest,
) -> tuple[SubtitleManifest, ...]:
    planned_subtitles: list[SubtitleManifest] = []
    language_counts: dict[str, int] = {}

    if manifest.files.subtitles:
        builder.add_directory(
            builder.target_directory / "subtitles",
            "Kreira standardni folder za prevode.",
        )

    for subtitle in manifest.files.subtitles:
        language = _safe_name(subtitle.language, "und")
        language_key = language.casefold()
        language_counts[language_key] = (
            language_counts.get(language_key, 0) + 1
        )
        occurrence = language_counts[language_key]
        language_suffix = (
            language if occurrence == 1 else f"{language}-{occurrence}"
        )
        extension = _canonical_extension(Path(subtitle.path))
        destination = Path(
            "subtitles",
            f"{builder.base_name}.{language_suffix}{extension}",
        )
        planned_path = builder.add_file(
            subtitle.path,
            destination,
            "Ujednacava naziv i lokaciju prevoda.",
        )

        if planned_path is not None:
            planned_subtitles.append(
                SubtitleManifest(
                    path=planned_path,
                    language=subtitle.language,
                    label=subtitle.label,
                )
            )

    return tuple(planned_subtitles)


def _plan_artworks(
    builder: _OrganizationPlanBuilder,
    artworks: tuple[ArtworkManifest, ...],
    folder_name: str,
    file_role: str,
) -> tuple[ArtworkManifest, ...]:
    """Planira kanonski folder i nazive jedne grupe slika."""

    target_folder = builder.target_directory / folder_name
    builder.add_directory(
        target_folder,
        f"Kreira standardni folder za {file_role} slike.",
    )
    planned_artworks: list[ArtworkManifest] = []

    for index, artwork in enumerate(artworks, start=1):
        extension = _canonical_extension(Path(artwork.path))
        destination = Path(
            folder_name,
            (
                f"{builder.base_name} - {file_role} "
                f"{index:02d}{extension}"
            ),
        )
        planned_path = builder.add_file(
            artwork.path,
            destination,
            f"Ujednacava naziv i lokaciju {file_role} slike.",
        )

        if planned_path is not None:
            planned_artworks.append(
                replace(
                    artwork,
                    path=planned_path,
                )
            )

    return tuple(planned_artworks)


def _unique_ostalo_destination(
    builder: "_OrganizationPlanBuilder",
    base_name: str,
    extension: str,
) -> Path:
    """Vraća slobodno ime u folderu ostalo (base, base.1, base.2, ...)."""

    index = 0
    while True:
        suffix = "" if index == 0 else f".{index}"
        candidate_relative = Path("ostalo", f"{base_name}{suffix}{extension}")
        candidate_key = (
            builder.target_directory / candidate_relative
        ).resolve(strict=False)
        if candidate_key not in builder.destinations:
            return candidate_relative
        index += 1


def _plan_other_files(
    builder: _OrganizationPlanBuilder,
) -> None:
    """Čuva sve neprepoznate fajlove u standardnom folderu ostalo."""

    extras = [
        file
        for file in builder.result.detected_files
        if file.role is MediaFileRole.UNKNOWN
    ]

    # Kada se sadržaj premešta u novi kanonski folder, postojeći
    # manifest se čuva kao rezervna informacija. Novi autoritativni
    # manifest se svakako upisuje nakon svih MOVE_FILE akcija.
    if not _same_path(
        builder.result.directory,
        builder.target_directory,
    ):
        extras.extend(
            file
            for file in builder.result.detected_files
            if file.role is MediaFileRole.MANIFEST
        )

    if not extras:
        return

    builder.add_directory(
        builder.target_directory / "ostalo",
        "Kreira folder za neprepoznate i pomoćne fajlove.",
    )

    for file in extras:
        relative_path = file.path.relative_to(
            builder.result.directory
        )

        if file.role is MediaFileRole.MANIFEST:
            # Backup postojećeg manifesta; ako već-organizovan folder već ima
            # ostalo/filmium_info.original.json, biramo jedinstveno ime da se
            # izbegne kolizija "vise datoteka koristi isto odrediste".
            destination = _unique_ostalo_destination(
                builder,
                "filmium_info.original",
                ".json",
            )
        elif (
            relative_path.parts
            and relative_path.parts[0].casefold() == "ostalo"
        ):
            destination = relative_path
        else:
            destination = Path("ostalo", *relative_path.parts)

        builder.add_file(
            relative_path.as_posix(),
            destination,
            "Čuva neprepoznatu datoteku umesto njenog brisanja.",
        )


# ==========          JAVNI PLANER          ==========

def plan_media_organization(
    result: MediaFolderScanResult,
    library_root: Path,
    *,
    target_directory: Path | None = None,
) -> MediaOrganizationPlan:
    """Pravi pregled organizacije bez bilo kakve izmene filesystema."""

    if not library_root.exists():
        raise FilmiumOrganizationPlanError(
            f"Korenski folder biblioteke ne postoji: {library_root}"
        )

    if not library_root.is_dir():
        raise FilmiumOrganizationPlanError(
            f"Putanja biblioteke nije folder: {library_root}"
        )

    builder = _OrganizationPlanBuilder(
        result,
        library_root,
        target_directory,
    )

    if result.release_year is None:
        builder.warnings.append(
            "Organizacija zahteva poznatu godinu izdanja."
        )

    builder.add_directory(
        builder.target_directory,
        "Kreira kanonski folder FILMIUM sadrzaja.",
    )

    source_files = result.manifest.files
    video = builder.add_file(
        source_files.video,
        _role_destination(
            builder.base_name,
            source_files.video,
            "",
        ),
        "Ujednacava naziv glavnog video fajla.",
    )
    poster = builder.add_file(
        source_files.poster,
        _role_destination(
            builder.base_name,
            source_files.poster,
            " - poster",
        ),
        "Ujednacava naziv postera.",
    )
    backdrop = builder.add_file(
        source_files.backdrop,
        _role_destination(
            builder.base_name,
            source_files.backdrop,
            " - backdrop",
        ),
        "Ujednacava naziv backdrop slike.",
    )
    trailer = builder.add_file(
        source_files.trailer,
        _role_destination(
            builder.base_name,
            source_files.trailer,
            " - trailer",
        ),
        "Ujednacava naziv trailera.",
    )
    subtitles = _plan_subtitles(builder, result.manifest)
    wallpapers = _plan_artworks(
        builder,
        source_files.wallpapers,
        "wallpapers",
        "wallpaper",
    )
    fanart = _plan_artworks(
        builder,
        source_files.fanart,
        "fanart",
        "fanart",
    )
    _plan_other_files(builder)

    planned_manifest = replace(
        result.manifest,
        files=MediaFilesManifest(
            video=video,
            poster=poster,
            backdrop=backdrop,
            trailer=trailer,
            subtitles=subtitles,
            wallpapers=wallpapers,
            fanart=fanart,
        ),
    )

    builder.actions.append(
        OrganizationAction(
            action_type=OrganizationActionType.WRITE_MANIFEST,
            destination=(
                builder.target_directory / FILMIUM_INFO_FILE_NAME
            ),
            reason="Upisuje prenosive relativne putanje u manifest.",
        )
    )

    return MediaOrganizationPlan(
        source_directory=result.directory,
        target_directory=builder.target_directory,
        manifest=planned_manifest,
        detected_files=result.detected_files,
        actions=tuple(builder.actions),
        warnings=tuple(dict.fromkeys(builder.warnings)),
        soft_warnings=tuple(dict.fromkeys(builder.soft_warnings)),
    )
