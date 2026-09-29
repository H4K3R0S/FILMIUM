---
atom_kreiran: 2026-09-26T14:00:00-04:00
atom_azuriran: 2026-09-26T14:00:00-04:00
id: kurator-cmd-browse
type: command
title: Browse / navigate — detail
---
**navigate {view}** — switch the FILMIUM window to a list view. The GUI opens
that route immediately (same as the user clicking the menu). No confirmation.

Views (canonical → what it shows), synonyms accepted:
- animirano (crtani, anime) — animated
- strano (strani, inostrano) — foreign
- domace (domaći) — domestic
- library (biblioteka, sve) — the whole library
- recommended (preporuke) — recommended section
- trending (popularno) — trending
- top-rated (najbolje ocenjeno) — highest rated
- upcoming (uskoro) — upcoming
- favorites (omiljeno, favoriti) — favorites
- collections (kolekcije) — collections
- history (istorija, gledano) — watch history

Examples:
- "pokaži mi animirane serije" → navigate {view: animirano}
- "prebaci na domaće" → navigate {view: domace}
- "otvori omiljene" → navigate {view: favorites}

Filters (optional, applied by the GUI on top of the view):
- media_type ∈ movie | series (synonyms: film/filmovi, serija/serije) — show only films or only series.
- genre — a genre name (e.g. SF, comedy) to filter by.
- sort ∈ rating | year | title | added (synonyms: ocena, godina, naslov, dodato).
Examples: "samo serije" → {media_type: series}; "domaći filmovi po oceni" →
{view: domace, media_type: movie, sort: rating}. Omit `view` to filter the whole library.
