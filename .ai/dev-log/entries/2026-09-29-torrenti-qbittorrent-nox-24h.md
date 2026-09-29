---
id: filmium-2026-09-29-torrenti-qbittorrent-nox-24h
type: log
domain: filmium
title: Torrenti popravljeni na Linuxu (qbittorrent-nox :8090 + autostart) + auto-uklanjanje 24h
summary: Torrenti strana je pucala jer je port 8080 zauzet SearXNG-om, qbittorrent-nox nije bio instaliran/pokrenut, a Linux podešavanja su imala Windows putanje. Instaliran qbittorrent-nox (headless) kao systemd --user servis na :8090 (localhost auth bypass), qbittorrent-api u .venv-linux, podešavanja prebačena na :8090 + Linux foldere, default porta u migraciji 8080→8090. Dodato samostalno uklanjanje ZAVRŠENIH torrenta 24h posle završetka (kartica + qBit zapis odlaze, fajlovi ostaju).
status: stable
keywords: [torrenti, qbittorrent, qbittorrent-nox, webui, port, 8090, 8080, searxng, konflikt, systemd, autostart, qbittorrent-api, venv-linux, magnet, kartica, awaiting_approval, retention, 24h, auto-remove, delete_files]
tags: [dev-log, filmium, torrenti, qbittorrent, systemd, retention]
source_path: .ai/dev-log/entries/2026-09-29-torrenti-qbittorrent-nox-24h.md
atom_kreiran: 2026-09-29T11:00:00-04:00
atom_azuriran: 2026-09-29T11:00:00-04:00
edges:
- {type: preceded_by, target: filmium-2026-09-20-linux-prevodi-terminator, weight: 0.6}
---

# Torrenti na Linuxu: qBittorrent daemon + auto-uklanjanje 24h

## Simptom
Torrenti strana: „qBittorrent nije dostupan na 127.0.0.1:8080" a u telu greške SearXNG HTML.

## Koren (dijagnostika)
1. **Port 8080 zauzet SearXNG-om** (pid worker) → FILMIUM engine dobija SearXNG stranicu i ispravno javlja da to nije qBittorrent.
2. **`qbittorrent-nox` nije instaliran** — postojao samo GUI `/usr/bin/qbittorrent`; nema pozadinskog daemona.
3. **`qbittorrentapi` nije u `.venv-linux`** (pravi Linux runtime koji Electron cell-shell spawn-uje); Windows `.venv` (sync sa `F:\`) ga IMA — odatle zabuna „u zavisnostima piše da postoji".
4. **Podešavanja imala Windows putanje** (`C:\Users\Game Centar\Videos\`, `Downloads\`) koje na Linuxu ne postoje.

## Rešenje
- `apt install qbittorrent-nox` (5.2.3); `pip install qbittorrent-api` u `.venv-linux` (bilo prisutno 2026.8.1).
- **Config** `~/.config/qBittorrent/qBittorrent.conf`: WebUI `Enabled`, `Address=127.0.0.1`, `Port=8090`, `LocalHostAuth=false` (bez lozinke sa localhost-a), `DefaultSavePath=/home/kalima/Videos`.
- **Autostart** `~/.config/systemd/user/qbittorrent-nox.service` → `ExecStart=/usr/bin/qbittorrent-nox --webui-port=8090`, `enable --now`. Diže se na loginu, čeka komande u pozadini (kao searxng/ai-router).
- **Podešavanja** (`filmium_torrent_settings` id=1): `port=8090`, prazan user/pass, `download_path=/home/kalima/Videos`, `watch_folders=(/home/kalima/Downloads,)`.
- **Migracija** `migration_v32.py`: default porta 8080→8090 (za buduće instalacije).

Tok „magnet → kartica → skidanje tek na klik" već je radio u bekendu: `add()` dodaje pauzirano (`is_paused=True`) + blokira sve fajlove (prioritet 0) → `AWAITING_APPROVAL`; `approve()` je taj klik „Preuzmi". Zapis živi u bazi, pa se odobrava kad god.

## Nova funkcija — auto-uklanjanje 24h (TDD)
`torrent_reconcile.py`: konstanta `COMPLETED_RETENTION_SECONDS = 24*3600` i metoda `_expire_completed()` u `poll()` — ZAVRŠEN torrent stariji od 24h se `remove(delete_files=False)` (kartica + qBit zapis odlaze, **fajlovi ostaju**). Bez `completed_at` se ne dira. Testovi: `tests/test_torrent_retention.py` (4, prolaze).

## Verifikacija
- `engine.is_available()` → `True / v5.2.3`.
- Živi endpoint `GET /api/v1/filmium/torrents/health` → `{"engine_available":true,"version":"v5.2.3"}` (aplikacija pokupila :8090 bez restarta).
- ruff čist; 4 testa zelena.
