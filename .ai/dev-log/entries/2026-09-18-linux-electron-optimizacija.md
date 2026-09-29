---
id: filmium-2026-09-18-linux-electron-optimizacija
type: log
domain: filmium
title: 2026-09-18-linux-electron-optimizacija
tags:
- dev-log
- entries
---

# 2026-09-18 — Linux+Windows, Electron prozor, biblioteka F:, keš postera, virtualizacija, brzina

Cilj: FILMIUM radi brzo na Kali Linuxu (i dalje i na Windowsu), u pravom prozoru
aplikacije, sa ispravnim prikazom slika iz biblioteke na F:. Agent ostaje „Kurator".

## Urađeno

- Univerzalni prelazak: `start.sh` (Linux ulaz, prepozna OS i predaje `start.bat`
  ako nije Linux), Linux `.venv-linux` odvojen od Windows `.venv`,
  `dependencies.py` platformski svestan (mpv/vlc/ffmpeg apt; radi na oba OS-a).
- Prozor: Electron (Chromium) `cell-shell` — frameless, maksimizovan; ~4x brži
  render od WebKit2GTK na NVIDIA. `cell_window.py` (WebKit) fallback.
- Biblioteka na deljenom disku: `os_library_bridge.py` pri startu usklađuje koren
  biblioteke sa OS-om (Windows `F:\\` ⇄ Linux `/run/media/kalima/FILMIUM`), pa
  se izvorne slike/fajlovi čitaju na oba sistema. Lokalni `data/filmium/assets` =
  samo keš.
- Slike: batch `cache_all_posters.py` — keširano ~1804 malih postera/backdrops
  (npr. 454 KB izvor → 87 KB keš); uvoz sada sam kešira poster pri dodavanju filma.
- Runtime brzina: asset endpoint dobio `Cache-Control`; grid postera prešao na
  progresivno učitavanje (40 + dodavanje pri skrolu) uz `content-visibility`
  (bez trzanja i na 900+ naslova).
- Optimizacija starta: lenji importi, `PRAGMA synchronous = NORMAL`.
- Lokacija: original ostaje na F: (zbog Windows-a), KOPIJA u `~/ai/domains/filmium`.
- AI: `ai.curator_model = qwen2.5:7b` (Ollama, GPU) — FILMIUM zadržava naziv
  `curator`/„Kurator" (to je njegov agent).

## Provereno

Import OK; server 8781 → HTTP 200; posteri se serviraju kao mali keš sa
`Cache-Control`; koren biblioteke u bazi = `/run/media/kalima/FILMIUM` (dostupan);
Electron prozor + OS handoff rade.

## Napomene

„Kurator" je namerno zadržan (FILMIUM-ov agent). SearXNG (lokalni pretraživač)
i Ollama su instalirani sistemski; VELES koristi SearXNG na 8080.
