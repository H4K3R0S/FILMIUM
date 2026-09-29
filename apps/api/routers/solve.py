"""POST /solve — prijem FALLTHROUGH zahteva od centralnog rutera.

Ruter (Global Atom OS) prosleđuje ovamo kada DRUGI domen nema odgovor a OVAJ
domen nudi traženu capability. Odgovaramo ISKLJUČIVO iz lokalne baze (Hybrid
RAG — FTS5 + Postgres/pgvector best-effort — + naučeni atomi) — BEZ daljeg
fallthrough-a (ruter već broji hopove i čuva od petlji). Uvek 200 sa
{ok, domain, snippets}; sve greške -> prazni snippeti.

Putanja je namerno `/solve` (bez `/api/v1` prefiksa) jer ruter (`router.ts`,
httpForwarder) šalje POST tačno na `/solve`.
"""
from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter
from pydantic import BaseModel

from core.cell.fallthrough import LearnedAtomStore
from core.cell.manifest import load_cell_manifest
from core.domains.filmium.search.hybrid_retriever import HybridRetriever

_ROOT = Path(__file__).resolve().parents[3]
_MANIFEST = load_cell_manifest(_ROOT)
_DOMAIN = _MANIFEST.domain_id
# HybridRetriever = FTS5 (uvek radi, i bez Postgresa) + vektor (best-effort) —
# bolji lokalni pogodak za /solve nego čist LocalRetriever.
_local = HybridRetriever(domain=_DOMAIN, k=5)
_learned = LearnedAtomStore(_ROOT, _DOMAIN)

router = APIRouter(tags=["Fallthrough"])


class SolveRequest(BaseModel):
    query: str = ""
    capability: str | None = None
    origin: str | None = None
    payload: object | None = None
    hops: int | None = None
    path: list[str] | None = None


class SolveResponse(BaseModel):
    ok: bool
    domain: str
    snippets: list[str] = []


@router.post("/solve", response_model=SolveResponse)
def solve(req: SolveRequest) -> SolveResponse:
    q = (req.query or "").strip()
    if not q:
        return SolveResponse(ok=False, domain=_DOMAIN, snippets=[])
    try:
        snippets = _local.retrieve(q) or []
    except Exception:  # noqa: BLE001 — lokalni RAG opcion
        snippets = []
    if not snippets:
        snippets = _learned.search(q)
    return SolveResponse(ok=bool(snippets), domain=_DOMAIN, snippets=snippets)
