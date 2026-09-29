# apps/api/agent_retriever.py
# ==========          LOCAL RETRIEVER (in-process, sopstvena baza ćelije)          ==========
# RAG kontekst iz SOPSTVENE baze ćelije, bez CORE-a i bez HTTP hop-a. Ogledalo
# CORE `_search` (apps/api/routers/rag.py): load_rag_config -> Embedder ->
# rag_connection -> search_domain(namespaces=cell:<domain>) -> memory_get snippet.
# Svaka greška (nema config/rag.json, baza dole, Ollama dole) -> [] (Agent radi
# bez konteksta). Vraća list[str] snippeta — isti ugovor kao stari HttpRetriever.
from __future__ import annotations

import logging

_logger = logging.getLogger(__name__)

# Maks. dužina jednog snippet-a (kao u CORE `_search`).
_SNIPPET_MAX = 400


class LocalRetriever:
    """In-process RAG retriever ćelije (sopstvena baza, namespace `cell:<domain>`)."""

    def __init__(self, domain: str, k: int = 5) -> None:
        self._domain = domain
        self._k = k

    def retrieve(self, query: str) -> list[str]:
        try:
            from core.rag.config import load_rag_config
            from core.rag.connection import rag_connection
            from core.rag.embedder import Embedder
            from core.rag.mcp_api import memory_get
            from core.rag.retrieve import search_domain

            cfg = load_rag_config()
            embedder = Embedder(cfg.embedding_model, endpoint=cfg.embedding_endpoint)
            out: list[str] = []
            # `connect_timeout` da mrtva baza ne blokira Agentov odgovor.
            with rag_connection(cfg.dsn + " connect_timeout=2") as conn:
                nodes = search_domain(
                    conn, query, self._domain, embedder=embedder, k=self._k,
                    namespaces=(f"cell:{self._domain}",),
                )
                for node in nodes:
                    doc = memory_get(conn, node.node_id) or {}
                    chunkovi = doc.get("chunks") or []
                    telo = "\n".join(chunkovi) or str(doc.get("summary") or node.title or "")
                    if telo:
                        out.append(telo[:_SNIPPET_MAX])
            return out
        except Exception as error:  # noqa: BLE001 — RAG je opcion; nikad ne ruši Agenta
            _logger.debug("LocalRetriever: RAG nedostupan (%s)", error)
            return []
