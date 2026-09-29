from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path, PurePosixPath

import psycopg

from core.rag.embedder import Embedder
from core.rag.ingest import ingest_text

IGNORISI: tuple[str, ...] = (
    ".git", ".venv", "node_modules", "__pycache__", ".pytest_cache",
    ".pytest_tmp", "target", "dist", "build",
    "NADOGRADNJE",  # radni fajlovi korisnika — nikad ne ingestovati
)
TEKST_EKST: frozenset[str] = frozenset({
    ".md", ".py", ".ts", ".tsx", ".js", ".mjs", ".rs", ".go", ".txt",
    ".json", ".toml", ".yaml", ".yml", ".css", ".html",
})
_MAX_BYTES = 1_000_000


def iter_ingestable(root: Path) -> Iterator[Path]:
    for putanja in root.rglob("*"):
        if not putanja.is_file():
            continue
        # Proveri samo segmente relativne na root, ne pretke root-a
        # (npr. da .pytest_tmp iznad korena ne obori sve).
        relativni = putanja.relative_to(root).parts
        if any(seg in IGNORISI for seg in relativni):
            continue
        if putanja.suffix.lower() not in TEKST_EKST:
            continue
        try:
            if putanja.stat().st_size > _MAX_BYTES:
                continue
        except OSError:
            continue
        yield putanja


def seed_paths(connection: psycopg.Connection, roots: list[Path], *,
               embedder: Embedder, project_root: Path) -> dict[str, int]:
    zbir = {"ingested": 0, "skipped_unchanged": 0, "error": 0}
    for root in roots:
        for putanja in iter_ingestable(root):
            rel = str(PurePosixPath(putanja.relative_to(project_root).as_posix()))
            try:
                text = putanja.read_text(encoding="utf-8", errors="replace")
                rez = ingest_text(connection, rel, text, embedder=embedder)
                zbir[rez.status] = zbir.get(rez.status, 0) + 1
                connection.commit()
            except Exception:  # noqa: BLE001
                connection.rollback()
                zbir["error"] += 1
    return zbir
