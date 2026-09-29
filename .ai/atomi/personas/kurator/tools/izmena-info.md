---
atom_kreiran: 2026-09-16T00:06:58-04:00
atom_azuriran: 2026-09-16T00:06:58-04:00
id: kurator-tool-izmena-info
type: tool
title: Izmena i čuvanje informacija
tags: [izmena, cuvanje]
---
Za izmenu podataka o filmu koristi intent `edit_metadata` (ili `save`) sa
`params.media_id` i `params.changes` (mapa polje→vrednost). Dozvoljena polja:
title, original_title, english_title, release_year, runtime_minutes,
watch_status, rating, notes, english_description, content_category, studio,
director, collection, is_favorite. Izmena se izvršava tek posle potvrde korisnika.
