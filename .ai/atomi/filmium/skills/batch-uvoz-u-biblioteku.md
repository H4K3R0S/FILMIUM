---
id: batch-uvoz-u-biblioteku
type: skill
domain: filmium
title: Batch uvoz u biblioteku
summary: Masovni uvoz više naslova odjednom.
status: stable
keywords:
- batch
- uvoz
- biblioteku
- vestina
- filmium
- upload-filmova-serija
- skener
- prikupljanje-info-tmdb-imdb
tags:
- vestina
- filmium
source_path: .ai/atomi/filmium/skills/batch-uvoz-u-biblioteku.md
atom_kreiran: 2026-09-19 07:37:57-04:00
atom_azuriran: 2026-09-19 07:37:57-04:00
edges:
- type: references
  target: upload-filmova-serija
  weight: 0.5
- type: references
  target: skener
  weight: 0.5
- type: references
  target: prikupljanje-info-tmdb-imdb
  weight: 0.5
kategorija: Veština
ikona: layers
namena: Masovni uvoz više naslova odjednom.
---

## 🎯 ŠTA JE
Masovni uvoz više naslova odjednom.

## 🤖 KADA AI OVO KORISTI
Kada ima mnogo novih fajlova (npr. posle skeniranja).

## 🛠️ KAKO (ulaz -> izlaz)
Ulaz: lista fajlova/folder. Izlaz: masovni unos + obogaćivanje.

## 🔀 VEZE
- [[upload-filmova-serija]]
- [[skener]]
- [[prikupljanje-info-tmdb-imdb]]
