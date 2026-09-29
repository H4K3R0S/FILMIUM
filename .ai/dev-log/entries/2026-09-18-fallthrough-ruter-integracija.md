---
id: filmium-2026-09-18-fallthrough-ruter-integracija
type: log
domain: filmium
title: 2026-09-18-fallthrough-ruter-integracija
tags:
- dev-log
- entries
---

# 2026-09-18 — FALLTHROUGH integracija sa centralnim ruterom

## Cilj
FILMIUM (Kurator) na lokalni RAG miss pita centralni ruter i naučeno upisuje kao
nov atom. Primenjeno na F: (autoritativni) i na ~/ai/domains kopiju.

## Urađeno
- `core/cell/fallthrough.py` i `apps/api/routers/solve.py`.
- `apps/api/curator_runtime.py`: RAG retriever `_retriever_rag` umotan u
  `build_fallthrough_retriever(_local_retriever_rag, "filmium", _MANIFEST.root)`
  (Kurator ostaje ime agenta; MediaRetriever/executori netaknuti).
- `/solve` registrovan u `cell_app.py`.
- Port ćelije vraćen na kanonski **4801** (F: i kopija) — usklađen sa ruter manifestom.

## Provereno
- Import ćelije čist (`import cell_app`), `/solve` ruta registrovana.
- Ruter podignut kao systemd user servis `ai-router` (127.0.0.1:4800), `enable --now`.
- Uživo: KALIMA→ruter→CODIUM vratio traženu skriptu (primer iz specifikacije);
  graf-keš pogodak preko `ggraph get`; nepoznat upit → prazan rezultat (graciozno).
- Import čist i sa F: `.venv-linux` i sa ~/ai kopijom.

## Napomene
- Isti fajlovi na F:\FILMIUM i ~/ai/domains/filmium (drže se u sinhronu).
- Sve tolerantno; bez novih zavisnosti.
