---
atom_kreiran: 2026-09-16T00:59:42-04:00
atom_azuriran: 2026-09-26T14:00:00-04:00
id: kurator-command-katalog
type: command
title: Command catalog
---
Pick EXACTLY ONE command. For a title, pass `title` as the user said it (the
system resolves it). Never invent commands.

## How to choose
- Wants a VIEW / genre / type list (browse) → **navigate**
- Wants to WATCH a specific title → **play**
- Wants to SEARCH or get a recommendation (no watching) → **search**
- Wants to SCAN the library for new media → **scan_library**
- Wants to CHANGE data → **edit_metadata** / **save** (confirm first)
- Wants a title that is NOT in the library → offer **add_to_wishlist** (confirm first)

## Browse — [[kurator-cmd-browse]]
- navigate {view?, media_type?, genre?, sort?} — switch the window to a list view
  and/or apply a filter/sort (GUI applies it instantly).
  view ∈ animirano, strano, domace, library, recommended, trending, top-rated,
  upcoming, favorites, collections, history (synonyms allowed; omit view = whole library).
  media_type ∈ movie|series; sort ∈ rating|year|title|added.
  e.g. "pokaži animirane" → {view: animirano}; "samo serije" → {media_type: series};
  "SF filmovi po oceni" → {media_type: movie, genre: SF, sort: rating}
- open_second_brain_map {} — open the Second Brain MAPS map (rings/circle/areas/links/timeline/orbit + other systems' spheres).

## Playback — [[kurator-cmd-playback]]
- play {title} — open the title's page and play in the WEB player (main).
  e.g. "pusti Matriks", "otvori Mutiny"
- play_vlc {title} — play in VLC (only if the user says VLC).

## Library — [[kurator-cmd-library]]
- scan_library {root_id?} — scan registered libraries for new films/series
  (given root_id, or all roots). e.g. "skeniraj biblioteku"
- enrich {title} — pull metadata for a title from TMDB + external providers
  (IMDb, Rotten Tomatoes, TVmaze, Jikan). e.g. "dopuni podatke za Matriks"

## Discover — [[kurator-cmd-discover]]
- search {query, top_n?} — search the library; returns titles as an answer, does
  NOT change the window. e.g. "nađi nešto sa Kijanuom"
- recommend {genre?} — open the "Recommended" section (GUI computes it), optionally
  for a genre. e.g. "preporuči mi nešto", "preporuči SF"
- info {title} — get info about a title (year, genres, rating, overview). Looks in
  the library first; if not there, fetches from TMDB. e.g. "reci mi o filmu Inception"

## Metadata (confirm before saving) — [[kurator-cmd-metadata]]
- edit_metadata {title, changes} — change a field. e.g. "stavi ocenu 8 Matriksu"
- save {title, changes} — save the changes (same as edit_metadata)
- add_to_wishlist {title} — add a title the user wants but isn't in the library
  to the wishlist. First checks if it's already in the library or wishlist.
  e.g. "dodaj Blade Runner u želje", or when a requested title isn't found.
