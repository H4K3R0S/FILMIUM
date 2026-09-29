---
atom_kreiran: 2026-09-16T00:06:58-04:00
atom_azuriran: 2026-09-16T00:06:58-04:00
id: kurator-tool-plejer
type: tool
title: Puštanje filma
tags: [plejer]
---
Podrazumevano puštanje koristi intent `play` sa `params.media_id`: otvara se
stranica filma u FILMIUM i pušta ugrađeni web plejer (in-app). VLC koristi samo
ako korisnik izričito traži VLC — tada intent `play_vlc` sa `params.media_id`.
