"""Poređenje skeniranog foldera sa postojećim (duplikat detekcija).

Za dati skenirani izvorni folder i njegov kanonski ciljni folder u
biblioteci računa po fajlu status:
    - ``identical`` (zeleno): isti brzi-hash (sigurna kopija),
    - ``similar`` (žuto): isti tip + veličina u okviru ±2% (moguća kopija,
      možda drugo ime),
    - ``new`` (crveno): nema poklapanja — sigurno novo.

Brzi hash: SHA-256 nad prvih + zadnjih ~8 MiB + veličina fajla. Za velike
video fajlove je skoro trenutan, a lažna poklapanja su vrlo retka.
"""

import hashlib
from dataclasses import dataclass
from pathlib import Path

from core.domains.filmium.library_scanner import (
    IMAGE_EXTENSIONS,
    SUBTITLE_EXTENSIONS,
    VIDEO_EXTENSIONS,
)

_HASH_CHUNK = 8 * 1024 * 1024  # 8 MiB
_SIMILAR_TOLERANCE = 0.02       # ±2% veličine za „žuto"


# ==========          MODELI          ==========

@dataclass(frozen=True)
class DuplicateFile:
    relative_path: str
    name: str
    size_bytes: int
    role: str          # video | poster | backdrop | image | subtitle | other
    status: str        # identical | similar | new | existing


@dataclass(frozen=True)
class DuplicateComparison:
    has_duplicate: bool
    target_directory: str | None
    source_files: tuple[DuplicateFile, ...]
    target_files: tuple[DuplicateFile, ...]


# ==========          POMOĆNE          ==========

def _role(path: Path) -> str:
    suffix = path.suffix.casefold()
    if suffix in VIDEO_EXTENSIONS:
        return "video"
    if suffix in SUBTITLE_EXTENSIONS:
        return "subtitle"
    if suffix in IMAGE_EXTENSIONS:
        name = path.stem.casefold()
        if "poster" in name:
            return "poster"
        if "backdrop" in name or "fanart" in name:
            return "backdrop"
        return "image"
    return "other"


def fast_hash(path: Path) -> str | None:
    """SHA-256 nad prvih + zadnjih ~8 MiB + veličina (brzo za velike fajlove)."""

    try:
        size = path.stat().st_size
    except OSError:
        return None

    digest = hashlib.sha256()
    digest.update(str(size).encode("utf-8"))
    try:
        with path.open("rb") as handle:
            head = handle.read(_HASH_CHUNK)
            digest.update(head)
            if size > _HASH_CHUNK:
                handle.seek(max(size - _HASH_CHUNK, 0))
                digest.update(handle.read(_HASH_CHUNK))
    except OSError:
        return None

    return digest.hexdigest()


def _list_files(directory: Path) -> list[Path]:
    if not directory.is_dir():
        return []
    return sorted(
        (path for path in directory.rglob("*") if path.is_file()),
        key=lambda path: path.as_posix(),
    )


def _is_similar(size_a: int, size_b: int) -> bool:
    if size_a <= 0 or size_b <= 0:
        return False
    larger = max(size_a, size_b)
    return abs(size_a - size_b) / larger <= _SIMILAR_TOLERANCE


# ==========          POREĐENJE          ==========

def compare_directories(
    source_directory: Path,
    target_directory: Path,
) -> DuplicateComparison:
    """Poredi skenirani izvor sa postojećim ciljnim folderom."""

    source_paths = _list_files(source_directory)
    target_paths = _list_files(target_directory)

    if not target_paths:
        # Nema šta da se poredi → nije duplikat.
        source_files = tuple(
            DuplicateFile(
                relative_path=path.relative_to(source_directory).as_posix(),
                name=path.name,
                size_bytes=path.stat().st_size if path.exists() else 0,
                role=_role(path),
                status="new",
            )
            for path in source_paths
        )
        return DuplicateComparison(
            has_duplicate=False,
            target_directory=None,
            source_files=source_files,
            target_files=(),
        )

    target_hashes: dict[str, Path] = {}
    target_sizes_by_role: dict[str, list[int]] = {}
    target_files: list[DuplicateFile] = []
    for path in target_paths:
        try:
            size = path.stat().st_size
        except OSError:
            size = 0
        role = _role(path)
        target_sizes_by_role.setdefault(role, []).append(size)
        digest = fast_hash(path)
        if digest is not None:
            target_hashes.setdefault(digest, path)
        target_files.append(
            DuplicateFile(
                relative_path=path.relative_to(target_directory).as_posix(),
                name=path.name,
                size_bytes=size,
                role=role,
                status="existing",
            )
        )

    source_files: list[DuplicateFile] = []
    for path in source_paths:
        try:
            size = path.stat().st_size
        except OSError:
            size = 0
        role = _role(path)
        digest = fast_hash(path)

        if digest is not None and digest in target_hashes:
            status = "identical"
        elif any(
            _is_similar(size, other)
            for other in target_sizes_by_role.get(role, ())
        ):
            status = "similar"
        else:
            status = "new"

        source_files.append(
            DuplicateFile(
                relative_path=path.relative_to(source_directory).as_posix(),
                name=path.name,
                size_bytes=size,
                role=role,
                status=status,
            )
        )

    return DuplicateComparison(
        has_duplicate=True,
        target_directory=target_directory.as_posix(),
        source_files=tuple(source_files),
        target_files=tuple(target_files),
    )
