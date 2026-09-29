"""Preusmeravanje CORE putanja na direktorijum ćelije.

Ćelija koristi isti kernel kao CORE, ali joj baza, logovi i podaci stoje u
sopstvenom folderu. Umesto da svaki repozitorijum dobije novu putanju, ovde se
jednom preusmeri registar putanja koji svi već koriste.
"""

from __future__ import annotations

from core.cell.manifest import CellManifest
from core.foundation.paths import CorePaths, core_paths


def apply_cell_paths(
    manifest: CellManifest,
    paths: CorePaths | None = None,
) -> None:
    """
    Preusmerava putanje na direktorijum ćelije i kreira ih.

    Args:
        manifest: Učitan manifest ćelije.
        paths: Registar putanja koji se menja. Bez njega se menja globalni
            `core_paths`, što se radi samo pri podizanju ćelije.
    """
    target = paths if paths is not None else core_paths

    target.data = manifest.data_dir
    target.database_dir = manifest.data_dir
    target.core_database = manifest.database_path
    target.logs = manifest.data_dir / "logs"
    target.screenshots = manifest.data_dir / "screenshots"
    target.editor_projects = target.screenshots / "projects"

    target.ensure_required_dirs()
