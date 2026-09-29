---
atom_kreiran: 2026-09-26T14:00:00-04:00
atom_azuriran: 2026-09-26T14:00:00-04:00
id: kurator-cmd-playback
type: command
title: Playback — detail
---
**play {title}** — open the title's detail page and start it in the WEB player
(the main player, embedded in the Electron webview). This both navigates to the
title's page and plays it. Use for any "watch / open / play <title>" request.
Examples: "pusti Matriks", "otvori Mutiny", "hoću da gledam Incepciju".

**play_vlc {title}** — play the title in VLC instead of the web player. Use ONLY
when the user explicitly says "VLC". (mpv is an internal alternative, not user-facing.)

For a title, pass `title` as the user said it; the system resolves it to a record.
