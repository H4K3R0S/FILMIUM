---
atom_kreiran: 2026-09-26T14:00:00-04:00
atom_azuriran: 2026-09-26T14:00:00-04:00
id: kurator-cmd-discover
type: command
title: Discover / search — detail
---
**search {query, top_n?}** — search or recommend within the library. Returns a
list of titles as an answer; does NOT change the window (use navigate for that).
Use for "find / recommend / anything with X" requests.
Examples: "nađi nešto sa Kijanuom", "preporuči komediju iz 2010" ({query, top_n}).

**recommend {genre?}** — open the "Recommended" section, which the GUI computes
from the user's library (optionally narrowed to a genre). Use for "recommend me
something" requests. Example: "preporuči mi nešto", "preporuči SF" → {genre: SF}.
