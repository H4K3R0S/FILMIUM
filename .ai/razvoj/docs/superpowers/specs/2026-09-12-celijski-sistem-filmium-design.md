# Ćelijski sistem — odcepljenje domena, pilot FILMIUM

Datum: 2026-09-12
Status: odobren dizajn, čeka plan implementacije
Izvori: `NADOGRADNJE/KALIMA/arhitekturu Decentralizovanog AI OS-a i domena.md`,
`NADOGRADNJE/TODO - Prevodni Sidebar + KALIMA.md` (Faza 2)

## 1. Cilj

Pretvoriti CORE domen u samostalnu aplikaciju („ćeliju") koja živi u sopstvenom
direktorijumu na proizvoljnom disku, ima svoj GUI, svoj API, svoju bazu, svoje
zavisnosti i svoj git repozitorijum. CORE posle odcepljenja ne nosi kod tog
domena — vidi ga isključivo kroz mrežni API na portu koji je sam dodelio, i
istim kanalom mu šalje beleške o željenim nadogradnjama.

Pilot je FILMIUM. Ostali domeni dolaze tek kad prva ćelija radi.

Ćelija i domen su ovde ista stvar. Naziv „ćelija" opisuje osobinu: može da se
odcepi od većeg organizma i da mu se ponovo pripoji.

## 2. Odluke i njihovi razlozi

| Odluka | Izbor | Razlog |
|---|---|---|
| Šta ćelija nosi od CORE runtime-a | Zamrznut kernel | Puna kopija CORE-a duplira i ono što se nikad ne dira (45 routera, GUI ostalih domena). CORE kao deljena biblioteka ne daje samostalnost — ćelija bi tražila CORE na toj mašini. Kernel daje samostalnost uz jasnu, verzionisanu granicu nadogradnje. |
| GUI odcepljenog domena | Ceo GUI seli u ćeliju | Duplirani GUI na dva mesta je najskuplja stavka održavanja u celom planu. Kad se ćelija pokrene, vidi se samo njen GUI. |
| Šta CORE prikazuje posle odcepljenja | Samo kartica domena | Kartica nosi status, verziju, listu poslatih beleški i dugme za otvaranje ćelije. Nijedan FILMIUM GUI fajl ne ostaje u CORE-u. Nepovezan domen prikazuje „Poveži / Dodaj domen". |
| Sudbina koda u repou | Premeštanje uz sopstveni git | Ćelija postaje pun projekat sa izvučenom istorijom, upotrebljiv i drugima preko javnog repozitorija. Kopija koja ostaje u CORE-u vodi u dve verzije istog koda koje se razilaze. |
| Redosled izgradnje | Prvo ručno izvajan FILMIUM, pa alat | Kontrakt ćelije je trenutno pretpostavka. Generički ekstraktor napisan unapred pogodio bi pogrešan kontrakt. Alat u CORE Settings-u nastaje iz onoga što je već jednom urađeno. |
| Restrukturiranje monorepoa u pakete | Posle prve ćelije | Dira sva četiri domena, 45 routera i ceo GUI pre nego što je ijedna ćelija proradila — najveći rizik uz najmanju povratnu informaciju. |
| KALIMA skener u FILMIUM auto-uvozu | Kopija u ćeliju kao `import_guard` | Kod je samostalan (221 linija, samo standardna biblioteka). Kopija zadržava zaštitu od izvršnog fajla maskiranog u video i trajno briše jedinu međudomensku nit. |
| Povezivanje CORE sa ćelijom | Skeniranje zadatog direktorijuma | Traži se `cell.json`. Korisnik bira gde se skenira; ništa se ne pogađa. |
| Dodela porta | CORE dodeljuje pri odcepljenju | Ćelija ne bira sama; sudari portova se rešavaju na jednom mestu. Port se upisuje u `cell.json`. |
| AI sloj u ćeliji | Samo Ollama klijent i persone | FILMIUM Kurator zavisi od `core/ai` (1711 linija), `core/integrations` i `core/security.secrets`. Ćelija nosi samo `ollama_client.py`, `persona_store.py` i `personas.py` (~350 linija); model i endpoint stoje u `cell.json`. Konektori, ključevi i biranje modela iz CORE registra ostaju u CORE-u. |
| Beleške o nadogradnji | Pišu se i u CORE-u i u ćeliji | Beleška mora da preživi period dok je ćelija ugašena, a mora i da bude čitljiva u samoj ćeliji kad se otvori bez CORE-a. |

## 3. Zatečeno stanje (mereno 2026-09-12)

Merenja koja opravdavaju obim:

- `core/domains/filmium/` — 119 fajlova, **nula import-a ka drugim domenima**.
- FILMIUM u `apps/api`: 16 routera i 4 runtime modula
  (`auto_import_runtime`, `torrent_runtime`, `curator_runtime`, `disk_runtime`).
- FILMIUM u `apps/gui/src/features/filmium/`: 144 fajla. Van svoje fascikle
  uvozi **samo 5 deljenih modula**: `services/httpClient`, `lib/sound`,
  `lib/useCoreSetting`, `components/chat/CoreChat`,
  `components/chat/CoreAssistantChat`.
- `data/database/core.db` ima 30 tabela; **25 su FILMIUM-ove**. Van FILMIUM-a
  ostaju samo `core_connectors`, `core_model_allowlist`,
  `core_model_visibility` i `core_schema_migrations`.
- Migracije već nose `scope="filmium"` (v1 naviše), pa mehanizam
  `apply_database_migrations` ne mora da se menja.
- `core/foundation/config.py` je 33 linije hardkodovanog dataclass-a; učitavanja
  `.env` nema nigde u `core/`. Konfiguracija ćelije se gradi na praznom.
- Jedina međudomenska nit: `apps/api/auto_import_runtime.py` uvozi
  `core.domains.kalima.security.FileScanner`. Domenski kod od nje ne zavisi —
  `auto_import_service.py:23` definiše `SecurityScanner` kao ubrizgan poziv.

Zaključak merenja: FILMIUM je već skoro razdvojen. Posao je pretežno premeštanje
i preusmeravanje putanja, a ne raspetljavanje zavisnosti.

## 4. Anatomija ćelije

```
F:\FILMIUM\
  cell.json            manifest ćelije
  .ai\                 uputstva i opis domena za AI (odeljak 10)
  kernel\              zamrznut CORE kernel (odeljak 5)
  domain\              domenski kod (danas core/domains/filmium)
  api\                 routeri i runtime moduli domena
  gui\                 GUI domena, 5 deljenih modula i shell
  data\                filmium.db, artwork, logovi
  tests\               testovi domena i ćelije
  requirements.txt     zavisnosti domena
  start.bat            pokretanje (API i GUI)
```

`cell.json` sadrži: `id`, `name`, `domain_version`, `kernel_version`, `port`,
`core_url`, `created_at`, `detached_from` (commit iz kog je ćelija izvučena).

## 5. Granica kernela

U `kernel\` ulazi, zamrznuto i verzionisano:

- Python: `foundation/{config, paths, context, errors, logging, lifecycle,
  runtime, dependencies, installer}`, `database/{connection, migrations,
  runtime}`, `system/file_monitor`, `rag/` (opcion podsistem, odeljak 10.2),
  `ai/{ollama_client, persona_store, personas}` (za Kuratora, odeljak 5.1),
  i okresana FastAPI skela izvedena iz `apps/api/main.py` (lifespan, CORS,
  registracija routera).
- GUI: `services/httpClient`, `lib/sound`, `lib/useCoreSetting`,
  `components/chat/CoreChat`, `components/chat/CoreAssistantChat`, plus shell
  (sidebar, teme, osnovni CSS).

`kernel_version` stoji u `cell.json`. Nadogradnja kernela je zasebna stavka u
listi nadogradnji ćelije, odvojena od nadogradnji domena.

Šta kernel ne nosi: routere drugih domena, ostatak `core/ai`,
`core/integrations`, `core/security`, `core/agents`, `core/roadmap`,
`core/finansije`, domene.

### 5.1 Kurator u ćeliji

`CuratorService` (184 linije) prima registry, `generate` poziv i retriever kao
ubrizgane zavisnosti, pa domenski kod ostaje nepromenjen. U CORE-u ga snabdeva
`core_ai_runtime` sa punim registrom modela; u ćeliji ga snabdeva tanak sloj
koji čita `ai.endpoint` i `ai.curator_model` iz `cell.json` i zove lokalnu
Ollamu. Persone se čitaju iz `persona_store`-a, koji je fajl-baziran i ne
trazi bazu.

Tabela komandi koje model sme da izvrši nad bibliotekom (pretraga i prikaz
filmova) još ne postoji ni u CORE-u; to je budući posao, van ovog spec-a.

## 6. Baza

FILMIUM tabele se izvlače iz deljene `data/database/core.db` u
`F:\FILMIUM\data\filmium.db`.

Postupak izvlačenja:

1. Kreirati praznu `filmium.db` i pustiti FILMIUM migracije (v1 naviše) da je
   izgrade — šema tako nastaje istim kodom koji je i do sada gradi.
2. Preneti sadržaj svih 25 `filmium_*` tabela.
3. Preneti redove iz `core_schema_migrations` za `scope='filmium'`, inače bi
   ćelija pri sledećem pokretanju pokušala da ponovi već primenjene migracije.
4. Provera: broj redova po tabeli u izvoru i odredištu mora biti jednak.

`core_database_connection` u kernelu čita putanju iz `cell.json` umesto iz
`core_paths.core_database`.

U CORE-u tabele **ostaju netaknute** dok ćelija ne dokaže rad. Njihovo brisanje
je zaseban, kasniji korak i nije deo ovog spec-a.

## 7. `import_guard` — kopija skenera u ćeliju

`core/domains/kalima/security/` (`file_scanner.py`, `hash_checker.py`,
`quarantine_service.py`, `security_models.py`, ukupno 221 linija) kopira se u
ćeliju kao `domain/import_guard/`. Kod zavisi samo od standardne biblioteke, pa
kopija radi bez izmena osim putanja uvoza.

Ćelija ubrizgava `import_guard.status_for(path)` u `AutoImportService` na mestu
gde je do sada stajao KALIMA adapter. Posle toga ćelija nema nijedan uvoz ka
drugom domenu.

KALIMA u CORE-u zadržava svoju kopiju; dve kopije su namerne i od tog trenutka
nezavisne.

## 8. Veza CORE i ćelije

CORE Settings → Nadogradnje → **Ćelijski sistem**.

- **Dodaj domen**: korisnik bira direktorijum; CORE ga skenira tražeći
  `cell.json` (uključujući jedan nivo poddirektorijuma). Nađena ćelija se upisuje
  u novu tabelu `cells` u `core.db`: `id`, `domain_id`, `path`, `port`,
  `kernel_version`, `domain_version`, `last_seen`, `status`.
- **Zdravlje**: `GET /cell/status` na portu ćelije. Vraća naziv, operativni
  sistem, verzije, aktivan radni prostor i broj neprimenjenih beleški. Ime je
  namerno različito od postojećeg `/status` u `apps/api/routers/system.py`.
- **Nepovezan domen**: CORE strana domena prikazuje karticu sa dugmadima
  „Poveži" i „Dodaj domen", bez ijedne strane tog domena.
- **Povezan domen**: kartica prikazuje status, verzije, listu poslatih beleški i
  dugme „Otvori ćeliju" koje otvara GUI ćelije na njenom portu.

Mrežni saobraćaj ide isključivo preko `http://<host>:<port>`; timeout 5 sekundi
na svaki poziv, da nedostupna ćelija nikad ne blokira CORE.

## 9. Beleške o nadogradnji

Tok:

1. U CORE-u korisnik piše belešku za domen (šta želi da se promeni). Upisuje se
   u tabelu `cell_upgrade_notes` (`id`, `domain_id`, `text`, `created_at`,
   `status` sa podrazumevanom vrednošću `PENDING`).
2. Ako je ćelija povezana, beleška odmah ide na `POST /cell/upgrades`. Uspeh
   (HTTP 200) menja status u `SYNCED`.
3. Ako ćelija nije dostupna, status ostaje `PENDING`. Pozadinski radnik u CORE-u
   budi se na svakih 900 sekundi (podesivo), izvlači sve `PENDING` zapise i
   pokušava ponovo. Mrežna greška ili timeout ostavljaju zapis nepromenjen za
   sledeći krug. Radnik se pali i gasi iz `core_lifespan`-a, po uzoru na
   `_start_auto_import` i `_start_torrents`.
4. Ćelija primljene beleške upisuje u `.ai/nadogradnje/` kao datirane markdown
   fajlove i u svoju bazu.
5. Pri pokretanju ćelija prikazuje listu primljenih beleški; korisnik bira koje
   se primenjuju. Ništa se ne primenjuje samo od sebe.

Beleška se može napisati i direktno u ćeliji, bez CORE-a — tada preskače korake
1 do 3.

Ovde se Moduli 2, 3 i 4 iz izvornog dokumenta uklapaju: SQLite red, pozadinski
radnik i API nisu sami sebi cilj nego transport za beleške. Red čekanja živi u
`core.db` kao tabela, ne kao odvojen `core_sync.db` fajl, jer projekat već ima
jedan obrazac migracija sa `scope`-om i drugi fajl baze bi ga razbio.

## 10. `.ai/` i RAG ćelije

### 10.1 Direktorijum `.ai/`

Ćelija ponavlja obrazac CORE-ovog `.ai/` direktorijuma u malom:

- `CLAUDE.md` — uputstva za AI koji radi na tom domenu.
- `PROJECT.yaml` — identitet, obim i granice domena.
- `INDEX.json`, `DEPENDENCIES.json` — mapa koda i zavisnosti ćelije.
- `READ_POLICY.md` — šta se čita pre rada.
- `dev-log/entries/` — dnevnik rada na ćeliji.
- `nadogradnje/` — primljene beleške iz CORE-a.
- `atomi/` — atomske beleške, izvor za RAG ćelije (10.2).

Sadržaj se izvodi iz postojećeg CORE `.ai/`, okresan na ono što se tiče samo tog
domena.

### 10.2 Sopstveni RAG nad atomskim fajlovima

Svaka ćelija ima svoj RAG, nezavisan od CORE-ovog.

**Atomski fajl** je jedna činjenica u jednom markdown fajlu u `.ai/atomi/`, sa
zaglavljem (`id`, `naslov`, `tip`, `izvor`, `datum`, `veze`) i telom od nekoliko
rečenica. Veze na druge atome pišu se kao `[[id]]`. Tipovi: `odluka`, `pravilo`,
`pojam`, `postupak`, `greska`. Jedan fajl nosi tačno jednu činjenicu — to je
razlog postojanja formata: pretraga vraća činjenicu, ne fajl od 400 linija u
kom ona negde stoji.

Izvori za unos u RAG ćelije: `.ai/atomi/`, `.ai/dev-log/entries/`,
`.ai/nadogradnje/` i `PROJECT.yaml`. Kod domena se ne unosi — za to postoji
`INDEX.json`.

Tehnički, ćelija koristi isti `core/rag` iz kernela (1407 linija, Postgres s
pgvector i Ollama embeddings), ali sa sopstvenim prostorom imena
`cell:<domain_id>`, upisanim u `cell.json`. Dve ćelije i CORE nikad ne vide
tuđe atome.

RAG je **opcion**, kao i u CORE-u danas. Postgres i Ollama su spoljni servisi i
ne smeju da budu uslov za pokretanje ćelije: ako ih nema, ćelija se diže
normalno, RAG je ugašen i prijavljuje se kao takav u `GET /cell/status`.
Atomski fajlovi i tada ostaju čitljivi jer su običan markdown.

Unos se pokreće na zahtev i pri izmeni fajla u `.ai/` — ne pri svakom
pokretanju, da paljenje ćelije ne zavisi od brzine embedding servisa.

## 11. Tajne i git

Trenutno stanje: `config/tmdb.json` je praćen git-om i sadrži žive TMDB
kredencijale (`access_token`, `api_key`), prisutne od prvog commita `0e78fa3`.

Mere, po redosledu:

1. `.gitattributes` i `git config filter.core-secrets.clean` — radna kopija
   zadržava prave vrednosti, a commit-ovani blob dobija čitljiv rezervisan tekst
   oblika `[ Here put API key for TMDB ]`. Isti filter pokriva svaki fajl u
   `config/` koji nosi ključeve.
2. `pre-commit` provera koja prekida commit ako obrazac ključa ipak prođe kroz
   filter.
3. Pre bilo kakvog `git push`-a ćelije ili CORE-a na javno mesto: povlačenje i
   ponovno izdavanje TMDB ključa, pa `git filter-repo` koji uklanja fajl iz cele
   istorije. Filter iz tačke 1 čisti samo buduće commit-e; commit `0e78fa3`
   ostaje netaknut dok se istorija ne prepiše.

Tačke 1 i 2 rade se u ovom poslu. Tačka 3 je uslov za objavljivanje i izvršava
se tek kad se ćelija objavljuje.

## 12. Testiranje

Pokretanje: `./.venv/Scripts/python.exe -m pytest` (ne sistemski python).

Novi testovi:

- izvlačenje baze: broj redova po tabeli jednak pre i posle; `core_schema_migrations`
  za `scope='filmium'` prenet; ponovno pokretanje migracija nad ćelijskom bazom
  ne menja ništa;
- `import_guard`: isti ishodi kao KALIMA skener na dvostrukoj ekstenziji,
  izvršnoj ekstenziji i poznatom malware hešu;
- registar `cells`: skeniranje direktorijuma nalazi `cell.json`, odbija
  neispravan manifest, ne upisuje isti domen dvaput;
- beleške: `PENDING` pri nedostupnoj ćeliji, `SYNCED` pri HTTP 200, radnik ne
  pada na timeout-u;
- `/cell/status`: vraća očekivan oblik i ne sudara se sa postojećim `/status`.

Ćelija nosi svoj `tests\` i svoje pytest podešavanje, nezavisno od CORE-a.

## 13. Obim i redosled

Ovaj spec pokriva P1 i P2 nad FILMIUM-om:

- **P1 — kontrakt ćelije**: `cell.json`, granica kernela, `/cell/*` endpointi.
- **P2 — odcepljenje FILMIUM-a**: baza, kod, GUI, `import_guard`, sopstveni git.

Van obima ovog spec-a:

- **P3** — pun ekran „Ćelijski sistem" u CORE Settings-u sa dugmetom „Odcepi"
  koje generiše ćeliju automatski (nastaje iz iskustva sa P2).
- **P4** — potpun tok beleški sa GUI-jem u ćeliji za biranje nadogradnji.
- **P5** — atomske beleške i nadogradnja `core/system/second_brain.py`.
- Odcepljenje CODIUM-a, IMPERIUM-a i KALIMA-e.
- Restrukturiranje monorepoa u pakete.
- Brisanje FILMIUM tabela i koda iz CORE repoa.

## 14. Rizici

| Rizik | Mera |
|---|---|
| Prepisivanje istorije glavnog repoa je jednosmerno | Ceo posao ide na grani; nijedan fajl se ne briše iz CORE-a dok ćelija ne proradi; provereni backup pre `filter-repo`. |
| Ćelija i CORE se raziđu u verziji kernela | `kernel_version` u `cell.json`, prikazan u CORE kartici; nesklad je vidljiv pre nego što postane kvar. |
| Tajne odlaze u javni repozitorijum | Odeljak 11, tačka 3 kao uslov za objavljivanje. |
| GUI shell se pokaže spleteniji nego što merenje kaže | Merenje pokriva samo `features/filmium`; shell i rute se proveravaju pre premeštanja, i ako ispadne veće, obim se vraća na sto. |
| Dodeljen port zauzet na ciljnoj mašini | CORE proverava dostupnost pre upisa u `cell.json`; ćelija odbija start uz jasnu poruku ako je port zauzet. |

## 15. Dopuna 2026-09-13 — GUI i API ćelije

Prvi plan je dao ćeliju koja se diže i odgovara samo na `/cell/status`. Ova
dopuna prenosi u ćeliju GUI i FILMIUM API, tako da se FILMIUM stvarno koristi
sa `F:\FILMIUM\`.

### 15.1 Odluke

| Odluka | Izbor | Razlog |
|---|---|---|
| Oblik pokretanja | Jedan proces na `127.0.0.1:<port>` služi API i GUI; `start.bat` otvara browser | Za pokretanje ne treba ni Node ni Rust. API je upaljen uvek kad je upaljen FILMIUM, pa ga CORE može gađati. |
| GUI u ćeliji | Izvorni kod + gotov build (`gui/dist`) | Izvor omogućava izmene u samoj ćeliji; build omogućava pokretanje bez Node-a. Build se pravi pri sklapanju, CORE-ovim `node_modules`. |
| Adresa API-ja u GUI-ju | Isti origin (`VITE_CORE_API_URL=""`) | GUI radi na bilo kom portu koji CORE dodeli. |
| Tauri dijalog za foldere | Omotač `lib/pathPicker.ts`: Tauri dijalog u Tauri prozoru, unos putanje u browseru | Pet FILMIUM fajlova danas zove `@tauri-apps/plugin-dialog`, koji u browseru ne radi. U CORE-u se ponašanje ne menja. |
| Podešavanja u ćeliji | FILMIUM podešavanja + Persona + prikaz Ollama modela | Po odluci iz §5.1 ćelija ne nosi Modele, API ključeve ni Chat panel. |
| Kurator chat u ćeliji | `CellAssistantChat` nad `POST /api/v1/filmium/curator/ask` | CORE-ov `CoreAssistantChat` zove CORE asistenta i vuče CODIUM, window manager i CORE podešavanja. |
| Zamena CORE-only modula | Jedna mapa zamena (`apps/gui/cell-substitutions.json`) koju čitaju i Vite plugin i Python sklapač | FILMIUM izvor ostaje netaknut; zamena je eksplicitna i proverljiva na jednom mestu. |
| Ponovno sklapanje | Režim ažuriranja zamenjuje kod, a čuva `data/` i `config/` | Baza ćelije i ručno upisan TMDB ključ ne smeju da nestanu pri osvežavanju koda. |

### 15.2 Izmereno zatvorenje GUI-ja (2026-09-13)

Polazeći od `features/filmium/**` i `pages/Filmium*.tsx`, zatvorenje uvoza ima
159 fajlova, od toga 66 van FILMIUM fascikli. CORE-only grane ulaze kroz tačno
dve tačke: `features/filmium/FilmiumKuratorChat.tsx` → `features/chat/CoreAssistantChat`
(vuče `features/codium`, `features/window`, `features/voice`) i
`pages/FilmiumSettingsPage.tsx` → `features/settings/{ApiKeysPanel, ChatPanel, ModelsPanel}`.
Obe se u ćeliji zamenjuju. npm zavisnosti zatvorenja: `react`, `react-dom`,
`react-router`, `lucide-react`, `@tauri-apps/api`, `@tauri-apps/plugin-dialog`.

### 15.3 API ćelije

`cell_app.py` preusmerava putanje i inicijalizuje bazu **pre** uvoza routera,
jer `apps/api/dependencies.py` pravi repozitorijume već pri uvozu. Montira svih
16 FILMIUM routera, `/cell/status` (dopunjen poljima `ai_endpoint` i
`ai_curator_model`), `GET /cell/personas` i `PUT /cell/personas/{id}` nad
`persona_store` opsegom `filmium`, i na kraju GUI build na `/`.
`apps/api/dependencies.py` je ponovo obavezan modul pri sklapanju.

## 16. Dopuna 2026-09-13 — Tauri prozor i sopstveno okruženje ćelije

Posle §15 ćelija se otvarala u browser tabu i, u praksi, nije radila: `start.bat`
je pozivao sistemski `python`, koji nema `uvicorn`, pa se API nikad nije digao.
Korisnik očekuje da se FILMIUM otvara kao CORE — u sopstvenom Tauri prozoru, uz
API koji se pokreće zajedno sa njim. Ova dopuna menja odluku o obliku pokretanja
iz §15.1.

### 16.1 Odluke

| Odluka | Izbor | Razlog |
|---|---|---|
| Oblik pokretanja | Tauri prozor (`<IME>.exe` u korenu ćelije) | Po obrascu `CORE-Start.exe`: jedan dvoklik otvara aplikaciju, API se diže zajedno sa njom. |
| Tauri projekat | Nov mali projekat `apps/cell-shell/`, ne CORE-ov `src-tauri` | CORE-ov nosi terminal, screenshot i glas. Ćeliji trebaju samo dijalog za foldere i dve komande za ugradnju mpv-a (`core_main_hwnd`, `core_window_geom`). |
| Jedan exe za sve ćelije | Shell čita `cell.json` pored sebe | Isti build služi svaki domen; builduje se jednom u repou, sklapanje ga kopira kao `<IME>.exe`. |
| Šta prozor učitava | `http://127.0.0.1:<port>/#/<domen>` | GUI i API ostaju na istom originu; `TrustedHostMiddleware` prolazi, CORS nije potreban. Tauri capability dozvoljava IPC samo za tu lokalnu adresu. |
| Naslovna traka | Standardna Windows traka (`decorations: true`) | CORE crta sopstvenu traku u svom shell-u, koji ćelija nema. |
| Životni ciklus API-ja | Shell pokreće API ako ne odgovara, i gasi samo proces koji je sam pokrenuo | Ako je API već upaljen (npr. CORE ga koristi), zatvaranje prozora ga ne ruši. |
| Python okruženje | Sopstveni `<ćelija>/.venv`, pravi ga sklapanje | Ćelija ne sme da zavisi od CORE-ovog `.venv` ni od sistemskog Python-a. `.venv` je korisnički prostor koji `--update` ne dira; paketi se doinstaliraju samo kad se spisak promeni. |
| `requirements.txt` ćelije | Samo paketi koje kod ćelije stvarno uvozi, sa tačnim instaliranim verzijama | CORE-ov spisak nosi `anthropic`, `openai`, `mcp`, `keyring`, koje ćelija ne koristi. |
| Nedostajući lokalni paketi | Sklapanje pada ako ćelija uvozi repo paket koji ne nosi | Merenje je našlo `integrations.translator` (dugme „Updatuj" i prevod u wishlist-i), koji postojeće provere nisu videle. |

### 16.2 Plakati i pozadine

`data/filmium/assets/{posters,backdrops}` je optimizovan keš (smanjene kopije);
originali su u folderu filma na disku biblioteke. Kad kopija ne postoji, API
servira original iz registrovanog izvora (`filmium_media_artworks`,
`storage_kind='source'`). Ovo važi i za CORE i za ćeliju.
