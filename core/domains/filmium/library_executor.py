import shutil
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from core.domains.filmium.library_manifest import (
    write_filmium_manifest,
)
from core.domains.filmium.library_models import (
    FilmiumInfoManifest,
    MediaOrganizationPlan,
    OrganizationAction,
    OrganizationActionType,
)

# ==========          REZULTAT IZVRSENJA          ==========

@dataclass(frozen=True)
class MediaOrganizationExecutionResult:
    """Opisuje uspesno primenjen plan organizacije."""

    target_directory: Path
    manifest: FilmiumInfoManifest
    moved_file_count: int
    created_directory_count: int


# ==========          GRESKE IZVRSENJA          ==========

class FilmiumOrganizationExecutionError(RuntimeError):
    """Oznacava odbijen ili neuspesan pokusaj organizacije."""


def _is_inside(path: Path, directory: Path) -> bool:
    """Proverava pripadnost putanje bez oslanjanja na tekst prefiksa."""

    try:
        path.resolve(strict=False).relative_to(
            directory.resolve(strict=False)
        )
    except ValueError:
        return False

    return True


def _validate_action(
    plan: MediaOrganizationPlan,
    action: OrganizationAction,
) -> None:
    if not _is_inside(action.destination, plan.target_directory):
        raise FilmiumOrganizationExecutionError(
            "Plan sadrzi odrediste izvan ciljnog FILMIUM foldera."
        )

    if action.action_type is OrganizationActionType.MOVE_FILE:
        if action.source is None:
            raise FilmiumOrganizationExecutionError(
                "MOVE_FILE akcija nema izvornu datoteku."
            )

        if not _is_inside(action.source, plan.source_directory):
            raise FilmiumOrganizationExecutionError(
                "Plan sadrzi izvor izvan skeniranog foldera."
            )

    elif action.source is not None:
        raise FilmiumOrganizationExecutionError(
            "Akcija koja nije MOVE_FILE ne sme imati izvor."
        )


def _validate_plan(plan: MediaOrganizationPlan) -> None:
    if not plan.can_apply:
        raise FilmiumOrganizationExecutionError(
            "Plan ima blokirajuca upozorenja i ne moze biti primenjen."
        )

    if not plan.source_directory.is_dir():
        raise FilmiumOrganizationExecutionError(
            "Izvorni folder vise nije dostupan."
        )

    write_actions = [
        action
        for action in plan.actions
        if action.action_type is OrganizationActionType.WRITE_MANIFEST
    ]

    if len(write_actions) != 1:
        raise FilmiumOrganizationExecutionError(
            "Plan mora imati tacno jednu WRITE_MANIFEST akciju."
        )

    for action in plan.actions:
        _validate_action(plan, action)


# ==========          PROVERA PRE PROMENE          ==========

def _preflight(
    plan: MediaOrganizationPlan,
    conflict_mode: str = "fail",
) -> None:
    """Ponovo proverava filesystem neposredno pre izvrsenja."""

    for action in plan.actions:
        if (
            action.action_type is OrganizationActionType.CREATE_DIRECTORY
            and action.destination.exists()
            and not action.destination.is_dir()
        ):
            raise FilmiumOrganizationExecutionError(
                    "Putanja za novi folder je zauzeta datotekom: "
                    f"{action.destination}"
                )

        if action.action_type is not OrganizationActionType.MOVE_FILE:
            continue

        assert action.source is not None

        if not action.source.is_file() or action.source.is_symlink():
            raise FilmiumOrganizationExecutionError(
                "Izvorna datoteka vise nije dostupna ili je simbolicka "
                f"veza: {action.source}"
            )

        # Postojeće odredište blokira samo u podrazumevanom „fail" režimu;
        # „skip"/„overwrite" ga obrađuju tokom izvršenja.
        if conflict_mode == "fail" and action.destination.exists():
            raise FilmiumOrganizationExecutionError(
                "Odredisna datoteka je u medjuvremenu kreirana: "
                f"{action.destination}"
            )


# ==========          PREMESTANJE (I PREKO DISKOVA)          ==========

_COPY_CHUNK = 1024 * 1024  # 1 MiB


def _move_path(source: Path, destination: Path) -> None:
    """Premesta fajl; ako rename ne radi preko diska, kopira pa briše."""

    try:
        source.replace(destination)
    except OSError:
        # Preko granica diska (EXDEV) rename ne uspeva → shutil.move
        # kopira pa uklanja original.
        shutil.move(str(source), str(destination))


def _move_path_progress(
    source: Path,
    destination: Path,
    report: Callable[[int, int], None],
) -> None:
    """
    Premesta fajl uz byte-progres tekućeg fajla preko ``report(uradjeno,
    ukupno)``. Isti disk = trenutni rename (report(size, size)); preko
    diska = kopiranje u komadima sa progresom, pa brisanje originala.
    """

    try:
        total = source.stat().st_size
    except OSError:
        total = 0

    try:
        source.replace(destination)
        report(total, total)
        return
    except OSError:
        # EXDEV / preko diska → kopiraj u komadima sa progresom.
        pass

    try:
        copied = 0
        with source.open("rb") as reader, destination.open("wb") as writer:
            while True:
                chunk = reader.read(_COPY_CHUNK)
                if not chunk:
                    break
                writer.write(chunk)
                copied += len(chunk)
                report(copied, total)

        shutil.copystat(str(source), str(destination))
        source.unlink()
    except OSError:
        # Neuspeh (npr. zaključan izvor): ukloni delimičnu/kopiranu
        # odredišnu datoteku da ne ostane duplikat u biblioteci, pa prosledi
        # grešku (rollback čisti ostalo).
        try:
            destination.unlink(missing_ok=True)
        except OSError:
            pass
        raise

    report(total, total)


