"""Manifest ćelije: čitanje i provera `cell.json`.

Ćelija je odcepljen domen koji živi u sopstvenom direktorijumu. Manifest je
jedini fajl koji CORE mora da razume da bi je pronašao i povezao.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

CELL_MANIFEST_FILENAME = "cell.json"

_REQUIRED_FIELDS = (
    "domain_id",
    "name",
    "domain_version",
    "kernel_version",
    "port",
    "created_at",
)

_DEFAULT_AI_ENDPOINT = "http://localhost:11434"


class CellManifestError(Exception):
    """Manifest ne postoji, nije čitljiv ili mu nedostaje obavezno polje."""


@dataclass(frozen=True)
class CellManifest:
    """Trajni identitet jedne ćelije."""

    domain_id: str
    name: str
    domain_version: str
    kernel_version: str
    port: int
    core_url: str | None
    created_at: str
    detached_from: str | None
    root: Path
    ai_endpoint: str
    ai_curator_model: str | None
    rag_enabled: bool
    rag_namespace: str

    @property
    def data_dir(self) -> Path:
        """Direktorijum sa bazom, artwork-om i logovima ćelije."""

        return self.root / "data"

    @property
    def database_path(self) -> Path:
        """SQLite baza ćelije, imenovana po domenu."""

        return self.data_dir / f"{self.domain_id}.db"


def load_cell_manifest(root: Path) -> CellManifest:
    """
    Učitava i proverava `cell.json` iz zadatog direktorijuma.

    Args:
        root: Koren ćelije (direktorijum u kom stoji `cell.json`).

    Returns:
        Pročitan manifest.

    Raises:
        CellManifestError: Ako fajl ne postoji, nije ispravan JSON ili mu
            nedostaje obavezno polje.
    """
    path = root / CELL_MANIFEST_FILENAME

    if not path.is_file():
        raise CellManifestError(f"Nema {CELL_MANIFEST_FILENAME} u {root}")

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise CellManifestError(f"Nečitljiv {path}: {error}") from error

    if not isinstance(data, dict):
        raise CellManifestError(f"{path} nije JSON objekat")

    missing = [field for field in _REQUIRED_FIELDS if field not in data]
    if missing:
        raise CellManifestError(
            f"{path} nema obavezna polja: {', '.join(missing)}"
        )

    try:
        port = int(data["port"])
    except (TypeError, ValueError) as error:
        raise CellManifestError(f"{path}: port nije broj") from error

    ai = data.get("ai") or {}
    rag = data.get("rag") or {}
    domain_id = str(data["domain_id"])

    return CellManifest(
        domain_id=domain_id,
        name=str(data["name"]),
        domain_version=str(data["domain_version"]),
        kernel_version=str(data["kernel_version"]),
        port=port,
        core_url=data.get("core_url"),
        created_at=str(data["created_at"]),
        detached_from=data.get("detached_from"),
        root=root,
        ai_endpoint=str(ai.get("endpoint") or _DEFAULT_AI_ENDPOINT),
        ai_curator_model=ai.get("curator_model"),
        rag_enabled=bool(rag.get("enabled", False)),
        rag_namespace=str(rag.get("namespace") or f"cell:{domain_id}"),
    )


def find_cell_manifests(directory: Path) -> tuple[Path, ...]:
    """
    Traži manifeste u zadatom direktorijumu i jedan nivo ispod.

    Dublje se namerno ne ide: ćelija je uvek folder sa imenom domena, a dublje
    skeniranje bi po velikim diskovima trajalo neprihvatljivo dugo.

    Args:
        directory: Direktorijum koji korisnik bira u CORE Settings-u.

    Returns:
        Putanje pronađenih `cell.json` fajlova, sortirane.
    """
    if not directory.is_dir():
        return ()

    found: list[Path] = []

    own = directory / CELL_MANIFEST_FILENAME
    if own.is_file():
        found.append(own)

    try:
        children = sorted(directory.iterdir())
    except OSError:
        return tuple(found)

    for child in children:
        if not child.is_dir():
            continue
        candidate = child / CELL_MANIFEST_FILENAME
        if candidate.is_file():
            found.append(candidate)

    return tuple(found)
