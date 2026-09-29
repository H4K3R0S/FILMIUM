from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path

from core.foundation.paths import core_paths


@dataclass(frozen=True)
class RagConfig:
    dsn: str
    embedding_model: str
    embedding_dim: int
    embedding_endpoint: str
    context_buckets: tuple[int, ...]
    top_k: int
    rrf_k: int
    rerank: bool
    decay_half_life_days: int
    dormant_threshold: float
    default_visible_namespaces: tuple[str, ...]


def _default_config_path() -> Path:
    return core_paths.root / "config" / "rag.json"


def load_rag_config(path: Path | None = None) -> RagConfig:
    """Ucitava RAG konfiguraciju i gradi Postgres DSN.

    Lozinka se cita iz konfiguracije, pa iz env varijable RAG_DB_PASSWORD
    ako u konfiguraciji nedostaje. Testovi mogu preko RAG_TEST_DSN da
    zaobidju ceo blok baze.
    """
    target = path or _default_config_path()
    data = json.loads(target.read_text(encoding="utf-8"))

    db = data["db"]
    # Host/port se mogu pregaziti env-om radi prelaska na Linux mini PC bez
    # menjanja config fajla (npr. RAG_DB_HOST=192.168.1.50).
    host = os.environ.get("RAG_DB_HOST", db["host"])
    port = os.environ.get("RAG_DB_PORT", db["port"])
    password = db.get("password") or os.environ.get("RAG_DB_PASSWORD", "")
    dsn = (
        f"host={host} port={port} dbname={db['name']} "
        f"user={db['user']} password={password}"
    ).strip()

    emb = data["embedding"]
    ret = data["retrieval"]
    dec = data["decay"]
    return RagConfig(
        dsn=dsn,
        embedding_model=emb["model"],
        embedding_dim=int(emb["dim"]),
        embedding_endpoint=emb["endpoint"],
        context_buckets=tuple(int(b) for b in data["context_buckets"]),
        top_k=int(ret["top_k"]),
        rrf_k=int(ret["rrf_k"]),
        rerank=bool(ret["rerank"]),
        decay_half_life_days=int(dec["half_life_days"]),
        dormant_threshold=float(dec["dormant_threshold"]),
        default_visible_namespaces=tuple(data["namespaces"]["default_visible"]),
    )
