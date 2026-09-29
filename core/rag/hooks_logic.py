from __future__ import annotations

import psycopg

from core.rag.retrieve import RetrievalScope, retrieve


def evaluate_tool_access(connection: psycopg.Connection, source_path: str, *,
                         current_domain: str) -> tuple[bool, str]:
    """Namespace gate: blokira private cvor drugog domena."""
    red = connection.execute(
        "SELECT domain, namespace FROM nodes WHERE source_path = %s LIMIT 1",
        (source_path,),
    ).fetchone()
    if red is None:
        return True, "ok"
    if red["namespace"] == "private" and red["domain"] != current_domain:
        return False, "ACCESS_DENIED: private namespace drugog domena"
    return True, "ok"


def build_context_injection(connection: psycopg.Connection, query: str, *,
                            embedder, domain: str | None, k: int = 3) -> str:
    """Formatira top-k RAG cvorove u tekstualni blok sa file:line."""
    scope = RetrievalScope(tier="domain", domain=domain, k=k)
    cvorovi = retrieve(connection, query, scope, embedder=embedder)
    linije = []
    for n in cvorovi:
        if n.source_path and n.span_start is not None:
            lokacija = f" [{n.source_path}:{n.span_start}-{n.span_end}]"
        elif n.source_path:
            lokacija = f" [{n.source_path}]"
        else:
            lokacija = ""
        linije.append(f"- {n.title}{lokacija}")
    return "\n".join(linije)
