from __future__ import annotations

import psycopg


def _uslovi(domain: str | None, owner_agent: str | None,
            namespaces: tuple[str, ...]) -> tuple[str, list]:
    uslovi = ["n.namespace = ANY(%s)"]
    params: list = [list(namespaces)]
    if domain is not None:
        uslovi.append("n.domain = %s")
        params.append(domain)
    if owner_agent is not None:
        uslovi.append("n.owner_agent = %s")
        params.append(owner_agent)
    return " AND ".join(uslovi), params


def _dedup(redovi: list[dict]) -> list[str]:
    vidjeni: list[str] = []
    for r in redovi:
        if r["node_id"] not in vidjeni:
            vidjeni.append(r["node_id"])
    return vidjeni


def vector_search(connection: psycopg.Connection, query_vec: list[float], *,
                  domain: str | None, namespaces: tuple[str, ...],
                  owner_agent: str | None = None, k: int = 20) -> list[str]:
    where, params = _uslovi(domain, owner_agent, namespaces)
    literal = "[" + ",".join(repr(float(x)) for x in query_vec) + "]"
    sql = f"""
        SELECT c.node_id
        FROM chunks c JOIN nodes n ON n.id = c.node_id
        WHERE c.embedding IS NOT NULL AND {where}
        ORDER BY c.embedding <=> %s::vector
        LIMIT %s
    """
    redovi = connection.execute(sql, [*params, literal, k * 3]).fetchall()
    return _dedup(redovi)[:k]


def bm25_search(connection: psycopg.Connection, query: str, *,
                domain: str | None, namespaces: tuple[str, ...],
                owner_agent: str | None = None, k: int = 20) -> list[str]:
    where, params = _uslovi(domain, owner_agent, namespaces)
    sql = f"""
        SELECT c.node_id
        FROM chunks c JOIN nodes n ON n.id = c.node_id
        WHERE c.fts @@ plainto_tsquery('simple', %s) AND {where}
        ORDER BY ts_rank_cd(c.fts, plainto_tsquery('simple', %s)) DESC
        LIMIT %s
    """
    redovi = connection.execute(sql, [query, *params, query, k * 3]).fetchall()
    return _dedup(redovi)[:k]


def shallow_search(connection: psycopg.Connection, query: str, *,
                   k: int = 10) -> list[dict]:
    """T1 ruter: BM25 nad shallow_index, bez vektora."""
    sql = """
        SELECT node_id, domain, node_type, title
        FROM shallow_index
        WHERE fts @@ plainto_tsquery('simple', %s)
        ORDER BY ts_rank_cd(fts, plainto_tsquery('simple', %s)) DESC
        LIMIT %s
    """
    return connection.execute(sql, (query, query, k)).fetchall()
