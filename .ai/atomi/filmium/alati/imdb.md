---
id: imdb
type: tool
domain: filmium
title: IMDB
summary: Ocene i broj glasova (Cinemagoer).
status: stable
keywords:
- imdb
- alat
- filmium
- tmdb
- rotten-tomatoes
- prikupljanje-info-tmdb-imdb
tags:
- alat
- filmium
source_path: .ai/atomi/filmium/alati/imdb.md
atom_kreiran: 2026-09-19 07:37:57-04:00
atom_azuriran: 2026-09-19 07:37:57-04:00
edges:
- type: references
  target: tmdb
  weight: 0.5
- type: references
  target: rotten-tomatoes
  weight: 0.5
- type: references
  target: prikupljanje-info-tmdb-imdb
  weight: 0.5
kategorija: Alat
ikona: film
namena: Ocene i glasovi (Cinemagoer)
---

## 🎯 ŠTA JE
Ocene i broj glasova (Cinemagoer).

## 🤖 KADA AI OVO KORISTI
Za dopunu ocena kada TMDB ocena nije dovoljna; keyless.

## 🛠️ KAKO (ulaz -> izlaz)
Ulaz: naslov/imdb_id. Izlaz: imdb_rating, broj glasova.

## 🔀 VEZE
- [[tmdb]]
- [[rotten-tomatoes]]
- [[prikupljanje-info-tmdb-imdb]]
