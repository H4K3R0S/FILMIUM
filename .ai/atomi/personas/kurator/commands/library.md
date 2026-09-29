---
atom_kreiran: 2026-09-26T14:00:00-04:00
atom_azuriran: 2026-09-26T14:00:00-04:00
id: kurator-cmd-library
type: command
title: Library — detail
---
**scan_library {root_id?}** — scan the registered FILMIUM libraries for new
films/series. If `root_id` is given, scan that library root; otherwise scan all
registered roots. Returns a short summary (how many roots scanned). No confirmation.
Examples: "skeniraj biblioteku", "proveri ima li novih filmova".

**enrich {title}** — pull metadata for a title from TMDB and the external
providers (IMDb, Rotten Tomatoes, TVmaze, Jikan). Confirms the TMDB match and
persists external ratings (best-effort). Pass `title` as the user said it; the
system resolves it to a record. Example: "dopuni podatke za Matriks".
