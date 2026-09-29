---
id: filmium-cisa-master
type: cisa_global_core
domain: filmium
title: FILMIUM CISA — globalni koordinator situacione svesti
summary: Koordinator situacione svesti FILMIUM-a; Commander delegira pod-agentima po fazama.
status: stable
agent_owner: kurator
active_sub_agents: [filmium-catalog-architect, filmium-media-importer, filmium-catalog-janitor]
situation_awareness_level: high
total_learned_patterns: 4
keywords: [cisa, filmium, zdravlje, biblioteke, (posteri, putanje, tmdb, obogaćenje, titlovi, veze, film↔glumac↔franšiza), catalog-architect]
tags: [cisa, filmium, koordinator, agenti]
source_path: cisa_matrix/filmium_cisa_master.md
atom_kreiran: 2026-09-19T16:07:14-04:00
atom_azuriran: 2026-09-19T16:07:14-04:00
edges:
- {type: has_part, target: filmium-catalog-architect, weight: 0.9}
- {type: has_part, target: filmium-media-importer, weight: 0.9}
- {type: has_part, target: filmium-catalog-janitor, weight: 0.9}
- {type: references, target: kurator, weight: 0.6}
- {type: references, target: learn-media-catalog-integrity, weight: 0.7}
---

# 🧠 FILMIUM CISA — situaciona svest

Koordinator (`kurator` kao Commander) prati zdravlje biblioteke (posteri, putanje, TMDB obogaćenje, titlovi, veze film↔glumac↔franšiza). Kada zadaš zadatak, analizira CISA bazu, prepoznaje obrasce i delegira pod-agentima.

## 🔀 DELEGACIJA (faza → pod-agent)
| Faza | Pod-agent (persona) | Lokalni CISA fajl | Fokus |
|---|---|---|---|
| 1. Struktura & veze | Catalog-Architect (`kurator`) | `[[filmium-catalog-architect]]` | Integritet kataloga i veza (film↔glumac↔franšiza) |
| 2. Uvoz & obogaćenje | Media-Importer (`kurator`) | `[[filmium-media-importer]]` | Skeniranje/uvoz + TMDB delta-obogaćenje |
| 3. Popravke | Catalog-Janitor (`kurator`) | `[[filmium-catalog-janitor]]` | Titlovi/posteri/putanje, dedupe, zastarele putanje |

## 🔄 CROSS-AGENT PETLJA UČENJA
Agenti rade redom, presreću greške, sami rešavaju iz svoje lokalne matrice, i upisuju nove lekcije u `[[learn-media-catalog-integrity]]`. Commander osvežava ovaj master i vezuje stabilno stanje za Git commit (Time-Travel = istorija commit-ova).

## 🛡️ Bezbednost
Agenti rade nad SOPSTVENOM medijskom bibliotekom (lokalno). Jedini eksterni izvor: TMDB API (čita metapodatke). Osetljive sistemske akcije kroz Approval Gate.
