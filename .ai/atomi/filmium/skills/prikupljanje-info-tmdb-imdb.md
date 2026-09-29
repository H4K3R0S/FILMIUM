---
id: prikupljanje-info-tmdb-imdb
type: skill
domain: filmium
title: Prikupljanje info (TMDB/IMDB/…)
summary: Orkestracija info-alata radi obogaćivanja metapodataka.
status: stable
keywords:
- prikupljanje
- info
- tmdb
- imdb
- vestina
- filmium
- rotten-tomatoes
- tvmaze
tags:
- vestina
- filmium
source_path: .ai/atomi/filmium/skills/prikupljanje-info-tmdb-imdb.md
atom_kreiran: 2026-09-19 07:37:57-04:00
atom_azuriran: 2026-09-19 07:37:57-04:00
edges:
- type: references
  target: tmdb
  weight: 0.5
- type: references
  target: imdb
  weight: 0.5
- type: references
  target: rotten-tomatoes
  weight: 0.5
- type: references
  target: tvmaze
  weight: 0.5
- type: references
  target: jikan
  weight: 0.5
kategorija: Veština
ikona: database
namena: Orkestracija info-alata radi obogaćivanja metapodataka.
---

## 🎯 ŠTA JE
Orkestracija info-alata radi obogaćivanja metapodataka.

## 🤖 KADA AI OVO KORISTI
Posle uvoza — ocene, cast, posteri, kolekcije, žanrovi.

## 🛠️ KAKO (ulaz -> izlaz)
Ulaz: naslov(i). Izlaz: kompletni metapodaci. Redosled: TMDB -> IMDB/RT/TVmaze/Jikan.

## 🔀 VEZE
- [[tmdb]]
- [[imdb]]
- [[rotten-tomatoes]]
- [[tvmaze]]
- [[jikan]]
