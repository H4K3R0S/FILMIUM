---
id: filmium-search-filmovi-serije-glumci
type: skill
domain: filmium
title: FILMIUM Search (filmovi/serije/glumci)
summary: Hibridna pretraga baze i atoma.
status: stable
keywords:
- filmium
- search
- filmovi
- serije
- glumci
- vestina
- region-filmovi
- region-serije
tags:
- vestina
- filmium
source_path: .ai/atomi/filmium/skills/filmium-search-filmovi-serije-glumci.md
atom_kreiran: 2026-09-19 07:37:57-04:00
atom_azuriran: 2026-09-19 07:37:57-04:00
edges:
- type: references
  target: region-filmovi
  weight: 0.5
- type: references
  target: region-serije
  weight: 0.5
- type: references
  target: region-glumci
  weight: 0.5
kategorija: Veština
ikona: search
namena: Hibridna pretraga baze i atoma.
---

## 🎯 ŠTA JE
Hibridna pretraga baze i atoma.

## 🤖 KADA AI OVO KORISTI
Kada AI ili korisnik traži naslov, glumca ili vezu.

## 🛠️ KAKO (ulaz -> izlaz)
Ulaz: upit. Izlaz: rangirani pogoci + veze ka atomima.

## 🔀 VEZE
- [[region-filmovi]]
- [[region-serije]]
- [[region-glumci]]
