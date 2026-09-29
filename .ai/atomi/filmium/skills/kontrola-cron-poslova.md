---
id: kontrola-cron-poslova
type: skill
domain: filmium
title: Kontrola cron poslova
summary: Zakazivanje i nadzor periodičnih poslova.
status: stable
keywords:
- kontrola
- cron
- poslova
- vestina
- filmium
- skener
- prikupljanje-info-tmdb-imdb
tags:
- vestina
- filmium
source_path: .ai/atomi/filmium/skills/kontrola-cron-poslova.md
atom_kreiran: 2026-09-19 07:37:57-04:00
atom_azuriran: 2026-09-19 07:37:57-04:00
edges:
- type: references
  target: skener
  weight: 0.5
- type: references
  target: prikupljanje-info-tmdb-imdb
  weight: 0.5
kategorija: Veština
ikona: clock
namena: Zakazivanje i nadzor periodičnih poslova.
---

## 🎯 ŠTA JE
Zakazivanje i nadzor periodičnih poslova.

## 🤖 KADA AI OVO KORISTI
Za automatsko skeniranje/obogaćivanje po rasporedu.

## 🛠️ KAKO (ulaz -> izlaz)
Ulaz: raspored (cron). Izlaz: zakazani/pokrenuti poslovi + status.

## 🔀 VEZE
- [[skener]]
- [[prikupljanje-info-tmdb-imdb]]
