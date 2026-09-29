---
id: filmium-c83ebde0-2026-08-08-filmium-kategorije-i-migracija-biblioteke-design-md
type: spec
domain: filmium
namespace: global
visibility: global
tier: domain
title: FILMIUM — kategorije biblioteke (Strano/Domaće/Animirano) + migracija strukture
summary: 'Datum: 2026-08-08'
keywords:
- filmium
- kategorije
- biblioteke
- strano
- domaće
- animirano
- migracija
- strukture
- docs
- superpowers
tags:
- superpowers
- specs
source_path: docs/superpowers/specs/2026-08-08-filmium-kategorije-i-migracija-biblioteke-design.md
---

# FILMIUM — kategorije biblioteke (Strano/Domaće/Animirano) + migracija strukture

Datum: 2026-08-08
Status: odobren dizajn (čeka plan implementacije)

## Cilj

Preurediti FILMIUM biblioteku oko tri kategorije sadržaja — **Strano**, **Domaće**, **Animirano** — umesto dosadašnje podele Filmovi/Serije/Animirano. Kategorija je primarni filter (sidebar), a tip sadržaja (film/serija) je sekundarni filter preko dva boolean dugmeta pored pretrage. Uskladiti fizičku strukturu na disku, bazu i tok uvoza sa ovom podelom.

Model već ima `content_category` sa vrednostima `regular` (strano), `domestic` (domaće), `animated` (animirano); vrednost se izvodi iz putanje pri uvozu. Ovaj rad NE uvodi novi pojam kategorije — preimenuje UI oko postojećeg polja i sređuje strukturu na disku.

## Finalna struktura na disku (odluka A2)

Prefiks za strano/domaće; animirano ostaje na srpskom (bez pomeranja).

| Kategorija | `content_category` | Trenutno na disku | Nova lokacija |
|---|---|---|---|
| Strani filmovi | regular | `F:\Filmovi\*` | `F:\Strano\Filmovi\*` |
| Strane serije | regular | `F:\Serije\Filmske serije\*` | `F:\Strano\Serije\*` |
| Domaći filmovi | domestic | `F:\Domaci\Filmovi\*` | `F:\Domace\Filmovi\*` |
| Domaće serije | domestic | `F:\Domaci\Serije\*` (ako postoji) | `F:\Domace\Serije\*` |
| Animirani filmovi | animated | `F:\Animirano\Filmovi\*` | bez promene |
| Animirane serije | animated | `F:\Animirano\Serije\*` | bez promene |

## Redosled izvođenja

Migracija prvo (disk → baza → kod uvoza), pa GUI. Svaka destruktivna skripta ima dry-run kao podrazumevani režim; izvršavanje samo uz eksplicitnu potvrdu. Backup baze pre DB migracije.

---

## Faza 1 — Migracija na disku

Skripta `scripts/migrate_library_layout.py`.

- Režimi: `--dry-run` (podrazumevano; ispiše plan, ništa ne menja) i `--apply`.
- Same-drive `os.rename` na nivou celog foldera (instant, atomično, reverzibilno inverznim rename-om). Bez kopiranja podataka.
- Plan pomeranja:
  1. `mkdir F:\Strano` → `rename F:\Filmovi → F:\Strano\Filmovi`
  2. `rename F:\Serije\Filmske serije → F:\Strano\Serije`, zatim ukloni prazan `F:\Serije`
  3. `rename F:\Domaci → F:\Domace` (zadržava podfoldere `Filmovi`/`Serije`)
  4. `F:\Animirano\*` netaknuto
- Sigurnost: pre svakog `rename` proveri da odredište ne postoji; ako postoji, prekid sa jasnom porukom (bez prepisivanja). Ako `F:\Serije` posle premeštanja nije prazan (neočekivani fajlovi), ne briši ga — samo prijavi.
- Izlaz: log fajl sa svim izvršenim `rename` operacijama (izvor → odredište) + generisana rollback skripta (inverzni rename-ovi) na Desktop/`.ai` (van radnog outputs foldera).
- Verifikacija posle `--apply`: nove putanje postoje, stare nema; broj foldera pre/posle po kategoriji se poklapa.

