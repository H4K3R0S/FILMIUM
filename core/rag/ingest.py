from __future__ import annotations

from dataclasses import dataclass

import psycopg

from core.rag.chunker import chunk_for
from core.rag.deriver import derive_node_from_file, has_frontmatter
from core.rag.edges import sync_structural_edges
from core.rag.embedder import Embedder
from core.rag.node import parse_node
from core.rag.store import (
    ChunkRow,
    get_node,
    node_fully_embedded,
    sync_node_edges,
    upsert_chunks,
    upsert_node,
)


@dataclass(frozen=True)
class IngestResult:
    node_id: str
    status: str
    chunks: int
    embedded: int


def ingest_text(connection: psycopg.Connection, relpath: str, text: str,
                *, embedder: Embedder) -> IngestResult:
    if has_frontmatter(text):
        node = parse_node(text, source_path=relpath)
    else:
        node = derive_node_from_file(relpath, text)

    postojeci = get_node(connection, node.id)
    nepromenjeno = (
        postojeci is not None
        and postojeci["content_hash"] == node.content_hash
    )
    # Preskoci samo ako je nepromenjeno I vec potpuno embedovano — inace
    # (npr. ranije seedovano dok Ollama nije radila) ponovo embeduj.
    if nepromenjeno and node_fully_embedded(connection, node.id):
        return IngestResult(node.id, "skipped_unchanged", 0, 0)

    telo = node.body or text
    chunks = chunk_for(relpath, telo)
    vektori = embedder.embed([c.content for c in chunks])
    embedded = sum(1 for v in vektori if v is not None)

    redovi = [
        ChunkRow(c.ordinal, c.content, c.token_count, vektori[i])
        for i, c in enumerate(chunks)
    ]

    upsert_node(connection, node)
    upsert_chunks(connection, node.id, redovi)
    sync_node_edges(connection, node)
    # Auto import/link edges (depends_on/tested_by/references) — samo ka
    # ciljevima koji vec postoje kao cvorovi.
    sync_structural_edges(connection, node)
    return IngestResult(node.id, "ingested", len(chunks), embedded)
