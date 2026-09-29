---
id: filmium-c881e803-2026-08-09-filmium-auto-update-design-md
type: spec
domain: filmium
namespace: global
visibility: global
tier: domain
title: FILMIUM Auto Update — dizajn
summary: 'Datum: 2026-08-09'
keywords:
- filmium
- auto
- update
- dizajn
- docs
- superpowers
- specs
tags:
- superpowers
- specs
source_path: docs/superpowers/specs/2026-08-09-filmium-auto-update-design.md
---

# FILMIUM Auto Update — dizajn

Datum: 2026-08-09
Status: predlog (čeka pregled)

## 1. Cilj

U editoru sadržaja (FILMIUM → Detalji → Uredi sadržaj) zameniti dugme
„Dopuni preko TMDB" novim dugmetom **„Auto Update"** koje jednim klikom, na
serverskoj strani, kompletno dopuni jedan naslov iz TMDB-a, prevede/uredi
opis i naslov, popuni ključne reči i **snimi sve u bazu**. Isti postupak mora
biti dostupan i kao masovni (bulk) posao koji se pokreće komandom
`/update-filmium` iz glavnog searcha, radi u pozadini „polako", preživljava
gašenje i ponovno pokretanje aplikacije, i vidljiv je kroz indikator u donjem
desnom uglu na CORE nivou.

## 2. Kontekst i nalazi iz istrage

Analiza postojećeg stanja i baze (`data/database/core.db`, 893 stavke):

- **Editor ČITA iz baze.** Vezana polja (`title`, `original_title`,
  `release_year`, `studio`, `director`, `cast_names`, `notes`, `genres`,
  `rating`, `watch_status`) se pune iz `item` objekta koji dolazi iz
  `GET /api/v1/filmium/media`. Primer: John Wick 1–4 (id 1154–1157) imaju pun
  podatak i prikazuju se ispravno.
- **Ima 121 stavki sa praznim metapodacima** (samo naslov, npr. „John Wict 5 -
  Balerina", id 1158: `original_title=NULL`, opis prazno, `cast=[]`,
  `keywords=[]`, ima poster + godina 2026). Za njih editor tačno prikazuje —
  nema šta da pokupi.
- **TMDB dopuna promašuje kod iskrivljenih naslova.** Pretraga ide sa
  `original_title or title` + godina. Za „John Wict 5 - Balerina" (2026) TMDB
  vraća `matched=false` jer je pravi naslov **`Ballerina` (2025)**. Dokazano:
  `enrich_movie("Ballerina", 2025)` pogađa, `enrich_movie("John Wict 5 -
  Balerina", 2026)` vraća `None`. Treptavi tekst na dugmetu je poruka
  „TMDB nije pronašao ovaj naslov".
- **Postojeće dugme ne snima.** `runTmdbEnrich` puni samo prazna polja u formi
  klijentski; bez „Sačuvaj" ništa ne ide u bazu.
