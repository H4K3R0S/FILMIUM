from __future__ import annotations

from dataclasses import dataclass

import psycopg

from core.rag.fusion import rrf_fuse
from core.rag.search import bm25_search, vector_search


@dataclass(frozen=True)
class RetrievedNode:
    node_id: str
    title: str
    domain: str
    node_type: str
    source_path: str | None
    span_start: int | None
    span_end: int | None
    score: float


@dataclass(frozen=True)
class RetrievalScope:
    tier: str
    domain: str | None = None
    owner_agent: str | None = None
    namespaces: tuple[str, ...] = ("global", "protected")
    k: int = 10


def _ucitaj_cvorove(connection: psycopg.Connection,
                    id_skor: list[tuple[str, float]]) -> list[RetrievedNode]:
    if not id_skor:
        return []
    ids = [i for i, _ in id_skor]
    redovi = {
        r["id"]: r
        for r in connection.execute(
            "SELECT id, title, domain, node_type, source_path, span_start, span_end "
            "FROM nodes WHERE id = ANY(%s)", (ids,)
        ).fetchall()
    }
    rezultat: list[RetrievedNode] = []
    for ident, skor in id_skor:
        r = redovi.get(ident)
        if r is None:
            continue
        rezultat.append(RetrievedNode(
            node_id=r["id"], title=r["title"], domain=r["domain"],
            node_type=r["node_type"], source_path=r["source_path"],
            span_start=r["span_start"], span_end=r["span_end"], score=skor,
        ))
    return rezultat


def retrieve(connection: psycopg.Connection, query: str, scope: RetrievalScope,
             *, embedder) -> list[RetrievedNode]:
    query_vec = embedder.embed([query])[0]

    rankings: list[list[str]] = []
    if query_vec is not None:
        rankings.append(vector_search(
            connection, query_vec, domain=scope.domain,
            namespaces=scope.namespaces, owner_agent=scope.owner_agent, k=scope.k * 2))
    if scope.tier != "agent":
        rankings.append(bm25_search(
            connection, query, domain=scope.domain,
            namespaces=scope.namespaces, owner_agent=scope.owner_agent, k=scope.k * 2))

    fuzija = rrf_fuse(rankings)[:scope.k]
    return _ucitaj_cvorove(connection, fuzija)


def search_domain(connection, query, domain, *, embedder, k=10,
                  namespaces=("global", "protected")):
    return retrieve(connection, query,
                    RetrievalScope("domain", domain=domain, namespaces=namespaces, k=k),
                    embedder=embedder)


def search_agent(connection, query, agent_id, *, embedder, k=3):
    return retrieve(connection, query,
                    RetrievalScope("agent", owner_agent=agent_id, k=k),
                    embedder=embedder)
