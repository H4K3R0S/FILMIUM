from __future__ import annotations

import psycopg

from core.rag.node import EdgeSpec, Node
from core.rag.retrieve import RetrievalScope, retrieve
from core.rag.store import get_node, neighbors, sync_node_edges, upsert_node


def memory_search(connection, query, *, embedder, domain=None, k=10) -> list[dict]:
    cvorovi = retrieve(connection, query,
                       RetrievalScope("domain", domain=domain, k=k), embedder=embedder)
    return [
        {"node_id": n.node_id, "title": n.title, "domain": n.domain,
         "source_path": n.source_path, "span_start": n.span_start,
         "span_end": n.span_end, "score": n.score}
        for n in cvorovi
    ]


def memory_get(connection: psycopg.Connection, node_id: str) -> dict | None:
    cvor = get_node(connection, node_id)
    if cvor is None:
        return None
    chunkovi = connection.execute(
        "SELECT content FROM chunks WHERE node_id = %s ORDER BY ordinal", (node_id,)
    ).fetchall()
    return {**cvor, "chunks": [c["content"] for c in chunkovi]}


def memory_neighbors(connection, node_id, *, edge_types=None) -> list[dict]:
    return neighbors(connection, node_id, edge_types=edge_types)


def memory_upsert(connection: psycopg.Connection, node_dict: dict) -> str:
    veze = tuple(
        EdgeSpec(e["type"], e["target"], float(e.get("weight", 0.5)))
        for e in node_dict.get("edges", []) or []
    )
    node = Node(
        id=node_dict["id"], domain=node_dict["domain"],
        node_type=node_dict["type"], namespace=node_dict["namespace"],
        visibility=node_dict.get("visibility", node_dict["namespace"]),
        tier=node_dict["tier"], title=node_dict["title"],
        summary=node_dict.get("summary"), source_path=node_dict.get("source_path"),
        edges=veze,
    )
    upsert_node(connection, node)
    sync_node_edges(connection, node)
    return node.id