- **Neka polja su mock hardkod** (Tehnika: „4K/MKV/H.265…"; ocene IMDb/TMDB/
  Rotten; engleski naslov; domaći naslovi SR/HR/BS; „Mood tagovi") — ne čitaju
  bazu uopšte.

Zaključak: potrebna je robusnija TMDB pretraga (čišćenje naslova + fallback bez
godine + ručni override naziv/ID), obavezno snimanje u bazu, i vezivanje
polja koja imaju kolonu u bazi.

### Postojeća infrastruktura koja se koristi

- `core/domains/filmium/tmdb_client.py` — `enrich_movie(title, year)`,
  `enrich_series(title, year)`; enrichment već nosi `keywords` i `collection`;
  jezički lanac `sr-RS → hr-HR → bs-BA → en-US`.
- `core/domains/filmium/repository.py` + `service.py` — `update` (SELECT *,
  puno mapiranje), `update_keywords`.
- `integrations/translator/service.py` — `TranslatorService` (deep-translator,
  bez ključa, podržava `bs`), rate limiter (1/s), backoff.
- `apps/api/routers/filmium.py` — `POST /media/{id}/tmdb-enrich`,
  `PUT /media/{id}`, `POST /media/{id}/keywords`.
- `apps/api/main.py` — `core_lifespan` (mesto za resume na startu).
- Frontend: `FilmiumEditorPanel.tsx` (dugme + „Mood tagovi"),
  `FilmiumTopBar.tsx` (glavni search), `AppShell.tsx` (CORE okvir),
  `FilmiumKeywordsBox.tsx` (već postoji UI za ključne reči u detaljima).

## 3. Odluke (potvrđene sa korisnikom)

1. **Cron motor:** zaseban Python proces (ne asyncio unutar API-ja).
2. **Bulk obim:** obradi samo nedostajuće/nekompletne stavke; ćirilicu uvek
   transliteriraj.
3. **Postojeći latinični domaći opis:** ostavi ga; prevod EN→SR (pa latinica)
   samo kad je
   domaći opis prazan.
4. **Epizode:** samo TMDB metapodaci, bez prevoda/transliteracije opisa.

## 4. Arhitektura — pregled

Jedna deljena serverska pipeline funkcija (`auto_update_item`) je izvor
istine. Koriste je i (a) dugme „Auto Update" preko novog endpointa i (b) bulk
cron proces. Sve promene se perzistiraju u bazu unutar pipeline funkcije.

```
Editor „Auto Update"  ┐
                      ├─→ POST /media/{id}/auto-update ─→ auto_update_item() ─→ DB
Bulk cron proces ─────┘        (jedan po jedan, sleep)
        ▲
        │ start/stop/status + resume na startu
 /update-filmium (glavni search)      core_lifespan → resume_if_active()
        │
 CronStatusIndicator (donji desni ugao, CORE nivo) ← GET /status (polling)
```

## 5. Moduli

### M1 — Transliteracija (`core/domains/filmium/transliteration.py`)

Čist, deterministički, bez mreže.

- `is_cyrillic(text: str) -> bool` — `True` ako tekst sadrži ćirilične znakove
  (opseg U+0400–U+04FF).
- `cyrillic_to_latin(text: str) -> str` — srpska ćirilica → latinica, uključi
  digrafe: Љ→Lj, Њ→Nj, Џ→Dž, Ђ→Đ, Ж→Ž, Ч→Č, Ћ→Ć, Ш→Š, Đ/Ž/Č/Ć/Š mala slova,
  i očuvanje velikog/malog slova (Љ→Lj, ЉЕ→LJE heuristika: sledeće slovo veliko
  → sve veliko). Ne-ćirilične znakove propušta netaknute.

Testovi: prazan string, čist latinski (nepromenjen), digrafi, mešano, velika
slova.

### M2 — Proširenje prevodioca (`integrations/translator/service.py`)

- `translate_pair(title, overview, *, target="sr") -> tuple[str, str]` — spoji
  naslov i opis jednim delimiterom (`"\n⟐⟐⟐\n"`), pošalji **jedan**
  `translate` poziv (EN→target), pa rasparčaj nazad. Ako broj delova ne
  odgovara, fallback: dva odvojena `translate` poziva. Prazan ulaz vraća prazan
  izlaz.
- Google prevod na `sr` vraća **ćirilicu**; zato pipeline (M4) uvek propušta
  prevedeni tekst kroz `cyrillic_to_latin` da izlaz bude srpska latinica.

Testovi: uspešan split, fallback pri lošem splitu (mock provajder), prazan
naslov ili opis.

### M3 — TMDB matching helper (`core/domains/filmium/tmdb_client.py`, dopuna)

Robusnije pronalaženje da se pokriju iskrivljeni naslovi, ručno dodati redni
brojevi i preimenovani nastavci/spin-offovi.

- `enrich_best(query_title, year, media_type, *, tmdb_id=None,
  override_title=None, collection_hint=None) -> Enrichment | None`:
  1. Ako je `tmdb_id` zadat → direktno `enrich_*_by_id(tmdb_id)` (nova
     funkcija: `movie/{id}` / `tv/{id}` + credits/keywords/`belongs_to_collection`).
  2. Inače koristi `override_title` ako postoji, pa `query_title`.
  3. **Varijante naziva** (prvi pogodak pobeđuje), da pokrijemo i „neki filmovi
     se stvarno tako zovu sa brojem, neki ne":
     - kako jeste (sa rednim brojem), sa godinom pa bez;
     - **bez vodećeg rednog broja** — skini trailing ordinal (`"(.*)\s+\d+$"`,
       npr. „John Wick 5" → „John Wick"), sa godinom pa bez;
     - **bez franšiznog prefiksa/šuma** tipa `"^.* \d+ - "` i samo poslednji
       segment posle „ - " (npr. „John Wict 5 - Balerina" → „Balerina").
  4. **Franšiza / kolekcija (cross-check za preimenovane nastavke):** ovo
     rešava slučaj kao „John Wick 5" koji je zapravo `Ballerina`.
     - Odredi bazni naziv (naziv bez rednog broja) i redni broj `N` ako postoji.
     - Izvor kolekcije, redom: `collection_hint` → `item.collection` →
       `belongs_to_collection` sa TMDB pogotka baznog naziva → TMDB
       `search/collection` na bazni naziv.
     - Ako imamo kolekciju, povuci njene delove (`collection/{id}`), sortiraj po
       datumu izlaska i izaberi po: (a) godini stavke ako je poznata, inače (b)
       `N`-tom po redu. Tako se pronalazi pravi film i kad je preimenovan.
     - Dodatni „discovery" korak (best-effort): TMDB `movie/{id}/recommendations`
       ili `similar` baznog filma, filtriraj po godini stavke.
- Best-effort automatsko; **ručni override (naziv/ID) je zagarantovani
  fallback** kad ni kolekcija ne pomogne (npr. spin-off koji TMDB ne drži u
  istoj kolekciji).

Napomena o iskrenosti: preimenovani spin-off (npr. `Ballerina`) često NIJE u
istoj TMDB kolekciji kao matična franšiza, pa automatika možda neće uvek
pogoditi — zato je ručni override naziv/ID obavezan deo toka.

Testovi (mock HTTP): pogodak sa godinom, fallback bez godine, skidanje trailing
rednog broja, čišćenje prefiksa, izbor iz kolekcije po godini i po `N`-tom
mestu, override po ID-u.

### M4 — Pipeline jednog naslova (`core/domains/filmium/auto_update_service.py`)

`auto_update_item(item_id, *, tmdb_id=None, override_title=None) ->
AutoUpdateResult`

Koraci:
1. Učitaj `item` (`service.get_media_item`).
2. `enrichment = tmdb_client.enrich_best(..., collection_hint=item.collection)`.
   Ako `None` → vrati rezultat `matched=False`, bez izmena; upiši razlog.
3. **Skalarna polja (fill-empty):** `original_title`, `english_title`,
   `release_year`, `studio`, `director`, `runtime` (ako TMDB daje),
   `rating`(tmdb) — popuni samo ako je prazno.
4. **Spoji:** `genres` i `cast_names` (unija, bez duplikata).
5. **Ključne reči:** unija `item.keywords` (postojeće) + `enrichment.keywords`
   → sačuvaj (deo istog `update` poziva; vidi §7 o kolonama).
6. **Domaći naslov (jezik/pismo)** — redosled: prvo uzmi TMDB podatke, pa
   pogledaj šta naš program ima:
   - Ako TMDB vrati domaći (srpski) naslov `enrichment.local_title` → ako je na
     ćirilici, `cyrillic_to_latin`; ako je već latinica, ostavi. Upiši u domaći
     naslov.
   - Ako TMDB **nema** domaći naslov → prevedi `english_title` (ili
     `original_title`) EN→SR i upiši kao domaći naslov (latinica).
7. **Opis (jezik/pismo)** — ista logika:
   - Ako je `notes` (domaći opis) **prazan** i postoji `enrichment.local_overview`
     → koristi ga (transliteriraj ako je ćirilica). Ako nema domaćeg ali ima
     `english_overview` → prevedi EN→SR i upiši `notes`.
   - Ako `notes` **postoji i sadrži ćirilicu** → `cyrillic_to_latin(notes)`.
   - Ako `notes` postoji i već je latinica → ostavi.
   - Naslov i opis se prevode zajedno jednim pozivom (`translate_pair`) kad oba
     traže prevod.
8. `poster/backdrop` backfill ako fale (postojeći `_persist_tmdb_visuals`).
9. **Snimi sve** (`service.update_media_item` sa spojenim payload-om +
   `update_keywords` ako je odvojen put).
10. Vrati `AutoUpdateResult{matched, changed_fields[], message}`.

`auto_update_episode(ep_id)` — samo TMDB metapodaci epizode (bez prevoda/
transliteracije), preko postojećih episode servisa.

Testovi: prazan naslov → prevod EN→SR (latinica) + snimljeno; ćirilični opis →
transliteracija; latinični opis → netaknut; promašaj → bez izmena; keywords
unija; fill-empty ne gazi postojeće.

### M5 — Endpoint pojedinačne dopune (`apps/api/routers/filmium.py`)

- `POST /media/{item_id}/auto-update` sa opcionim body-jem
  `{tmdb_id?: int, override_title?: str}` → poziva M4, perzistira, vraća
  ažuriran `MediaItemResponse` + sažetak (`AutoUpdateResponse{matched,
  changed_fields, message, item}`).

### M6 — Editor (frontend, `FilmiumEditorPanel.tsx` + `filmiumApi.ts`)

- Header dugme **„Dopuni preko TMDB" → „Updatuj"**; zove
  `autoUpdateFilmiumMedia(id, {tmdb_id?, override_title?})`; po uspehu reload
  `item` (`onSaved` → refresh kataloga) i highlight promenjenih polja.
- Kad je `matched=false`: prikaži polje **„TMDB naziv ili ID"** (override) i
  dugme „Pokušaj ponovo" koje šalje override.
- **„Mood tagovi" → „Ključne reči"**: vezati na `item.keywords` (+ korisničke
  iz `editor_settings.user_keywords`), snimati preko postojećeg keywords
  endpointa. Ukloniti mock `moodTags`.
- Vezati polja koja imaju DB kolonu a sad su mock: `englishTitle`
  (`item.english_title`), `descriptionEnglish` (`item.english_description`),
  domaći naslovi SR/HR/BS (`editor_settings.basic.local_title_*`). Tehnika i
  eksterne ocene (IMDb/Rotten/Metacritic) nemaju DB kolonu — ostaju van
  ovog dizajna (napomena za budućnost; Tehnika dolazi iz media probe).

### M7 — Bulk cron proces (`scripts/filmium_auto_update_cron.py`)

Zaseban proces, stanje u `data/filmium_auto_update/`:

- `--build` → napravi listu svih filmova, serija i epizoda (id + tip + naslov),
  snimi u `queue.json`. Ovo je „lista" koju korisnik traži.
- `--run` / `--resume` → čitaj `queue.json` + kursor iz `state.json`; obradi
  jednu stavku, `sleep(delay)` (podrazumevano nekoliko sekundi = „polako"),
  pomeri kursor, upiši `state.json`, ponovi. Filmovi/serije → M4 pun; epizode →
  `auto_update_episode` (TMDB-only). **Preskoči već kompletne** (imaju
  `original_title` + neprazan `notes` + `keywords`).
- `state.json`: `{status: idle|running|stopped|done, pid, total, cursor,
  current: {id,title}, started_at, updated_at, done_count, error_count,
  errors: [{id, reason}]}`.
- Greške po stavci → upiši u `errors[]`, nastavi (ne ruši posao).

### M8 — Menadžer cron-a (`core/domains/filmium/auto_update_cron_manager.py`)

- `start()` → ako već `running` sa živim PID-om, ne diraj; inače `--build` pa
  `subprocess.Popen([...,"--run"])` detached (`CREATE_NO_WINDOW`/
  `DETACHED_PROCESS` na Windows), upiši PID.
- `stop()` → `status=stopped`, terminiši PID ako živ.
- `status()` → pročitaj `state.json` (ili `idle` ako ga nema).
- `resume_if_active()` → ako je `status=running` a PID **mrtav** → relaunch
  `--resume`. Zove se iz `core_lifespan`.

Provera živosti PID-a: `psutil` ako postoji, inače `os.kill(pid, 0)` /
`tasklist` fallback.

### M9 — Cron API (`apps/api/routers/filmium.py` ili nov router)

- `POST /filmium/auto-update/start`
- `POST /filmium/auto-update/stop`
- `GET  /filmium/auto-update/status` → JSON iz `state.json`.
- `core_lifespan` (M-startup) dopuniti pozivom `resume_if_active()` uz
  `initialize_core_database()`.

### M10 — Glavni search komanda (`FilmiumTopBar.tsx`)

- Presresti unos: `"/update-filmium"` → `start`; `"/update-filmium stop"` →
  `stop`. Po presretanju očisti polje i ne tretiraj kao pretragu.

### M11 — CORE indikator (`CronStatusIndicator.tsx`, montiran u `AppShell`)

- Fiksiran u **donji desni ugao**, prisutan na svim rutama (CORE nivo).
- Polling `GET /filmium/auto-update/status` ~3 s. Prikazuje `done_count/total`,
  trenutni naslov, spinner; sakriven kad je `idle`/`done` (kratki „gotovo"
  toast na prelazu u `done`). Klik → mali popover sa detaljima i „Zaustavi".

## 6. Tok podataka i greške

- TMDB promašaj (posle svih varijanti + override) → stavka se preskače u
  bulku (upis u `errors[]`); u editoru se nudi ručni override.
- Prevod rate-limit → postojeći backoff; ako i dalje padne, polje ostaje kako
  je bilo (opis se ne kvari).
- Pad/gašenje procesa → `state.json` ostaje `running` sa mrtvim PID-om →
  sledeći start CORE-a ga nastavi (`resume_if_active`).
- Duplo pokretanje spregnuto PID proverom u `start()`.

## 7. Uticaj na bazu

Bez migracije šeme — sve kolone već postoje (`original_title`,
`english_title`, `english_description`, `notes`, `cast_names`, `studio`,
`director`, `keywords`, `collection`, `editor_settings`, `genres` preko
`_replace_genres`). `auto_update_item` koristi postojeći `service.update` put.
Novi fajlovi stanja su van baze (`data/filmium_auto_update/*.json`).

## 8. Testiranje

- Unit: M1 transliteracija, M2 `translate_pair` (mock), M3 matching varijante
  (mock HTTP), M4 pipeline logika (mock TMDB + translator), M7 build queue +
  resume kursora, M8 PID živ/mrtav grane.
- API: `POST /media/{id}/auto-update` (matched/unmatched/override), cron
  start/stop/status, resume na startu.
- Frontend: slash parse u TopBar, rename „Ključne reči" + vezivanje keywords,
  render indikatora (idle skriven, running vidljiv), Auto Update tok.

## 9. Van obima (za sada)

- Eksterne ocene IMDb/Rotten/Metacritic (nema DB kolone, nema izvora).
- Tehnički podaci u editoru (dolaze iz media probe, ne iz TMDB) — ostaju kako
  jesu.
- Prevod/transliteracija opisa epizoda.
- Garantovano automatsko pogađanje preimenovanih spin-offova (npr. `Ballerina`)
  — radi se best-effort kroz kolekciju/related, uz ručni override kao siguran
  fallback.

## 10. Redosled implementacije (predlog)

1. M1 transliteracija + M2 translate_pair (+ testovi).
2. M3 matching + M4 pipeline + M5 endpoint (+ testovi).
3. M6 editor (Auto Update dugme, override, „Ključne reči", vezivanje polja).
4. M7 cron skripta + M8 menadžer + M9 API + startup resume (+ testovi).
5. M10 slash komanda + M11 CORE indikator.
