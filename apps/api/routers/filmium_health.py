# ==========          FILMIUM HEALTH — API          ==========
"""Jednoobrazan health endpoint celije: `GET /api/v1/filmium/health` (v.
UNAPREDJENJE/01-ARHITEKTURA/11-observability-i-telemetrija.md).

Tolerantno svuda: provera vektor sloja (Qdrant/pgvector) ima kratak timeout
i NIKAD ne puca — u najgorem slucaju vraca 'down'. Ne pokrece nista pri
uvozu (nema mreznog poziva na modulskom nivou).
"""
from __future__ import annotations

import socket
import time

from fastapi import APIRouter

from core.cell.jobs import PROCESS_STARTED_AT
from core.domains.filmium.jobs.registry import REGISTRY
from core.domains.filmium.search import fts_index

router = APIRouter(prefix="/api/v1/filmium", tags=["FILMIUM Health"])

_QDRANT_HOST = "127.0.0.1"
_QDRANT_PORT = 6333
_CHECK_TIMEOUT_S = 0.3


def _qdrant_up() -> bool:
    try:
        with socket.create_connection(
            (_QDRANT_HOST, _QDRANT_PORT), timeout=_CHECK_TIMEOUT_S
        ):
            return True
    except OSError:
        return False


def _pgvector_up() -> bool:
    try:
        import psycopg  # lenj uvoz — tezak paket, samo kad se health stvarno pita

        from core.rag.config import load_rag_config

        dsn = load_rag_config().dsn
        with psycopg.connect(dsn, connect_timeout=1) as conn:
            conn.execute("SELECT 1")
        return True
    except Exception:  # noqa: BLE001 — health je tolerantan po definiciji
        return False


def _vector_status() -> str:
    try:
        if _qdrant_up() or _pgvector_up():
            return "up"
    except Exception:  # noqa: BLE001, S110
        pass
    return "down"


@router.get("/health")
def health() -> dict:
    """`{ok, rag:{fts_atoms, vector}, jobs:<broj registrovanih>, uptime_s}`."""

    try:
        fts_atoms = fts_index.count()
    except Exception:  # noqa: BLE001
        fts_atoms = 0

    try:
        jobs_n = len(REGISTRY)
    except Exception:  # noqa: BLE001
        jobs_n = 0

    return {
        "ok": True,
        "rag": {"fts_atoms": fts_atoms, "vector": _vector_status()},
        "jobs": jobs_n,
        "uptime_s": round(time.time() - PROCESS_STARTED_AT, 3),
    }
