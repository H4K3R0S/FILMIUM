# core/domains/<d>/search/vector_index.py
# ==========          VEKTORSKI INDEKS ATOMA (Qdrant, semantička pretraga)          ==========
# Puni per-domen Qdrant kolekciju `atoms_<domen>` embedinzima atoma (ISTI korpus
# kao FTS: .ai/atomi/** + globalni vault) i traži semantički preko
# `core.cell.memory_client` (Ollama nomic-embed-text 768d -> Qdrant :6333).
# Ovo je vektor sloj `HybridRetriever`-a UMESTO mrtvog pgvector-a (LocalRetriever).
# Best-effort svuda: Qdrant/Ollama dole ili modul fali -> 0/[] , NIKAD izuzetak.
from __future__ import annotations

import logging

from core.domains.filmium.search import fts_index  # reuse iteracije atoma + parsera

_logger = logging.getLogger(__name__)
_SNIPPET_MAX = 400
_DOC_MAX = 2000  # koliko teksta atoma šaljemo embedderu


def _collection(domain: str) -> str:
    return f"atoms_{domain}"


def _points_count(domain: str) -> int:
    """Broj tačaka u kolekciji (Qdrant) ili -1 ako nepoznato (Qdrant dole)."""
    import json
    import urllib.request
    try:
        from core.cell import memory_client
        req = urllib.request.Request(f"{memory_client.QDRANT_URL}/collections/{_collection(domain)}")
        with urllib.request.urlopen(req, timeout=3) as r:
            d = json.loads(r.read().decode("utf-8"))
        return int((d.get("result") or {}).get("points_count") or 0)
    except Exception:  # noqa: BLE001
        return -1


def _delete_collection(domain: str) -> None:
    """Obriši kolekciju (za čist rebuild na `force`) — izbacuje ustajale tačke
    (npr. atomi koji su u međuvremenu izbrisani ili sad isključeni type:log)."""
    import urllib.request
    try:
        from core.cell import memory_client
        req = urllib.request.Request(
            f"{memory_client.QDRANT_URL}/collections/{_collection(domain)}", method="DELETE")
        urllib.request.urlopen(req, timeout=3).read()
    except Exception:  # noqa: BLE001, S110
        pass


def sync(domain: str, force: bool = False) -> int:
    """Embeduj atome domena u `atoms_<domen>`. Idempotentno (upsert po id-u).
    Ako NIJE `force` i kolekcija već ima >= broj atoma tačaka, preskače (da se
    ne re-embeduje ceo korpus na svaki boot procesa — `atom_reindex` job zove
    `force=True` da pokupi izmene). Vraća broj upsertovanih (ili postojećih);
    0 na svaku grešku (tolerantno)."""
    try:
        from core.cell import memory_client  # lenj import (kao fallthrough F4 kuka)
    except Exception as error:  # noqa: BLE001
        _logger.debug("vector_index: memory_client nedostupan (%s)", error)
        return 0
    coll = _collection(domain)
    if force:
        _delete_collection(domain)  # čist rebuild — ukloni ustajale/log tačke
    try:
        memory_client.ensure_collection(coll)
    except Exception as error:  # noqa: BLE001
        _logger.debug("vector_index: ensure_collection(%s) nije uspeo (%s)", coll, error)
        return 0
    try:
        files = fts_index._iter_atom_files()
    except Exception as error:  # noqa: BLE001
        _logger.debug("vector_index: iteracija atoma nije uspela (%s)", error)
        return 0
    # PRESKAČI `type: log` (audit/izvršenja) — semantički šum koji gura prave
    # znanjske atome iz top-3 (dokazano bench regresijom na KALIMA logovima).
    to_index: list = []
    for p in files:
        try:
            text = p.read_text(encoding="utf-8", errors="ignore")
            meta, body = fts_index._parse_frontmatter(text)
            if (meta.get("type") or "").strip().lower() == "log":
                continue
            to_index.append((p, meta, body))
        except Exception as error:  # noqa: BLE001
            _logger.debug("vector_index: parsiranje %s nije uspelo (%s)", p, error)
            continue
    if not force:
        pc = _points_count(domain)
        if pc >= len(to_index) and pc > 0:
            return pc  # već indeksirano — preskoči re-embed (jeftin no-op)
    n = 0
    for p, meta, body in to_index:
        try:
            aid = (meta.get("id") or p.stem).strip()
            title = (meta.get("title") or aid).strip()
            doc = f"{title}\n{body}".strip()[:_DOC_MAX]
            if not doc:
                continue
            ok = memory_client.upsert(coll, aid, doc, {
                "id": aid, "title": title,
                "type": meta.get("type", ""), "status": meta.get("status", ""),
                "snippet": (body.strip()[:_SNIPPET_MAX] or title),
            })
            if ok:
                n += 1
        except Exception as error:  # noqa: BLE001 — jedan atom ne ruši sync
            _logger.debug("vector_index: atom %s nije upsertovan (%s)", p, error)
            continue
    return n


def search(domain: str, query: str, k: int = 5) -> list[dict]:
    """Semantička pretraga atoma domena -> [{id, snippet, status, score}].
    Best-effort -> []."""
    try:
        from core.cell import memory_client
        hits = memory_client.search(_collection(domain), query, k=k) or []
    except Exception as error:  # noqa: BLE001
        _logger.debug("vector_index: search nije uspeo (%s)", error)
        return []
    out: list[dict] = []
    for h in hits:
        pl = h.get("payload") or {}
        snip = pl.get("snippet") or pl.get("document") or ""
        if not snip:
            continue
        out.append({
            "id": pl.get("id"), "snippet": snip,
            "status": pl.get("status", ""), "score": h.get("score", 0.0),
        })
    return out
