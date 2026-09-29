---
id: rotten-tomatoes
type: tool
domain: filmium
title: Rotten Tomatoes
summary: Tomatometer (kritika) i Audience score (publika); keyless.
status: stable
keywords:
- rotten
- tomatoes
- alat
- filmium
- imdb
- prikupljanje-info-tmdb-imdb
tags:
- alat
- filmium
source_path: .ai/atomi/filmium/alati/rotten-tomatoes.md
atom_kreiran: 2026-09-19 07:37:57-04:00
atom_azuriran: 2026-09-19 07:37:57-04:00
edges:
- type: references
  target: imdb
  weight: 0.5
- type: references
  target: prikupljanje-info-tmdb-imdb
  weight: 0.5
kategorija: Alat
ikona: star
namena: Tomatometer / publika
---

## 🎯 ŠTA JE
Tomatometer (kritika) i Audience score (publika); keyless.

## 🤖 KADA AI OVO KORISTI
Za dodatni ugao ocene (kritika vs publika).

## 🛠️ KAKO (ulaz -> izlaz)
Ulaz: naslov+godina. Izlaz: rt_tomatometer, rt_audience_score.

## 🔀 VEZE
- [[imdb]]
- [[prikupljanje-info-tmdb-imdb]]
