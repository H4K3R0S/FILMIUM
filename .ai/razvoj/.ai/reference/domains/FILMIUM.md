---
id: core-152c811a-filmium-md
type: reference
domain: core
namespace: global
visibility: global
tier: core
title: FILMIUM (Level-1) — v1.0.0
summary: 'Namena: lična filmska/medijska kolekcija. **Prvi završen domen = referentni
  obrazac** za sve ostale. Verzija domena: **1.0.0** (2026-08-09). Agenti: verovatno
  1'
keywords:
- filmium
- level
- reference
- domains
tags:
- reference
- domains
source_path: .ai/reference/domains/FILMIUM.md
---

# FILMIUM (Level-1) — v1.0.0

Namena: lična filmska/medijska kolekcija. **Prvi završen domen = referentni obrazac** za sve ostale. Verzija domena: **1.0.0** (2026-08-09). Agenti: verovatno 1 (preporuka filmova), malo posla.

## Postoji (kod, migracije v1→v27)
Biblioteke (library/root, scan, organizacija, import), kolekcije + žanrovi (genre rules/selector), artwork (posteri/backdrops, sync), titlovi (scan/inspekcija/repair queue/service), lokalizacija, deljenje (share), aktivnost (feed/log), media source.
Uploads (bulk selekcija/prebacivanje + auto-obogaćivanje na sken), stranica detalja (box ključnih reči IMDB+korisničke, "Updatuj" iz TMDB + srpska latinica), mpv plejer (native overlay), TMDB obogaćivanje, ffprobe media-probe, bulk cron `/update-filmium` (bez terminala, resume), command palette pretraga.
GUI: FilmiumPage, LibraryPage, CollectionsPage, MediaDetailsPage, HistoryPage, UploadsPage + komponente/hooks/stilovi.
Testovi: ~210 GUI + ~673 Python (2026-08-09).

## Post-1.0 backlog (enhancement, ne blokira 1.0)
- Povezani filmovi (TMDB similar/recommendations) — zasebna, obimna mrežna faza (`tmdb_id` kolona, backfill kataloga rate-limited, 3 reda preporuka).
- Epizode serija u bulk (`auto_update_episode`, TMDB po epizodi).
- Pretraga po lokalnim naslovima iz `editor_settings` (sad se ne pretražuju).
- Vizuelni chip aktivne kolekcije.

Pravilo: razbijati velike fajlove (< ~500-800 linija); komentari SR. FILMIUM je uzor po kom se prave IMPERIUM/CODIUM/KALIMA.
