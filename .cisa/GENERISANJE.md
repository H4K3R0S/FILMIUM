---
id: cisa-generisanje
type: reference
domain: filmium
title: CISA samounapređivač — kako se arhiva pravi, ažurira i sama unapređuje
summary: .cisa/ je arhiva rešenih problema sa trakerima simptom→glavni i score-om uspešnosti.
status: stable
keywords: [cisa, samounapredjivac, arhiva, trakeri, score, root-cause, lekcija]
tags: [cisa, uputstvo, samounapredjivac]
source_path: .cisa/GENERISANJE.md
---
# 🔧 CISA samounapređivač — `.cisa/`

Arhiva SVIH rešenih problema (samo-učenje). Jedan problem = atom u `problemi/<slug>.md`.
Cilj: da AI od najmanjeg simptoma prati trakere do GLAVNOG problema i reši koren, ne simptom.

## ➕ Kako se dodaje (self-improvement petlja)
Kad CISA (bilo koji agent) reši problem:
```bash
python3 scripts/cisa_log.py add --root <dir> --id <slug> --title "…" \
  --problem "…" --solution "…" --result "…" --severity high|med|low \
  --code OPT:201|SEC:324|PYT:001 [--root-cause <glavni-id>] [--related a,b] [--score 0.0-1.0]
```
Ili `cisa_log.add(...)` iz koda. Automatski preračuna `_score.md`.
**Loguj i NAJMANJE probleme** — mreža trakera otkriva zajednički koren.

## 🔗 Trakeri (simptom → glavni problem)
- `root_cause` (edge) + `root_problem:` (polje) → vode od SIMPTOMA ka GLAVNOM (root) problemu.
- `related_to` → bočne veze.
- Primer: „16 pokvarenih testova" (simptom) →`root_cause`→ „zastareo HttpRetriever import" (glavni).
  Prateći traker, AI reši glavni i simptom nestaje.

## 🏅 Score uspešnosti (`_score.md`)
Rešeno/ukupno (%) + **ponderisani uspeh** (ozbiljnost × pouzdanost `score`) + raspodela po ozbiljnosti.
CISA se „unapređuje" gomilanjem dokazanih rešenja → veći recall pri sledećem sličnom problemu + rastući score.

## 🧬 Format problem-atoma
`id, type: cisa_lesson, severity, problem_code, root_problem, score, edges` + telo `## ❌ PROBLEM / ✅ REŠENJE / 📊 REZULTAT`.

## 🌐 Domeni
Isti `.cisa/` postoji u SVAKOM domenu (svoj samounapređivač); alat je deljen (`ai_workplace/scripts/cisa_log.py`).
Povezano sa `cisa_matrix/` (profili agenata) — agenti UPISUJU u `.cisa/` kad reše problem.
