---
id: tmdb
type: tool
domain: filmium
title: TMDB
summary: Primarni izvor metapodataka i slika (naziv, godina, žanr, poster, cast, kolekcija).
status: stable
keywords:
- tmdb
- alat
- filmium
- prikupljanje-info-tmdb-imdb
- imdb
- region-filmovi
tags:
- alat
- filmium
source_path: .ai/atomi/filmium/alati/tmdb.md
atom_kreiran: 2026-09-19 07:37:57-04:00
atom_azuriran: 2026-09-19 07:37:57-04:00
edges:
- type: references
  target: prikupljanje-info-tmdb-imdb
  weight: 0.5
- type: references
  target: imdb
  weight: 0.5
- type: references
  target: region-filmovi
  weight: 0.5
kategorija: Alat
ikona: database
namena: 'Primarni izvor: metapodaci, slike'
---

## 🎯 ŠTA JE
Primarni izvor metapodataka i slika (naziv, godina, žanr, poster, cast, kolekcija).

## 🤖 KADA AI OVO KORISTI
Za SVAKI novi naslov — prvi izvor istine za metapodatke i postere.

## 🛠️ KAKO (ulaz -> izlaz)
Ulaz: naslov+godina (ili tmdb_id). Izlaz: metapodaci+slike. Zahteva API ključ u config/tmdb.json (dodaje korisnik).

## 🔀 VEZE
- [[prikupljanje-info-tmdb-imdb]]
- [[imdb]]
- [[region-filmovi]]