### Ograničenja
- Registovane biblioteke (library roots) u ovom trenutku su `F:\` (id 158) i `F:\Animirano\Serije` (id 281). Root 281 ostaje validan (animirano se ne pomera). Root 158 (`F:\`) ostaje validan koren; menjaju se samo podputanje.

---

## Faza 2 — Migracija baze

Skripta `scripts/migrate_library_db_paths.py`.

- Režimi: `--dry-run` / `--apply`. Pre `--apply` napravi backup `data/database/core.db.bak-<timestamp>`.
- Za svaki red u `filmium_media_sources` preslikaj prefiks u `relative_directory` (i u `root_path_snapshot` ako embeduje staru putanju):
  - `Filmovi/…` → `Strano/Filmovi/…`
  - `Serije/Filmske serije/…` → `Strano/Serije/…`
  - `Domaci/…` → `Domace/…`
  - `Animirano/…` → bez promene
  - snapshot `F:\Serije\Filmske serije` → `F:\Strano\Serije`, `F:\Domaci` → `F:\Domace`, `F:\Filmovi` → `F:\Strano\Filmovi`
- `content_category` je već tačan (regular/domestic/animated) — ne dira se; skripta samo VERIFIKUJE da nova putanja odgovara kategoriji i prijavi neslaganja.
- Idempotentno: ponovni run ne sme dvostruko da prefiksuje (proveri da putanja već nije u novom obliku).
- Verifikacija (reprodukuje logiku plejera): za uzorak po kategoriji sklopi `root.path + relative_directory + relative_path` i potvrdi da fajl postoji na disku.

### Redosled Faza 1 ↔ Faza 2
Disk prvo, pa baza (baza mora da pokazuje na već premeštene fajlove). Između faza reprodukcija ne radi — kratak prozor, prihvatljivo.

---

## Faza 3 — Tok uvoza (Uploads/import)

- `series_import_service.py` i `library_import_commit_service.py`: ciljni bazni folderi
  - domaće: `Domaci` → `Domace`
  - strano (film): koren `Filmovi` → `Strano\Filmovi`
  - strano (serija): `Serije\Filmske serije` → `Strano\Serije`
  - animirano: bez promene (`Animirano\{Filmovi,Serije}`)
- `_infer_content_mode` (izvođenje kategorije iz putanje): prepoznaj nove prefikse — `Strano`→regular, `Domace`→domestic, `Animirano`→animated. Zadrži prepoznavanje starih (`Domaci`) kao fallback dok migracija ne prođe, radi tolerancije.
- Bez promene UI toka uploads-a osim ciljnih putanja.

---

## Faza 4 — GUI

### Sidebar
- Zameni stavke `Filmovi` / `Serije` / `Animirano` sa `Strano` / `Domaće` / `Animirano`.
- Rute: `/filmium/strano`, `/filmium/domace`, `/filmium/animirano`. Svaka filtrira po `content_category` (regular/domestic/animated).

### Top bar (pored pretrage, levo)
- Dva boolean toggle dugmeta: `FILM` i `SERIJE`.
- Default: oba isključena → prikazuje sve u izabranoj kategoriji (i filmove i serije).
- Jedno uključeno → filtrira samo taj `media_type` unutar kategorije.
- Ako su oba uključena → ponaša se kao „sve" (ekvivalent oba isključena); UI može dozvoliti oba ali rezultat je unija.

### Filter hook
- `useFilmiumFilters`: dodaj `categoryFilter` (`strano`/`domace`/`animirano`/`all`). Postojeći `mediaTypeFilter` vozi FILM/SERIJE toggle (`movie`/`series`/`all`).
- `FilmiumLibraryPage`: `view` mapiran na kategoriju; renderuje `FilmiumMediaPosterGrid` (klik → detalji).

### Čišćenje
- Ukloni `FilmiumCatalog` upotrebu i za `top-rated`/`upcoming` (prebaci na poster kartice). Star admin prikaz se više nigde ne koristi.

---

## Testovi

- Faza 1: jedinični test skripte na privremenom stablu (sintetički `Filmovi/`, `Serije/Filmske serije/`, `Domaci/`, `Animirano/`) — proverava plan (dry-run) i rezultat (apply) + rollback vraća original.
- Faza 2: test migracije putanja na privremenoj bazi — prefiks korektan, idempotentnost, verifikacija kategorije.
- Faza 3: import testovi za nove ciljne putanje + `_infer_content_mode` za nove prefikse (i stari fallback).
- Faza 4: GUI testovi za `categoryFilter` + FILM/SERIJE toggle kombinacije; da `content_category` filtrira ispravno; da poster grid renderuje.

## Rizici / napomene

- Destruktivno nad celom bibliotekom (~800 foldera). Ublaženo: same-drive rename (bez kopiranja, instant, reverzibilno), dry-run podrazumevan, rollback skripta, backup baze.
- Ako korisnik naknadno želi da neki „regular" naslov bude domaći, to je ručno tagovanje (van ovog spec-a) — trenutno je samo 2 naslova `domestic`.
- Prozor nekonzistentnosti između Faze 1 i Faze 2 (disk premešten, baza još stara) — reprodukcija ne radi dok obe ne prođu; izvršavaju se zaredom.
- Projekat NIJE git repo — spec se ne commit-uje; čuva se kao fajl.
