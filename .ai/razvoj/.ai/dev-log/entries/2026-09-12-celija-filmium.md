# 2026-09-12 — Sklapanje žive FILMIUM ćelije

Cilj: prvi put pustiti u pogon ono što je devet prethodnih zadataka izgradilo —
sklopiti pravu FILMIUM ćeliju na disku, preneti joj podatke u sopstvenu bazu i
dokazati da odgovara na `GET /cell/status`, bez CORE-a na putanji.

## Urađeno

Šest koraka iz `.superpowers/sdd/2026-09-12-celija-filmium-temelj/task-10-brief.md`
odrađeno redom, u privremenom folderu (`%TEMP%\celija-proba\FILMIUM`, ne `F:\` —
premeštanje na konačno mesto ostaje odluka korisnika za kasnije):

1. **Sklapanje** — `scripts/cell/build_cell.py filmium <folder> 8781` je
   sklopio ćeliju u jednom prolazu: `Ćelija sklopljena: ...FILMIUM (port 8781)`,
   izlazni kod 0, nijedan prijavljen strani uvoz (ni `find_foreign_domain_imports`
   ni `find_forbidden_module_imports` nisu našli ništa). Drugi pokušaj nad istim,
   već popunjenim folderom je, kako i treba, odbijen sa `FileExistsError` —
   provera praznog cilja radi.
2. **Uvoz bez CORE-a na putanji** — `cd` u koren ćelije pa
   `python -c "import cell_app; print(cell_app.MANIFEST.domain_id, cell_app.MANIFEST.port)"`
   je vratio `filmium 8781`, bez ijednog `ModuleNotFoundError`. `KERNEL_PYTHON_MODULES`
   i `KERNEL_GUI_MODULES` iz Task 8 su bili potpuni — nije trebalo dopunjavati
   nijedan kernel modul.
3. **Prenos podataka** — `scripts/cell/extract_domain_db.py <koren-ćelije>` je
   preneo svih 25 `filmium_*` tabela (uključujući prazne — 0 redova je i dalje
   ispravan prenos) iz `data/database/core.db` u ćelijinu `data/filmium.db`:
   `Preneto 21529 redova`, bez ijednog reda `NESLAGANJE`. Najveće tabele:
   `filmium_media_files` (8248), `filmium_episodes` (4051), `filmium_activity`
   (2111), `filmium_media_genres` (2942), `filmium_media_artworks` (1694).
   Izvorna `core.db` je ostala netaknuta (`ATTACH DATABASE` samo za čitanje,
   provereno i čitanjem `core/cell/extraction.py` pre pokretanja).
4. **Podizanje i status** — `uvicorn cell_app:app --host 127.0.0.1 --port 8781`
   u pozadini, pa `curl http://127.0.0.1:8781/cell/status` iz drugog terminala:

   ```json
   {"domain_id":"filmium","name":"FILMIUM","domain_version":"0.1.0",
    "kernel_version":"0.1.0","port":8781,"operating_system":"windows",
    "node_name":"DESKTOP-0FK92N6",
    "database_path":"C:\\Users\\Game Centar\\AppData\\Local\\Temp\\celija-proba\\FILMIUM\\data\\filmium.db",
    "rag_enabled":false,"rag_namespace":"cell:filmium","pending_upgrades":0}
   ```

   `database_path` pokazuje na ćelijinu sopstvenu bazu, ne na deljeni
   `data/database/core.db` — ćelija je stvarno odvojena. Server je posle
   provere zaustavljen (`taskkill` nad procesom sa porta 8781); nijedan server
   nije ostao da radi.
5. **CORE nepromenjen** — pun `pytest tests/ -q`: `1 failed, 2239 passed,
   38 skipped, 1 warning`, identično zatečenom stanju pre ovog plana
   (jedini pad je poznat i nepovezan: `test_dependencies.py::test_every_installable_dependency_has_install_script`,
   `tauri-plugin-global-shortcut` bez unosa u `INSTALL_SCRIPTS` — ne dira se).
6. **Ovaj upis** + commit.

## Nalazi

Nijedan defekt nije otkriven. Svih šest koraka je prošlo iz prve, bez izmena u
`core/cell/build.py` ili drugim izvorima — Task-ovi 1-9 su ćeliju već ispravno
pripremili (kernel spisak, crna lista uvoza, prepisivanje `import_guard`-a,
`persona_store`-a i `curator_runtime`-a, izdvajanje domenskih tabela po
prefiksu). Nijedan kernel modul nije trebalo dodati.

## Sledeće

Sledeći plan (`docs/superpowers/plans/`) pokriva ono što je ovaj plan namerno
ostavio po strani:
- GUI ćelije (Vite build i serviranje iz ćelijskog FastAPI-ja);
- CORE Settings ekran „Ćelijski sistem" (tabela `cells`, skeniranje foldera,
  „Poveži / Dodaj domen");
- Beleške o nadogradnji (`cell_upgrade_notes`, `POST /cell/upgrades`, pozadinski
  radnik na 900 sekundi);
- RAG nad `.ai/atomi/` (prostor imena `cell:filmium`);
- Sopstveni git repozitorijum ćelije;
- Tabela komandi koje Kurator sme da izvrši nad bibliotekom;
- Brisanje FILMIUM koda i tabela iz CORE repoa — tek kad ćelija odradi pun
  ciklus rada uživo (ovaj upis dokazuje da se diže i odgovara, ne da je već
  u produkcionoj upotrebi).

## Napomene/odluke

- Sklapanje je rađeno isključivo u privremenom folderu pod `%TEMP%`, nikad na
  `F:\` — premeštanje na konačno mesto je odluka korisnika, van ovog plana.
- Ništa nije obrisano iz repoa; `data/database/core.db` je čitana samo za
  čitanje (`ATTACH DATABASE`), nijedan upis u nju nije izveden.
- Probni folder (`%TEMP%\celija-proba`) je privremen i ne ulazi u repo; nestaje
  sam kad korisnik očisti temp, ili ga korisnik premešta na `F:\` kad odluči.

## Dopuna 2026-09-13 — ćelija na `F:\FILMIUM\`

Po odluci korisnika ćelija je ponovo sklopljena na konačnom mestu, posle
završnog talasa popravki (commit `7a9c51d`: pre-commit brana za tajne,
nedestruktivan smudge filter, `dependencies.py` kao domenska žica, izvedena
crna lista uvoza, izvorna baza otvorena preko read-only URI-ja).

- **Sklapanje:** `build_cell.py filmium F:/FILMIUM 8781` — izlazni kod 0, bez
  stranih i zabranjenih uvoza. Ćelija nosi i `config/tmdb.json` sa isključivo
  rezervisanim vrednostima; pravi TMDB ključ se u ćeliju ne prenosi i unosi se
  ručno.
- **Uvoz bez CORE-a:** `import cell_app` iz korena ćelije vraća
  `filmium 8781 F:\FILMIUM\data\filmium.db`.
- **Podaci:** preneto 21529 redova u 25 tabela; `verify_extraction` bez
  neslaganja; `PRAGMA integrity_check` vraća `ok`; biblioteka broji 856 filmova
  i 110 serija; u bazi ćelije nema nijedne `core_` tabele osim
  `core_schema_migrations`, i to samo sa 35 zapisa za `scope='filmium'`.
- **Server:** `uvicorn cell_app:app` iz `F:\FILMIUM` — `GET /cell/status`
  vraća 200 sa `database_path` `F:\FILMIUM\data\filmium.db`. FILMIUM rute
  (npr. `/api/v1/filmium/media`) vraćaju 404, jer routeri domena još nisu
  montirani u `cell_app.py` — to je posao sledećeg plana, zajedno sa GUI-jem.
- **Veličina:** 5.2 MB ukupno, od toga 3.2 MB baza.

Stara probna ćelija iz `%TEMP%\celija-proba` je uklonjena — zamenjena je ovom.
CORE i dalje radi nad sopstvenom `core.db`; FILMIUM tabele u njoj nisu dirane.

## Dopuna 2026-09-13 — GUI i API ćelije

FILMIUM ćelija na `F:\FILMIUM\` sada jednim `start.bat`-om diže proces na
`127.0.0.1:8781` koji služi i ceo FILMIUM API i FILMIUM GUI, i otvara browser na
`http://127.0.0.1:8781/#/filmium`. Dok je taj prozor otvoren, API je dostupan i
CORE-u na istom portu. Plan: `docs/superpowers/plans/2026-09-13-celija-filmium-gui-api.md`.

**Šta je izgrađeno.**
- `lib/pathPicker.ts` i `lib/tauriRuntime.ts`: biranje foldera radi i u Tauri
  prozoru (pravi dijalog) i u browseru (unos putanje); glas i biranje putanje
  prepoznaju Tauri bez uvoza CORE window manager-a.
- FILMIUM rute su izdvojene u `features/filmium/filmiumRoutes.tsx` i dele ih CORE
  i ćelija.
- Poseban GUI ulaz ćelije (`cell.html`, `src/cell/`) sa dve zamene CORE-only
  modula iz jedne mape (`cell-substitutions.json`): Kurator chat razgovara sa
  FILMIUM Kuratorom, a podešavanja nemaju API ključeve, izbor modela ni CORE chat.
  Vite build pada ako zamenjeni CORE modul ipak uđe u paket.
- Python računa zatvorenje GUI uvoza (120 izvornih fajlova) i odbija sklapanje ako
  uđe window manager, CODIUM ili CORE podešavanja; komentari ne mogu da lažno
  uvuku fajl.
- `cell_app.py` preusmerava putanje pre uvoza routera, montira 16 FILMIUM routera,
  `/cell/personas` i GUI build na `/`.
- Sklapanje kopira GUI izvor, `public/` statiku, trimovan `package.json` i gotov
  `gui/dist` (154 fajla). `--update` sklapa novi kod u privremeni folder pored
  ćelije i tek posle potpunog uspeha ga zamenjuje; pad na bilo kom koraku vraća
  ćeliju u prethodno stanje, a prekinut proces se oporavlja pri sledećem pokretanju.
  `data/` i `config/` se ni u jednom slučaju ne diraju.

**Provera uživo na F:\FILMIUM.**
- `--update` je dva puta prošao (drugi put posle popravke Kuratora), po 13 s.
- SHA-256 baze `F:\FILMIUM\data\filmium.db` je isti pre i posle oba ažuriranja
  (`f017229e…298f`); pomoćni folderi `.FILMIUM.staging` i `.FILMIUM.old` nisu
  zaostali.
- `/cell/status`, `/api/v1/filmium/media` (966 naslova), `/api/v1/filmium/genres`,
  `/cell/personas` i `/` vraćaju 200.
- U browseru: katalog prikazuje 966 naslova (uključujući „The Hunger Games"),
  podešavanja ćelije imaju Kurator, Personu, Prikaz i Torrente bez API ključeva i
  AI modela, nema CORE sidebar-a ni drugih domena, i nijedan zahtev ne ide na
  `:8000`.
- Kurator chat u GUI-ju vraća uputstvo i najbliže naslove.

**Nalazi tokom provere.**
- Kurator je vraćao HTTP 500 jer je `ai.curator_model` u novoj ćeliji prazan.
  Popravljeno u `core/cell/ai.py` (`CellCuratorService`): umesto greške vraća
  uputstvo da se model upiše u `cell.json`, uz najbliže naslove.
- Plakati i pozadine (`/api/v1/filmium/assets/posters/{id}/poster.jpg`) vraćaju
  404 i u ćeliji i u CORE-u: folder `data/filmium/assets` ne postoji nigde na ovoj
  mašini, a CORE-ov `MediaAssetService` za iste putanje vraća `None`. To je
  zatečeno stanje, nije kvar ćelije, i traži zasebnu proveru gde su slike nestale.

**Stanje testova.** Pytest: 2299 prolaza, 1 zatečen pad
(`test_every_installable_dependency_has_install_script`, nema veze sa ćelijom).
Vitest: 151 fajl, 1021 test, 0 padova.

**Šta ostaje.** CORE Settings ekran „Ćelijski sistem", beleške o nadogradnji,
RAG nad `.ai/atomi/`, sopstveni git repozitorijum ćelije, i upis Ollama modela u
`F:\FILMIUM\cell.json` da Kurator stvarno odgovara.

### Završni pregled grane i popravke (2026-09-13)

Finalni pregled cele grane je našao dve kritične stvari, i obe su popravljene pre
nego što je ćelija ostavljena na `F:\FILMIUM`:

- **Bezbednost.** Ćelija je imala `CORS allow_origins=["*"]` bez provere `Host`
  zaglavlja, ispred oko 94 FILMIUM rute koje menjaju stanje (kopiranje fajlova,
  torrenti, pokretanje VLC-a, izmena persone). Web stranica otvorena u običnom
  browseru je mogla da ih pozove, a DNS rebinding je zaobilazio CORS. Ćelija sada
  nema CORS uopšte (GUI je isti origin, CORE je zove sa servera), a
  `TrustedHostMiddleware` propušta samo `127.0.0.1` i `localhost`. Provereno uživo:
  tuđi `Host` dobija 400, tuđi `Origin` ne dobija `access-control-allow-origin`.
- **GUI izvor u ćeliji nije mogao sam da se izbuilduje** — kopirani fajlovi su
  uvozili zamenjene CORE module koji u ćeliji ne postoje. Zamena se sada primenjuje
  pre razrešenja uvoza (i u Vite pluginu i u Python zatvorenju), sklapanje proverava
  da se izvor u ćeliji razrešava sam, a ručna proba je potvrdila da build iz same
  ćelije daje isti izlaz kao build iz repoa.

Uz to je `--update` postao bezbedan za podatke koje će sledeći koraci smeštati u
ćeliju: menja **samo** generisane putanje (kod, `gui/src`, `gui/dist`, `.ai/CLAUDE.md`
…), a `.ai/atomi/`, `.ai/nadogradnje/`, `.git`, `gui/node_modules`, `data/`, `config/`
i sve ostalo ostaje. Završena zamena ostavlja marker, pa zaključana rezervna kopija
ne blokira buduća ažuriranja; neuspelo vraćanje ne skriva prvobitnu grešku.
Ažuriranje odbija da radi dok je ćelija upaljena. Zabranjeni CORE moduli se
proveravaju i u Vite grafu, a `gui/package.json` ćelije nosi tačne instalirane
verzije.

Ponovno postavljanje na `F:\FILMIUM` posle popravki: SHA-256 baze nepromenjen,
sve rute 200, katalog od 966 naslova u browseru, Kurator odgovara, nijedan zahtev
na `:8000`. Pytest 2324 prolaza uz 1 zatečen pad; Vitest 1021/1021.

## 2026-09-13 — Tauri prozor ćelije + sopstveni .venv (uživo na F:\FILMIUM)

Ćelija se sada otvara kao Tauri prozor (kao CORE), ne kao browser tab. Jedan exe
(`apps/cell-shell`, izgrađen jednom, kopira se u ćeliju kao `<IME>.exe`) čita
`cell.json`, diže API iz sopstvenog `.venv`-a ćelije ako ne radi, i otvori prozor
na `http://127.0.0.1:<port>/#/<domain>`. `start.bat` više ne zove `python -m
uvicorn` (otud raniji „No module named uvicorn" — sistemski Python nije imao
zavisnosti); sada pokreće `<IME>.exe`, a exe sam diže API iz `.venv`-a.

Ćelija nosi sopstveni `.venv` (`core/cell/venv.py`, pravi ga `build_cell.py` iz
baznog Pythona po otisku `requirements.txt`); `--update` ga nikad ne dira —
korisnički prostor. `requirements.txt` se izvodi iz stvarnih uvoza ćelije
(`core/cell/requirements.py`).

**Nađen i ispravljen bug pri živoj proveri:** `integrations/translator` je u
`CELL_EXTRA_PACKAGES` (Task 1), pa se sklapa u ćeliju, ali `generated_on_update`
(politika koju `--update` prenosi) nije imao koren `integrations` — svež build je
radio, ali `--update` na postojeću ćeliju nije unosio `integrations/`, pa je
auto-update ruta padala sa `ModuleNotFoundError`. Politika sada izvodi korene iz
`CELL_EXTRA_PACKAGES` (jedini izvor), uz regresioni test.

Uživo na `F:\FILMIUM` (port 8781), kroz `FILMIUM.exe`:
- SHA-256 baze nepromenjen pre i posle `--update`.
- `.venv` `created`; `uvicorn 0.51.0`, `fastapi 0.139.2`, `deep_translator` uvoze se.
- Proces na 8781 pokrenut kao `F:\FILMIUM\.venv\Scripts\python.exe -m uvicorn`
  (running image je bazni Python samo zbog venv redirector-a; `sys.prefix` =
  `F:\FILMIUM\.venv`). Prozor `FILMIUM`, `data/logs/api.log` postoji.
- `/api/v1/filmium/media`, `/cell/personas`, `/` → 200; tuđi `Host` → 400.
- `POST /media/1956/auto-update` → 200, bez `ModuleNotFoundError` u `api.log`.
- Plakati/backdrops sada većinom 200 (rezerva na izvorne slike u F: biblioteci
  služi original kad optimizovani keš u `data/filmium/assets` ne postoji).
- Zatvaranje prozora (`CloseMainWindow`) ugasi shell i CEO lanac API procesa
  (redirector + uvicorn), port 8781 slobodan.

Namerno van ovog plana: CORE Settings „Ćelijski sistem", beleške o nadogradnji,
RAG nad `.ai/atomi/`, autentifikacija ruta (pre bilo kakvog vezivanja van
127.0.0.1), Tauri installer/potpis, ponovno pravljenje keša plakata.

## 2026-09-13 (nastavak) — Sidebar/stil ćelije, pozicija prozora, posteri/backdrops

- **GUI ćelije dobio FILMIUM sidebar i stil.** Ćelija je renderovala samo rute bez
  okvira; sada `CellApp` obmotava rute u `CellShell` + `CellSidebar` (iste App.css
  klase = isti izgled), brend „FILMIUM", gornji rail samo FILMIUM (početna +
  podešavanja), dno „CORE Offline" dok se ne spoji. FILMIUM nav izvučen u deljeni
  `features/filmium/filmiumNav.tsx` (jedini izvor za CORE Sidebar i CellSidebar).
- **Prozor se otvara u gornjem levom uglu** (`apps/cell-shell/src/lib.rs`:
  `.center()` → `.position(0,0)`; potvrđeno Win32 GetWindowRect Left=0 Top=0).
- **Posteri/backdrops.** Dijagnoza: DB je bio zastareo — `filmium_media_artworks`
  je popunjavan samo pri prvom uvozu; posteri koje je korisnik dodao naknadno i
  serije nikad nisu ušli.
  - **Filmovi:** `rescan` je osvežavao samo indeks fajlova, ne artwork. Sada
    `MediaSourceService` prima `ArtworkSyncService` i po rescan-u sinhronizuje
    source artwork iz svežeg skeniranja. Backfill preko svih 967 izvora → posteri
    filmova (uklj. Annihilation i ostale koje je korisnik dopunio) vraćaju 200
    kroz source-fallback na originale u F: biblioteci.
  - **Serije:** idu kroz postojeći season-aware put (`refresh_media` →
    `apply_series_artwork`), koji pravi managed keš u `data/filmium/assets`
    (serija + po sezoni) i puni `filmium_seasons.poster_path/backdrop_path`.
    `apply_series_artwork` je preskakao regeneraciju kad je `poster_path` bio
    upisan iako keš datoteka ne postoji — ispravljeno (`_needs_refresh` regeneriše
    i kad managed fajl fali). Backfill 110/110 serija → posteri/backdrops (i
    sezonski) 200; GUI prikazuje sve.
  - Film = jedan poster/backdrop po izvoru (potvrđeno ispravno); serije nose
    sezonske slike kroz sezonski mehanizam, ne kroz movie rescan.
