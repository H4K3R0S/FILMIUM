---
id: upload-filmova-serija
type: skill
domain: filmium
title: Upload filmova/serija
summary: Ubacivanje pojedinačnog naslova u biblioteku (fajl + metapodaci).
status: stable
keywords:
- upload
- filmova
- serija
- vestina
- filmium
- batch-uvoz-u-biblioteku
- skener
- prikupljanje-info-tmdb-imdb
tags:
- vestina
- filmium
source_path: .ai/atomi/filmium/skills/upload-filmova-serija.md
atom_kreiran: 2026-09-19 07:37:57-04:00
atom_azuriran: 2026-09-19 07:37:57-04:00
edges:
- type: references
  target: batch-uvoz-u-biblioteku
  weight: 0.5
- type: references
  target: skener
  weight: 0.5
- type: references
  target: prikupljanje-info-tmdb-imdb
  weight: 0.5
kategorija: Veština
ikona: upload
namena: Ubacivanje pojedinačnog naslova u biblioteku (fajl + metapodaci).
---

## 🎯 ŠTA JE
Ubacivanje pojedinačnog naslova u biblioteku (fajl + metapodaci).

## 🤖 KADA AI OVO KORISTI
Kada korisnik doda jedan film/seriju koji treba registrovati.

## 🛠️ KAKO (ulaz -> izlaz)
Ulaz: fajl(ovi). Izlaz: unos u bazi + atomi + metapodaci.

## 🔀 VEZE
- [[batch-uvoz-u-biblioteku]]
- [[skener]]
- [[prikupljanje-info-tmdb-imdb]]
