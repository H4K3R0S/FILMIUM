# FILMIUM — Modul 6: Torrenti

Datum: 2026-09-11
Status: odobren dizajn, čeka plan implementacije
Izvori: `NADOGRADNJE/Filmium Torrente upgrade.md`, `NADOGRADNJE/KALIMA/Filmium asistent.md` (Modul 6)

## 1. Cilj

Dodati FILMIUM domenu torrent modul koji ne skida ništa bez izričitog odobrenja
korisnika. Korisnik unosi magnet link ili `.torrent` fajl (ručno ili tako što
fajl spusti u nadzirani folder), pregleda listu fajlova unutar torrenta,
štiklira samo ono što želi, i tek tada pokreće preuzimanje. Progres se prikazuje
u realnom vremenu na FILMIUM stranici i na CORE Dashboard-u. Po završetku sistem
obaveštava korisnika i nudi uvoz u biblioteku.

## 2. Odluke i njihovi razlozi

| Odluka | Izbor | Razlog |
|---|---|---|
| Engine (prvi) | qBittorrent Web API preko `qbittorrent-api` | Vidi 2.1. Ugrađen `libtorrent` nije instalabilan u ovom venv-u, pa ide kao drugi engine posle ovoga — iza istog protokola. |
| Izvori torrenta | Bez scraper-a u v1 | Ručni unos (magnet ili `.torrent`) plus nadzirani folder pokrivaju traženi tok. Scraper po torrent indeksima ostaje mogući podmodul 6B, odvojeno. |
| Po završetku | Notifikacija i ponuđen uvoz | Ništa se ne premešta na `F:\` bez potvrde. Pogrešno prepoznat naslov inače završi na pogrešnom mestu. |
| Izolacija od korisnikovih torrenta | qBittorrent kategorija `FILMIUM` | Modul vidi i dira isključivo torrente koje je sam dodao. Torrenti koje je korisnik ručno pustio u qBittorrent-u ostaju nevidljivi i netaknuti. |
| Transport progresa | SSE | `apps/api/streaming.py` već nosi progres uvoza. WebSocket se namerno ne uvodi; progres je jednosmeran. |
| Podešavanja | SQLite, ne localStorage | Backend čita podešavanja i kada GUI nije otvoren. |

### 2.1 Zašto qBittorrent prvi

Prva odluka je bila ugrađen `libtorrent` u našem Python backendu, po
`NADOGRADNJE/Filmium Torrente upgrade.md`. Provera u projektnom venv-u
(Python 3.14.4, Windows) pokazala je da to nije izvodljivo:

```
ERROR: No matching distribution found for libtorrent
```

Na PyPI-ju ne postoje ni `libtorrent`, ni `libtorrent-rasterbar`, ni
`python-libtorrent`. Jedini pogodak je `lbry-libtorrent 1.2.4`, fork iz 2020. sa
wheel-ovima za Python 3.7 i 3.8. Python bindingovi za libtorrent na Windows-u
dolaze kroz conda-forge ili ručni build sa Boost-om — nijedno ne staje u
`pip install -r requirements.txt`.

Zamena je `qbittorrent-api` (verzija 2026.8.1, aktivno održavan). Pokriva svaki
korak odobrenog toka:

| Korak | qBittorrent poziv |
|---|---|
| Dodaj bez pisanja na disk | `torrents/add` sa `is_paused=True`, `category="FILMIUM"` |
| Lista fajlova pre skidanja | `torrents/files` |
| Neštiklirani fajlovi se ne skidaju | `torrents/filePrio` sa prioritetom `0` |
| Odobri i skini | `torrents/resume` |
| Progres, brzina, preostalo vreme | `torrents/info` (mi anketiramo, korisniku ide naš SSE) |
| Ograničenja brzine | `transfer/setDownloadLimit`, `transfer/setUploadLimit` |
| Maksimalno aktivnih torrenta | `app/setPreferences` (`max_active_downloads`) |

Cena odluke: qBittorrent mora biti instaliran i Web UI uključen. To je jedini
ručni korak koji ostaje na korisniku.

**libtorrent nije otpisan** (odluka korisnika, 2026-09-11). Ostaje kao drugi
engine iza istog `TorrentEngine` protokola, u zasebnom fajlu
`torrent_engine_libtorrent.py`, sa izborom engine-a u podešavanjima. Radi se
tek pošto qBittorrent putanja proradi od kraja do kraja, i dobija svoj spec —
tamo se rešava i kako se bindingovi uopšte dobavljaju na Windows-u (conda-forge,
ručni build sa Boost-om, ili zaseban interpreter). Protokol je namerno tako
postavljen da taj dodatak ne dira ni servis, ni rute, ni GUI.

Dobitak koji libtorrent nije imao: qBittorrent sam čuva stanje torrenta, pa nam
ne treba `resume_data` i preuzimanja preživljavaju gašenje CORE-a.

### 2.2 Lozinka Web UI-ja

Preporučeno podešavanje je qBittorrent opcija *Bypass authentication for clients
on localhost*. Tada modul ne čuva nikakvu lozinku. Polja za korisničko ime i
lozinku postoje i prazna su; ako ih korisnik popuni, vrednosti se čuvaju u
lokalnoj SQLite bazi u čistom tekstu, isto kao i ostala podešavanja. To se
izričito navodi u opisu polja u GUI-ju, da izbor bude svestan.

## 3. Arhitektura

### 3.1 Backend

Novi paket `core/domains/filmium/torrents/`:

| Fajl | Odgovornost |
|---|---|
| `torrent_models.py` | `TorrentEntry`, `TorrentFileEntry`, `TorrentProgress`, `TorrentMetadata`, `TorrentStatus`, `TorrentSettings` |
| `torrent_engine.py` | Jedini modul koji uvozi `qbittorrentapi`. Iza `TorrentEngine` protokola. |
| `torrent_repository.py` | SQLite: torrenti, fajlovi sa štikliranjem, podešavanja |
| `torrent_settings.py` | Čitanje i upis podešavanja sa podrazumevanim vrednostima |
| `torrent_watch_service.py` | Nadzor foldera preko `core/system/file_monitor` |
| `torrent_service.py` | Poslovna logika: odobravanje, prioriteti, životni ciklus |

Granica koja se poštuje: `torrent_service` ne uvozi `qbittorrentapi`, a
`torrent_engine` ne dodiruje bazu. Zahvaljujući tome sve se testira bez mreže i
bez pokrenutog qBittorrent-a.

`TorrentEngine` protokol:

```
is_available() -> EngineHealth
add(source: str, *, save_path: str) -> TorrentMetadata
list_files(info_hash: str) -> list[TorrentFileEntry]
set_file_priorities(info_hash: str, priorities: dict[int, int]) -> None
start(info_hash: str) -> None
pause(info_hash: str) -> None
resume(info_hash: str) -> None
remove(info_hash: str, *, delete_files: bool) -> None
poll_status() -> list[TorrentProgress]
apply_limits(settings: TorrentSettings) -> None
```

Implementacija `QbittorrentEngine` drži jednog `qbittorrentapi.Client`-a i jednu
daemon nit koja svake sekunde zove `poll_status()`. Petlja hvata svaki izuzetak
i upisuje ga u status torrenta; izuzetak nikada ne obara nit.

Svi pozivi idu isključivo nad kategorijom `FILMIUM`.

### 3.2 Transport

- `apps/api/torrent_runtime.py` — deljena instanca servisa, `start` i `stop` iz
  `core_lifespan` u `apps/api/main.py`
- `apps/api/routers/filmium_torrents.py` — prefiks `/api/v1/filmium/torrents`
- `apps/api/schemas/filmium_torrents.py` — Pydantic modeli

Rute:

| Metoda i putanja | Posao |
|---|---|
| `GET /` | Lista torrenta, filter po statusu |
| `POST /add` | Magnet link ili putanja do `.torrent` |
| `GET /{info_hash}/files` | Lista fajlova iz metapodataka |
| `POST /{info_hash}/approve` | Izabrani indeksi fajlova; pokreće preuzimanje |
| `POST /{info_hash}/pause`, `POST /{info_hash}/resume` | Kontrola toka |
| `DELETE /{info_hash}` | Otkazivanje, opciono brisanje fajlova |
| `GET /stream` | SSE, jedan strim za sve aktivne torrente |
| `GET /settings`, `PUT /settings` | Podešavanja modula |
| `GET /health` | `engine_available`, verzija qBittorrent-a, poruka greške |

### 3.3 Baza

Nova `core/domains/filmium/migration_v32.py`, upisana u `FILMIUM_MIGRATIONS` u
`core/domains/filmium/migrations.py` (poslednja postojeća je `V31`).

Tabele:

- `filmium_torrents` — `info_hash` (primarni ključ), `name`, `source`,
  `source_kind` (`magnet` ili `file`), `status`, `save_path`, `total_bytes`,
  `added_at`, `completed_at`, `error_message`
- `filmium_torrent_files` — `info_hash`, `file_index`, `path`, `size_bytes`,
  `selected`
- `filmium_torrent_settings` — jedan red, kolone po grupama iz odeljka 4

Stanje samih preuzimanja drži qBittorrent. Naša baza pamti šta je korisnik
štiklirao i odobrio; na startu se usklađuje sa onim što qBittorrent prijavi za
kategoriju `FILMIUM`.

### 3.4 Frontend

- `apps/gui/src/components/layout/Sidebar.tsx` — nova stavka `filmium-torrents`,
  label „Torrenti", ikona `Download`, putanja `/filmium/torrents`, smeštena
  **ispod „Kolekcije" a iznad „Istorija"** u `filmiumNavigationItems`
- `apps/gui/src/App.tsx` — ruta `torrents` unutar `FilmiumWorkspaceProvider`
- `apps/gui/src/pages/FilmiumTorrentsPage.tsx` — tabovi **Aktivni**,
  **Čekaju odobrenje**, **Završeni**
- `apps/gui/src/features/filmium/components/torrents/`:
  - `FilmiumTorrentAddBar.tsx` — unos magnet linka ili izbor `.torrent` fajla
  - `FilmiumTorrentFilePicker.tsx` — lista fajlova sa štikliranjem, veličina po
    fajlu i ukupno izabrano, dugme „Odobri i skini"
  - `FilmiumTorrentList.tsx` — red po torrentu: naziv, traka, procenat, brzina,
    preostalo vreme, seed i peer brojevi, dugmad pauza, nastavi, otkaži
- `apps/gui/src/types/filmiumTorrents.ts` — TypeScript tipovi
- `apps/gui/src/services/filmiumTorrentsApi.ts` — REST pozivi
- `apps/gui/src/features/filmium/hooks/useTorrentProgress.ts` — `EventSource`
  nad `/stream`, sa ponovnim povezivanjem
- `apps/gui/src/pages/DashboardPage.tsx` — kompaktna kartica aktivnih skidanja
  nad istim strimom (tačka 5 iz `Filmium Torrente upgrade.md`)

Stil prati postojeće FILMIUM ekrane; CSS ide u `filmium-pages.css`.

## 4. Podešavanja

Nova kategorija „Torrenti" u `apps/gui/src/pages/FilmiumSettingsPage.tsx`.

| Grupa | Polje | Podrazumevano |
|---|---|---|
| Veza | qBittorrent host | `127.0.0.1` |
| Veza | qBittorrent port Web UI-ja | `8080` |
| Veza | Korisničko ime | prazno (preporučen localhost bypass) |
| Veza | Lozinka | prazno (preporučen localhost bypass) |
| Putanje | Nadzirani folder za `.torrent` | prazno, nadzor neaktivan dok se ne postavi |
| Putanje | Odredište preuzimanja | prazno, obavezno pre prvog preuzimanja |
| Ograničenja | Maksimalna brzina preuzimanja (kB/s) | `0` (bez ograničenja) |
| Ograničenja | Maksimalna brzina slanja (kB/s) | `0` (bez ograničenja) |
| Ograničenja | Maksimalno aktivnih torrenta | `3` |
| Ponašanje | Automatski start posle odobrenja | uključeno |
| Ponašanje | Seed posle završetka | isključeno |
| Ponašanje | Obriši izvorni `.torrent` po dodavanju | isključeno |
| Filteri | Ekstenzije podrazumevano odštiklirane | `.nfo .txt .url .jpg .png .sfv` |

Ograničenja se prosleđuju qBittorrent-u pri svakom upisu podešavanja.

## 5. Tok podataka

1. Nov `.torrent` se pojavi u nadziranom folderu, ili korisnik nalepi magnet
   link. Zapis dobija status `DETECTED`.
2. Torrent se dodaje u qBittorrent **pauziran**, u kategoriji `FILMIUM`. Dok
   metapodaci ne stignu (kod magnet linkova ide preko DHT-a), status je
   `METADATA_FETCHING`. Tajmaut je 60 sekundi; po isteku status je `ERROR` sa
   porukom. `.torrent` fajl ovaj korak praktično preskače.
3. Metapodaci stižu, lista fajlova se upisuje u `filmium_torrent_files`, status
   postaje `AWAITING_APPROVAL`, korisnik dobija notifikaciju. **Na disk se još
   ništa ne piše** — torrent stoji pauziran.
4. Korisnik štiklira fajlove. Ekstenzije iz filtera dolaze unapred
   odštiklirane.
5. „Odobri i skini": neštiklirani fajlovi dobijaju prioritet `0`, torrent se
   pušta i prelazi u `DOWNLOADING`.
6. Anketa svake sekunde emituje progres kroz SSE; čitaju ga lista torrenta i
   kartica na Dashboard-u.
7. Po završetku status je `COMPLETED`, korisnik dobija notifikaciju da je film
   spreman, a putanja se predaje postojećem FILMIUM uvozu. Pregled uvoza čeka
   potvrdu korisnika; ništa se ne premešta samo od sebe.

Statusi: `DETECTED`, `METADATA_FETCHING`, `AWAITING_APPROVAL`, `DOWNLOADING`,
`PAUSED`, `COMPLETED`, `ERROR`.

## 6. Obrada grešaka

| Slučaj | Ponašanje |
|---|---|
| `qbittorrent-api` nije instaliran | `GET /health` vraća `engine_available: false`; GUI prikazuje baner; ostatak FILMIUM-a radi |
| qBittorrent nije pokrenut ili Web UI je isključen | Isto kao gore, uz poruku koja imenuje host i port iz podešavanja |
| Pogrešno korisničko ime ili lozinka | `engine_available: false` sa porukom o prijavi; podaci se ne šalju dalje |
| Nadzirani folder ili odredište ne postoji | Nadzor se ne pali, poruka imenuje putanju koja nedostaje |
| Neispravan magnet link ili `.torrent` | Zapis dobija `ERROR` sa porukom; ostali torrenti nastavljaju |
| Nema mesta na disku ili greška pisanja | Torrent prelazi u `ERROR`, poruka stoji u redu liste |
| Restart CORE-a | qBittorrent nastavlja sam; na startu se baza usklađuje sa kategorijom `FILMIUM` |
| SSE veza pukne | Klijent se ponovo povezuje uz odstupanje; lista i dalje radi kroz `GET /` |

## 7. Testiranje

Razvoj ide test-first. Testovi ne dodiruju mrežu i ne zahtevaju pokrenut
qBittorrent — koriste lažni engine koji zadovoljava `TorrentEngine` protokol.

Python (`./.venv/Scripts/python.exe -m pytest`):

- `tests/test_filmium_torrent_engine.py` — mapiranje statusa i prioriteta,
  ponašanje kada `qbittorrentapi` nedostaje ili je veza odbijena
- `tests/test_filmium_torrent_service.py` — prelazi statusa, tajmaut
  metapodataka, prioritet `0` na neštikliranim fajlovima, predaja uvozu
- `tests/test_filmium_torrent_settings.py` — podrazumevane vrednosti, čuvanje,
  validacija putanja
- `tests/test_filmium_torrent_watch.py` — detekcija novog `.torrent` fajla bez
  automatskog pokretanja preuzimanja
- `tests/test_api_filmium_torrents.py` — rute, oblik SSE događaja
- `tests/test_filmium_torrent_migration.py` — tabele i kolone iz `V32`

Vitest:

- `FilmiumTorrentFilePicker.test.tsx` — unapred odštiklirane ekstenzije, zbir
  izabranog
- `useTorrentProgress.test.ts` — tumačenje SSE događaja i ponovno povezivanje

## 8. Van obima

- Automatska predaja završenog preuzimanja postojećem FILMIUM uvozu.
  U v1 korisnik po završetku dobija notifikaciju sa putanjom, a u tabu
  „Završeni" radnja koja ga vodi na ekran uvoza (`/filmium/uploads`).
  Automatsko ubacivanje u red uvoza ostaje sledeći korak (odluka R26).
- Scraper po torrent indeksima (mogući podmodul 6B)
- RSS praćenje objava
- Ograničavanje brzine po pojedinačnom torrentu
- Automatsko premeštanje na `F:\` bez potvrde korisnika
- Moduli 5 (TMDB nadogradnja) i 7 (skener foldera) — zasebni spec dokumenti,
  redosled 6, pa 5, pa 7
