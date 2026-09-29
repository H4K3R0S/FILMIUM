---
atom_kreiran: 2026-09-26T14:00:00-04:00
atom_azuriran: 2026-09-26T14:00:00-04:00
id: kurator-cmd-metadata
type: command
title: Metadata — detail
---
Writing commands — ALWAYS ask for confirmation before saving.

**edit_metadata {title, changes}** — change a field of a title. `changes` is a
map of field → new value. Example: "stavi ocenu 8 Matriksu" → {title: "Matriks",
changes: {rating: 8}}.

**save {title, changes}** — persist the changes (same shape as edit_metadata).

The agent shows a preview and requires the user's confirmation token before the
write is applied.
