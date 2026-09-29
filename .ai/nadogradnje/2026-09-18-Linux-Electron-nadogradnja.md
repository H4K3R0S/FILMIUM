# Nadogradnja 2026-09-18 — FILMIUM posle prelaska na Linux+Windows + Electron

> Referenca trenutne arhitekture. Migracija ZAVRŠENA.

## Pokretanje
- `start.sh` prepozna OS: Linux → Electron `cell-shell` (frameless, maksimizovan);
  nije Linux → predaje `start.bat` (Windows). WebKit fallback.
- Dva odvojena venv-a: Windows `.venv`, Linux `.venv-linux`. Port 8781.

## Biblioteka i slike
- Biblioteka + izvorne slike su na disku F: (Windows) / `/run/media/kalima/FILMIUM` (Linux).
- `os_library_bridge.py` pri startu usklađuje koren sa OS-om. Lokalni
  `data/filmium/assets` je SAMO keš (male slike); ~1804 keširano; uvoz sam kešira.
- Grid postera: progresivno učitavanje + `content-visibility` (gladak skrol).
- Asset endpoint: `Cache-Control`.

## AI
- `cell.json`: `ai.curator_model = qwen2.5:7b` (Ollama, GPU). Agent = „Kurator"
  (FILMIUM zadržava ovaj naziv; to je njegov agent).

## Lokacija
- Original na F: (zbog Windows-a), kopija u `~/ai/domains/filmium`.

## Napomene
- Detalji: `.ai/dev-log/entries/2026-09-18-linux-electron-optimizacija.md`.
- SearXNG (lokalni pretraživač) sistemski servis na 8080; koristi ga VELES.
