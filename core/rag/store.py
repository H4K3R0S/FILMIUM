from __future__ import annotations

import json
from dataclasses import dataclass

import psycopg

from core.rag.node import EdgeSpec, Node


@dataclass(frozen=True)
class ChunkRow:
    ordinal: int
    content: str
    token_count: int
    embedding: list[float] | None


_NODE_UPSERT = """
INSERT INTO nodes (
    id, domain, node_type, subtype, namespace, visibility, tier, owner_agent,
    title, summary, keywords, tags, symbols, source_path, span_start, span_end,
    content_hash, attributes, status)
VALUES (
    %(id)s, %(domain)s, %(node_type)s, %(subtype)s, %(namespace)s, %(visibility)s,
    %(tier)s, %(owner_agent)s, %(title)s, %(summary)s, %(keywords)s, %(tags)s,
    %(symbols)s, %(source_path)s, %(span_start)s, %(span_end)s, %(content_hash)s,
    %(attributes)s, 'active')
ON CONFLICT (id) DO UPDATE SET
    domain=EXCLUDED.domain, node_type=EXCLUDED.node_type, subtype=EXCLUDED.subtype,
    namespace=EXCLUDED.namespace, visibility=EXCLUDED.visibility, tier=EXCLUDED.tier,
    owner_agent=EXCLUDED.owner_agent, title=EXCLUDED.title, summary=EXCLUDED.summary,
    keywords=EXCLUDED.keywords, tags=EXCLUDED.tags, symbols=EXCLUDED.symbols,
    source_path=EXCLUDED.source_path, span_start=EXCLUDED.span_start,
    span_end=EXCLUDED.span_end, content_hash=EXCLUDED.content_hash,
    attributes=EXCLUDED.attributes, updated_at=now()
"""

_SHALLOW_UPSERT = """
INSERT INTO shallow_index (node_id, domain, node_type, title, summary, keywords, tags, fts)
VALUES (%(id)s, %(domain)s, %(node_type)s, %(title)s, %(summary)s, %(keywords)s, %(tags)s,
        to_tsvector('simple', coalesce(%(title)s,'') || ' ' || coalesce(%(summary)s,'')
                    || ' ' || array_to_string(%(keywords)s::text[], ' ')))
ON CONFLICT (node_id) DO UPDATE SET
    domain=EXCLUDED.domain, node_type=EXCLUDED.node_type, title=EXCLUDED.title,
    summary=EXCLUDED.summary, keywords=EXCLUDED.keywords, tags=EXCLUDED.tags,
    fts=EXCLUDED.fts
"""


def _node_params(node: Node) -> dict:
    return {
        "id": node.id, "domain": node.domain, "node_type": node.node_type,
        "subtype": node.subtype, "namespace": node.namespace,
        "visibility": node.visibility, "tier": node.tier,
        "owner_agent": node.owner_agent, "title": node.title,
        "summary": node.summary, "keywords": list(node.keywords),
        "tags": list(node.tags), "symbols": list(node.symbols),
        "source_path": node.source_path, "span_start": node.span_start,
        "span_end": node.span_end, "content_hash": node.content_hash,
        "attributes": json.dumps(node.attributes),
    }


def upsert_node(connection: psycopg.Connection, node: Node) -> None:
    params = _node_params(node)
    connection.execute(_NODE_UPSERT, params)
    connection.execute(_SHALLOW_UPSERT, params)


def get_node(connection: psycopg.Connection, node_id: str) -> dict | None:
    return connection.execute(
        "SELECT * FROM nodes WHERE id = %s", (node_id,)
    ).fetchone()


def upsert_chunks(connection: psycopg.Connection, node_id: str,
                  chunks: list[ChunkRow]) -> None:
    connection.execute("DELETE FROM chunks WHERE node_id = %s", (node_id,))
    for ch in chunks:
        connection.execute(
            """
            INSERT INTO chunks (id, node_id, ordinal, content, token_count, embedding, fts)
            VALUES (%s, %s, %s, %s, %s, %s, to_tsvector('simple', %s))
            """,
            (f"{node_id}#{ch.ordinal}", node_id, ch.ordinal, ch.content,
             ch.token_count, ch.embedding, ch.content),
        )


def upsert_edge(connection: psycopg.Connection, src: str, edge: EdgeSpec,
                *, decay_exempt: bool) -> None:
    connection.execute(
        """
        INSERT INTO edges (src, dst, edge_type, weight, decay_exempt, last_used_at)
        VALUES (%s, %s, %s, %s, %s, now())
        ON CONFLICT (src, dst, edge_type) DO UPDATE SET
            weight=EXCLUDED.weight, decay_exempt=EXCLUDED.decay_exempt,
            state='active', last_used_at=now()
        """,
        (src, edge.target, edge.edge_type, edge.weight, decay_exempt),
    )


def sync_node_edges(connection: psycopg.Connection, node: Node) -> None:
    exempt = {
        r["name"]: r["decay_exempt"]
        for r in connection.execute(
            "SELECT name, decay_exempt FROM edge_types"
        ).fetchall()
    }
    for edge in node.edges:
        upsert_edge(connection, node.id, edge,
                    decay_exempt=bool(exempt.get(edge.edge_type, False)))


def neighbors(
    connection: psycopg.Connection,
    node_id: str,
    *,
    edge_types: tuple[str, ...] | None = None,
    max_depth: int = 2,
    include_dormant: bool = False,
) -> list[dict]:
    """Rekurzivni traverzal odlaznih veza od node_id.

    Vraca {id, edge_type, weight, depth}. Preskace dormant veze osim ako
    include_dormant. Opciono filtrira po edge_types.
    """
    uslov_stanje = "" if include_dormant else "AND e.state <> 'dormant'"
    uslov_tip = "AND e.edge_type = ANY(%s)" if edge_types else ""

    sql = f"""
    WITH RECURSIVE hod AS (
        SELECT e.dst AS id, e.edge_type, e.weight, 1 AS depth
        FROM edges e
        WHERE e.src = %s {uslov_stanje} {uslov_tip}
        UNION ALL
        SELECT e.dst, e.edge_type, e.weight, h.depth + 1
        FROM edges e
        JOIN hod h ON e.src = h.id
        WHERE h.depth < %s {uslov_stanje} {uslov_tip}
    )
    SELECT DISTINCT id, edge_type, weight, depth FROM hod ORDER BY depth, id
    """

    params: list = [node_id]
    if edge_types:
        params.append(list(edge_types))
    params.append(max_depth)
    if edge_types:
        params.append(list(edge_types))

    return connection.execute(sql, params).fetchall()


def visible_node_ids(
    connection: psycopg.Connection,
    *,
    domain: str,
    namespaces: tuple[str, ...],
) -> list[str]:
    """Id-evi cvorova u domenu ciji je namespace u dozvoljenom skupu."""
    redovi = connection.execute(
        "SELECT id FROM nodes WHERE domain = %s AND namespace = ANY(%s)",
        (domain, list(namespaces)),
    ).fetchall()
    return [r["id"] for r in redovi]


def node_fully_embedded(connection: psycopg.Connection, node_id: str) -> bool:
    """True ako cvor ima chunkove i svi imaju embedding (nema NULL)."""
    red = connection.execute(
        "SELECT count(*) AS total, count(embedding) AS emb "
        "FROM chunks WHERE node_id = %s",
        (node_id,),
    ).fetchone()
    return red["total"] > 0 and red["total"] == red["emb"]
