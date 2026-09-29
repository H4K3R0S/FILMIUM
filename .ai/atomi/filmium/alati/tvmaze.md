---
id: tvmaze
type: tool
domain: filmium
title: TVmaze
summary: 'Serije: epizode, mreža, raspored, ocena; keyless.'
status: stable
keywords:
- tvmaze
- alat
- filmium
- region-serije
- prikupljanje-info-tmdb-imdb
tags:
- alat
- filmium
source_path: .ai/atomi/filmium/alati/tvmaze.md
atom_kreiran: 2026-09-19 07:37:57-04:00
atom_azuriran: 2026-09-19 07:37:57-04:00
edges:
- type: references
  target: region-serije
  weight: 0.5
- type: references
  target: prikupljanje-info-tmdb-imdb
  weight: 0.5
kategorija: Alat
ikona: tv
namena: 'Serije: epizode, mreža, ocena'
---

## 🎯 ŠTA JE
Serije: epizode, mreža, raspored, ocena; keyless.

## 🤖 KADA AI OVO KORISTI
Za SERIJE — struktura sezona/epizoda i podaci o emitovanju.

## 🛠️ KAKO (ulaz -> izlaz)
Ulaz: naslov serije. Izlaz: sezone, epizode, mreža, tvmaze_rating.

## 🔀 VEZE
- [[region-serije]]
- [[prikupljanje-info-tmdb-imdb]]
