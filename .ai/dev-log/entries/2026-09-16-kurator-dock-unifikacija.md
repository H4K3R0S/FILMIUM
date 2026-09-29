---
id: filmium-2026-09-16-kurator-dock-unifikacija
type: log
domain: filmium
title: 2026-09-16-kurator-dock-unifikacija
tags:
- dev-log
- entries
---

# 2026-09-16 — FILMIUM Kurator dock: dole-centar (umesto lebdeće ikonice)

Cilj: Kurator chat kao jedan dock, fiksiran dole-centar, na SVIM stranicama
(standalone + CORE embed), umesto lebdeće ikonice u workspace-u. Ime „Kurator"
zadržano — to je ime agenta u FILMIUM-u.

## Urađeno

`FilmiumKuratorChat` (lebdeći okvir + FAB) → `FilmiumKuratorDock`: izvučen
sadržaj (CoreChat + logika iz `curatorClient.ts`) u `.agent-dock` dole-centar
kontejner sa skupljanjem, bez frame-in-frame (stari FAB/panel/backdrop
obrisani). Montiran jednom preko `cellAgentDock` slota (`CellNav.AgentDock` →
`CellShell` + `CellApp` `ChromelessContent`); uklonjen lebdeći mount iz
`FilmiumWorkspace`. Reflow: `useDockHeightVar` (var na :root) + `agent-dock.css`
cap (`max-height: min(58vh,460px)`).

## Provereno

`tsc` čist, `npm run build` čist; `gui/dist` rebuildovan i committovan (FILMIUM
prati dist). Ćelija (8781) nije živo proverena — kod simetričan KALIMA
(verifikovana uživo).

## Napomene

Deo cross-repo „Agent Chat Unifikacija". Ime „Kurator" ostaje samo u FILMIUM-u.