# ==========          POVRATAK PROMENA          ==========

def _try_rmdir(directory: Path) -> None:
    """Ukloni folder ako je prazan; nepostojeci ili neprazan se tiho preskace."""

    try:
        directory.rmdir()
    except OSError:
        pass


def _restore_one_file(source: Path, destination: Path) -> str | None:
    """Vrati jednu datoteku na izvornu putanju (rollback). Greska -> poruka."""

    try:
        source.parent.mkdir(parents=True, exist_ok=True)
        if destination.exists() and not source.exists():
            _move_path(destination, source)
    except OSError as error:
        return f"Nije vracena datoteka {destination}: {error}"
    return None


def _rollback_moves(
    moved_files: list[tuple[Path, Path]],
) -> list[str]:
    errors: list[str] = []

    for source, destination in reversed(moved_files):
        error = _restore_one_file(source, destination)
        if error:
            errors.append(error)

    return errors


def _remove_empty_directories(
    directories: list[Path],
) -> None:
    for directory in reversed(directories):
        _try_rmdir(directory)


def _remove_empty_source_tree(
    source_directory: Path,
    target_directory: Path,
) -> None:
    """Uklanja stari izvor samo kada je nakon prenosa potpuno prazan."""

    if (
        source_directory.resolve(strict=False)
        == target_directory.resolve(strict=False)
    ):
        return

    try:
        directories = sorted(
            (
                path
                for path in source_directory.rglob("*")
                if path.is_dir()
            ),
            key=lambda path: len(path.parts),
            reverse=True,
        )
    except OSError:
        return

    for directory in directories:
        _try_rmdir(directory)

    try:
        source_directory.rmdir()
    except OSError:
        # Bez rekurzivnog brisanja: sadržaj koji nije premešten ostaje.
        return


# ==========          IZVRSENJE PLANA          ==========

def execute_media_organization(
    plan: MediaOrganizationPlan,
    *,
    confirmed: bool = False,
    on_progress: Callable[[int, int, int, int], None] | None = None,
    conflict_mode: str = "fail",
) -> MediaOrganizationExecutionResult:
    """
    Primenjuje prethodno pregledan plan samo uz potvrdu korisnika.

    ``on_progress(fajlova_gotovo, fajlova_ukupno, bajtova_gotovo,
    bajtova_ukupno)`` se poziva tokom prenosa (byte-progres tekućeg fajla)
    i po završetku svakog fajla. Greška u callback-u ne sme da sruši uvoz.

    ``conflict_mode`` određuje ponašanje kad odredište već postoji:
    ``"fail"`` (podrazumevano, blokira), ``"skip"`` (dodaj samo nove, ostavi
    postojeće) ili ``"overwrite"`` (prepiši postojeće fajlove).
    """

    if not confirmed:
        raise FilmiumOrganizationExecutionError(
            "Organizacija nije eksplicitno potvrdjena."
        )

    _validate_plan(plan)
    _preflight(plan, conflict_mode)

    total_moves = sum(
        1
        for action in plan.actions
        if action.action_type is OrganizationActionType.MOVE_FILE
    )
    created_directories: list[Path] = []
    moved_files: list[tuple[Path, Path]] = []
    manifest_backup: bytes | None = None
    manifest_path: Path | None = None

    def _report(files_done: int, file_done: int, file_total: int) -> None:
        if on_progress is None:
            return
        try:
            on_progress(files_done, total_moves, file_done, file_total)
        except Exception:  # noqa: BLE001, S110
            pass

    try:
        for action in plan.actions:
            if action.action_type is OrganizationActionType.CREATE_DIRECTORY:
                if not action.destination.exists():
                    action.destination.mkdir(parents=True, exist_ok=False)
                    created_directories.append(action.destination)

            elif action.action_type is OrganizationActionType.MOVE_FILE:
                assert action.source is not None

                if action.destination.exists():
                    if conflict_mode == "skip":
                        # „Dodaj novo": postojeći fajl ostaje netaknut.
                        continue
                    if conflict_mode == "overwrite":
                        action.destination.unlink()

                action.destination.parent.mkdir(parents=True, exist_ok=True)
                completed = len(moved_files)
                _move_path_progress(
                    action.source,
                    action.destination,
                    lambda done, total, completed=completed: _report(completed, done, total),
                )
                moved_files.append((action.source, action.destination))

            elif action.action_type is OrganizationActionType.WRITE_MANIFEST:
                manifest_path = action.destination

                if manifest_path.is_file():
                    manifest_backup = manifest_path.read_bytes()

                write_filmium_manifest(manifest_path, plan.manifest)

    except Exception as error:
        if manifest_path is not None:
            try:
                if manifest_backup is None:
                    manifest_path.unlink(missing_ok=True)
                else:
                    manifest_path.write_bytes(manifest_backup)
            except OSError:
                pass

        rollback_errors = _rollback_moves(moved_files)
        _remove_empty_directories(created_directories)
        detail = f"Organizacija nije uspela: {error}"

        if rollback_errors:
            detail += " Povratak nije potpun: " + "; ".join(
                rollback_errors
            )

        raise FilmiumOrganizationExecutionError(detail) from error

    _remove_empty_source_tree(
        plan.source_directory,
        plan.target_directory,
    )

    return MediaOrganizationExecutionResult(
        target_directory=plan.target_directory,
        manifest=plan.manifest,
        moved_file_count=len(moved_files),
        created_directory_count=len(created_directories),
    )
