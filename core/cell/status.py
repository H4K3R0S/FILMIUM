"""Status ćelije: ono što CORE pita preko mreže."""

from __future__ import annotations

import platform

from core.cell.manifest import CellManifest


def build_cell_status(
    manifest: CellManifest,
    *,
    pending_upgrades: int = 0,
) -> dict[str, object]:
    """
    Sklapa opis stanja ćelije.

    Args:
        manifest: Manifest ćelije.
        pending_upgrades: Broj primljenih, a neprimenjenih beleški.

    Returns:
        Rečnik spreman za JSON odgovor.
    """
    return {
        "domain_id": manifest.domain_id,
        "name": manifest.name,
        "domain_version": manifest.domain_version,
        "kernel_version": manifest.kernel_version,
        "port": manifest.port,
        "operating_system": platform.system().lower(),
        "node_name": platform.node(),
        "database_path": str(manifest.database_path),
        "rag_enabled": manifest.rag_enabled,
        "rag_namespace": manifest.rag_namespace,
        "pending_upgrades": pending_upgrades,
        "ai_endpoint": manifest.ai_endpoint,
        "ai_curator_model": manifest.ai_curator_model,
    }
