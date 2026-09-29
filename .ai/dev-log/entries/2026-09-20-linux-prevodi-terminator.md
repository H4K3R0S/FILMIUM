---
id: filmium-2026-09-20-linux-prevodi-terminator
type: log
domain: filmium
title: Linux pokretanje + reprodukcija + Terminator prevoda (popravke/opcije) + transliteracija
summary: Popravljen Linux launcher i reprodukcija (OS-most disk-probom), dopunjeni glumci (media_people), niz popravki/opcija u Terminatoru prevoda i transliteracija latinica↔ćirilica (dugme + cron posao).
status: stable
keywords: [linux, launcher, desktop, os-most, disk, mount, reprodukcija, mpv, glumci, media_people, terminator, prevodi, srt, diff, crlf, virtuelizacija, transliteracija, cirilica, latinica, cron, subtitle_script_pair]
tags: [dev-log, filmium, linux, prevodi, terminator, transliteracija, cron]
source_path: .ai/dev-log/entries/2026-09-20-linux-prevodi-terminator.md
atom_kreiran: 2026-09-20T12:20:00-04:00
atom_azuriran: 2026-09-20T12:20:00-04:00
edges:
- {type: preceded_by, target: filmium-2026-09-19-thumbnail-sistem, weight: 0.8}
---

# FILMIUM na Linuxu: pokretanje, reprodukcija, Terminator, transliteracija

Cilj dana: FILMIUM da radi na Linuxu (pokretanje ikonicom, puštanje filmova, glumci),
pa niz popravki i opcija u „Terminatoru prevoda" + transliteracija pisma.

## Pokretanje (Linux launcher) — `9dcf691`
- `FILMIUM.desktop` je pokazivao na nemontirani eksterni put (`/run/media/kalima/FILMIUM/FILMIUM/start.sh`) → „No such file". Ispravljen Exec/Icon/Path na Linux lokaciju domena (`~/ai/domains/filmium/`); instaliran u ~/Desktop + ~/.local/share/applications (trusted). Dvoklik radi (Electron cell-shell + uvicorn :4801).

## Reprodukcija filmova — OS-most (disk probom) — `8ef6252`
- Uzrok: `os_library_bridge` je koren biblioteke računao iz lokacije APLIKACIJE, a app je na sistemskom disku dok je biblioteka na ODVOJENOM „FILMIUM" NTFS disku (mount `/run/media/kalima/FILMIUM`) → upisivao `/` u bazu → `resolve_playable_video` gradio `/Strano/Filmovi/…` (nedostupno).
- Fix: `find_library_root()` nalazi disk **probom** (`<mount>/<relative_directory>` postoji), OS-neutralno; popravlja samo korene koji ne drže biblioteku; ako disk nije montiran ništa ne dira; idempotentno. Verifikovano: start sa `/` → auto-uskladi na mount (968 zapisa); playinfo/mpv rade.

## Glumci na film-stranici — `4a25d6d` (+ `bae2059` regen atoma)
- Sekcija „Glumci" (`/media/{id}/cast`) čita `filmium_media_people`, koju gradi `tmdb_people_import._regenerate_atoms` iz `cast_names` — ali samo prvih 50/boot → 127 od 833 filmova imalo glumce (preko biblioteke se nisu videli, preko glumca jesu).
- Fix: `run()` zove `_backfill_missing_media_people` (svi naslovi sa cast_names bez linkova; lokalno, bez TMDB; idempotentno). Uživo: media_people 127→933; filmovi bez glumaca 729→22.

## Terminator prevoda — popravke i opcije
- **Fiksni okvir** `82d4058`: Terminator iz drawera portalovan na `document.body` (drawer overlay ima backdrop-filter → containing block za position:fixed → okvir veći od prozora). Regresioni test cp1250+`<font>` `222d1a5`.
- **Progres + legenda** `2206acb`: batch prekodiranje pokazuje „done/total" + tanka traka; legenda kvadratića vrsta problema (kodiranje) — upaljen ako postoji, hover=naziv, klik=poveži.
- **Raspored dugmadi** `6d6120f`: Razveži (✕) levo, Prekodiraj desno od kvadratića; broj povezanih uz „Pronađeni fajlovi".
- **CRLF/LF diff** `e6c6942`: reparacija normalizuje CRLF→LF pa je diff (`split("\n")`) lažno označavao SVE redove izmenjenim i „Izmenjena verzija" panel ostajao prazan (delovalo kao da uništi ceo prevod; backend je vraćao svih 267 blokova). Diff sada deli na `/\r?\n/`.
- **↑/↓ navigacija** `7502340`: prethodni/sledeći prevod (preview) + scrollIntoView; preskače kad je fokus u textarea.
- **Virtuelizacija preview-a** `70dfbcf`→`75bba85`: prvo mereno scrollHeight (nepouzdano, ne popunjavalo/ne skrolovalo) → prešlo na **IntersectionObserver + sentinel** (rootMargin 350px). Uživo: 60→120→…→480 po skrolu.

## Transliteracija prevoda (latinica ↔ ćirilica) — `8fc97fa` + cron `cf10f93`
- `transliteration.py` (isti alat kao TMDB opisi) proširen `latin_to_cyrillic` (digrafi lj/nj/dž) + `transliterate_srt` (ne dira indeks/timecode/HTML tagove). `subtitle_transliterate.py`: detektuje pismo → nov fajl sa zamenjenim srpskim kodom (`.sr-Latn` ↔ `.sr-Cyrl`); SAMO srpski prevodi (.en/.hr… preskočeni).
- **Dugme** u Terminatoru (`→ Ćirilica`/`→ Latinica`) + endpoint `POST /subtitles/transliterate`.
- **Cron/boot posao** `subtitle_script_pair` (registrovan + daemon nit na boot-u, kao tmdb_people_import): za svaki srpski prevod bez para napravi drugo pismo; idempotentno. Uživo napravio ~1720/1767.

## Provera
Backend testovi (nove skripte): os-most, cast-backfill, cp1250+font, transliteracija (4/4), posao (3/3) — svi prolaze; ruff čist na novim modulima. GUI build (tsc/vite) čist; virtuelizacija/dugme/transliteracija verifikovani uživo u browseru/HTTP. Sve dual-copy nije potrebno (Linux domen); commitovano (15 commit-ova).

## Pravila (ai_workplace)
Dodat ZAKON „Virtuelizacija skrola" u `config_core/runtime_operations.md` + CISA lekcija `scroll-virtuelizacija` (render okvir+10%, ostatak na skrol).
