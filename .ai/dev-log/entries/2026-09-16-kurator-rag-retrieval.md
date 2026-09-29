---
id: filmium-2026-09-16-kurator-rag-retrieval
type: log
domain: filmium
title: 2026-09-16-kurator-rag-retrieval
tags:
- dev-log
- entries
---

# 2026-09-16 — FILMIUM Kurator: RAG retrieval preko CORE-a

Cilj: Kurator (FILMIUM Agent) pri komandi povlači relevantno znanje/prošle
interakcije iz RAG-a i obogaćuje odgovor. Ćelija ne nosi pgvector — retrieval
HTTP-om ka CORE-u. Ime „Kurator" zadržano.

## Urađeno

FILMIUM je bespoke (svoj `core/domains/filmium/curator/intent_router.py`
`CuratorAgent`, nema `core/cell/curator`; već ima nepovezani `MediaRetriever` za
media grounding). Zato NIJE kopija kanona nego EKVIVALENTNA izmena: `CuratorAgent`
dobio `retrieve` param (poslednji) + `_sa_kontekstom` u `_ask_model` (byte-equiv
CORE kanonu — dodaje „Relevantan kontekst iz memorije", graciozno). Media-grounding
netaknut. Nov `apps/api/agent_retriever.py` (`HttpRetriever`, stdlib urllib,
`domain=filmium`, non-200/greška → `[]`). Runtime `curator_runtime.py`:
`_retriever_rag` + `retrieve=` u agentu. Import bez mrežnog poziva.

## Provereno

py 73 testa (2 nova + regresija; 61 `-k curator`), offline import, media-grounding
i write-safety netaknuti. Live retrieval tek kad korisnik pokrene Postgres +
`rag_ingest_cells.py` u CORE-u.

## Napomene

Deo cross-repo D. Ime „Kurator" ostaje samo u FILMIUM-u. Restart ćelije za nov backend.
