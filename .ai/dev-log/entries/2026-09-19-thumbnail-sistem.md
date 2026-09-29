---
id: filmium-2026-09-19-thumbnail-sistem
type: log
domain: filmium
title: Thumbnail sistem — .thumb u biblioteci + cron backfill + settings kontrola
summary: Sličice se sad prave pri dodavanju u .thumb dir (film/epizode), ne na svaki load; + backfill job + Settings Poslovi sekcija.
status: stable
keywords: [thumbnail, thumb, ffmpeg, biblioteka, cron, backfill, settings, poslovi, optimizacija]
tags: [dev-log, filmium, thumbnail, cron]
source_path: .ai/dev-log/entries/2026-09-19-thumbnail-sistem.md
atom_kreiran: 2026-09-19T17:08:56-04:00
atom_azuriran: 2026-09-19T17:08:56-04:00
edges:
- {type: references, target: filmium-catalog-janitor, weight: 0.4}
---

# Thumbnail sistem — .thumb + cron + settings

## Uzrok sporosti
Endpoint `series_episode_thumbnail` pokretao ffmpeg NA SVAKI load, keš u `/tmp` (efemeran → stalno regeneriše).

## Urađeno (5 faza)
- **F1 `media_thumbnail`:** persistentno `<dir>/.thumb/<ime>_thumb.jpg` (film-dir/epizode-dir) + DB-vođena detekcija (`has_thumbnail`/`thumb_path_for`/`ensure_thumbnail`), tmp rezerva. Backward-compat.
- **F2 formater:** pri commitu u biblioteku (`library_import_commit_service`) → puna `.thumb` za sve video fajlove; series uvoz → `.thumb` za sve epizode. Best-effort (ne ruši uvoz).
- **F3 endpoint:** čita persistentni `.thumb` (brzo), ffmpeg tek ako fali → load više nije spor.
- **F4 cron:** `jobs/thumb_backfill.py` (DB `filmium_library_roots`) → pozadinski `.thumb` za sve bez sličice. Test: 10742 videa bez → radi (limit 3 napravio prave).
- **F5 settings:** `ThumbBackfillJob` registrovan (`GET /jobs`) + Settings „Poslovi (Cron)" sekcija — kartice svih poslova (atom_reindex, auto_update, tmdb_people_import, thumb_backfill) + „Pokreni".

## Provera
72 testa prolaze posle svake faze; tsc 0 grešaka; gui build ✓. Optim skener: 8 🔴 kompleksnih fn (kandidati za CISA/modularnost). Sve dual-copy + commitovano.