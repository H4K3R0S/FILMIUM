---
id: filmium-8adce83f-2026-08-16-filmium-related-recommendations-design-md
type: spec
domain: filmium
namespace: global
visibility: global
tier: domain
title: FILMIUM — Preporuke na detalj-stranici (Povezani / Preporučeni / Po žanru)
summary: '**Datum:** 2026-08-16'
keywords:
- filmium
- preporuke
- detalj
- stranici
- povezani
- preporučeni
- žanru
- docs
- superpowers
- specs
tags:
- superpowers
- specs
source_path: docs/superpowers/specs/2026-08-16-filmium-related-recommendations-design.md
---

# FILMIUM — Preporuke na detalj-stranici (Povezani / Preporučeni / Po žanru)

**Datum:** 2026-08-16
**Domen:** FILMIUM
**Tip:** Arhitekturna izmena (DB shema + TMDB pipeline + migracija + frontend)

## 1. Cilj

Detalj-stranica filma/serije (`FilmiumMediaDetailsPage`) trenutno prikazuje
dva klijentski računata reda preporuka:

- `genreMatches` → „Filmovi/Serije iz istog žanra" (skor po broju istih žanrova)
- `actorMatches` → „Preporučeni filmovi ili serije" (skor po istom akteru/cast-u)

Zamenjujemo ih sa **tri jasno odvojena odeljka**, po redosledu:

1. **Povezani filmovi / Povezane serije** — bazirano na TMDB
   `recommendations` (stvarna „povezanost" iz TMDB baze).
2. **Preporučeni Filmovi / Preporučene Serije** — ponderisano poklapanje po
   nazivu + žanrovima + ključnim rečima.
3. **Preporuka po žanru** — poklapanje po žanru (žanr-skup).

## 2. Odluke (potvrđene sa korisnikom)

- **Izvor „Povezani":** TMDB `recommendations`. Prikazuju se i naslovi koje
  korisnik NE poseduje.
  - owned → normalna kartica, vodi na detalj.
  - **ne-owned → kartica sa crvenom ivicom**, klik otvara `FilmiumAcquireModal`
    (lista „za preuzeti") popunjen podacima naslova.
- **Punjenje TMDB related polja:** **samo unapred** — novi importi i ručno
  „Dopuni preko TMDB". Postojeći redovi ostaju prazni dok se ne osveže.
- **Čuvanje:** nova JSON kolona `related_tmdb` + migracija `v30` (prati
  obrazac `v29 tmdb_id`).
- **Broj kartica:** računamo do 20, prikazujemo **10** po odeljku (bez „Prikaži
  još" za sad).
- **Dedupliranje:** **kaskadno** — Povezani → Preporučeni → Po žanru; svaki
  odeljak izbacuje naslove koje su gornji već prikazali. Bez ponavljanja iste
  kartice.

## 3. Backend

### 3.1 TMDB client (`core/domains/filmium/tmdb_client.py`)

- Dodati `recommendations` u `append_to_response` u sve tri fetch putanje
  (film, serija, enrich) — trenutno `"credits,keywords"` →
  `"credits,keywords,recommendations"`.
- Nova parser funkcija `_parse_recommendations(data) -> tuple[RelatedTitle, ...]`
  koja iz TMDB `recommendations.results` vadi lagane zapise. TMDB vraća `id`,
  `title`/`name`, `release_date`/`first_air_date`, `poster_path`, `media_type`.
- Novi lagani dataclass `RelatedTitle`:
  `tmdb_id: int`, `title: str`, `year: int | None`,
  `poster_path: str | None`, `media_type: MediaType`.
- Dodati `recommendations: tuple[RelatedTitle, ...] = ()` na TMDB rezultat
  dataclass (isti onaj koji već nosi `keywords`, `cast_names`...).
- Ograničiti na prvih 20 pri parsiranju (hard cap).

### 3.2 Model (`core/domains/filmium/models.py`)

- Dodati `related_tmdb: tuple[RelatedTitle, ...] = ()` na `MediaItem` i
  `MediaItemCreate`. (`RelatedTitle` živi u `models.py` ili se re-exportuje;
  bira se po postojećem obrascu za `keywords`.)

### 3.3 Migracija (`core/domains/filmium/migration_v30.py` — novo)

```python
FILMIUM_MIGRATION_V30 = DatabaseMigration(
    scope="filmium",
    version=30,
    name="add_media_related_tmdb",
    statements=(
        """
        ALTER TABLE filmium_media_items
        ADD COLUMN related_tmdb TEXT
        """,
    ),
)
```

- Registrovati u `migrations.py`: import + dodati u `FILMIUM_MIGRATIONS` tuple
  posle `V29`.
- Kolona je JSON tekst (lista objekata). Postojeći redovi = NULL → parsira se
  kao prazna lista.

### 3.4 Repository (`core/domains/filmium/repository.py`)

- U `INSERT` (create) i `UPDATE` upisati `related_tmdb` kao
  `json.dumps([... ])` (serijalizacija liste `RelatedTitle` u dict-ove),
  isti obrazac kao `keywords`/`cast_names`.
- `_row_to_media_item` — parsirati `related_tmdb` kolonu nazad u tuple
  `RelatedTitle` (nova helper `_parse_related(value)`; NULL → `()`).
- Enrich/TMDB update putanja (koja već upisuje `keywords`) mora upisati i
  `related_tmdb`. Ako postoji uzak update sličan `update_keywords`, proširiti
  ga ili dodati odgovarajući upis. Ručno „Dopuni preko TMDB" ide kroz istu
  putanju → automatski puni polje.

### 3.5 API schema (`apps/api/schemas/filmium.py`)

- Dodati `related_tmdb: list[RelatedTitleSchema]` na media schema odgovor.
- Novi `RelatedTitleSchema`: `tmdb_id`, `title`, `year`, `poster_path`,
  `media_type`.

## 4. Frontend

### 4.1 Tip (`apps/gui/src/types/...`)

- Dodati `RelatedTitle` tip i `related_tmdb: RelatedTitle[]` na `MediaItem` tip.

### 4.2 Detalj-stranica (`apps/gui/src/pages/FilmiumMediaDetailsPage.tsx`)

Tri `useMemo` bloka, poštuju kategoriju (Domaće/Anime restrikcija) kao sad:

**Odeljak 1 — Povezani (`relatedItems`):**
- Iz `item.related_tmdb` (do 20).
- Za svaki, potraži owned parnjak u `items` po `tmdb_id`.
- Rezultat: lista `{ related: RelatedTitle, owned: MediaItem | null }`.
- Owned prvo, pa ne-owned. Slice na 10 (posle dedupa).

**Odeljak 2 — Preporučeni (`recommendedItems`):**
- Ponderisan skor po kandidatu iz `items`:
  - keywords overlap × W_kw (najveći ponder),
  - genre overlap × W_genre,
  - title-token overlap × W_title (samo tokeni dužine ≥ 4, tačan match —
    štiti od „Walking Tall" ↔ „Chaos Walking").
- Filter `score > 0`, sort opadajuće, poštuje kategoriju, isključi `item.id`.

**Odeljak 3 — Po žanru (`genreItems`):**
- Postojeći `genreMatches` logika (skor = broj istih žanrova).

**Kaskadni dedup:** skup `seenIds`. Povezani popune skup (owned id-jevi +
tmdb id-jevi), Preporučeni izbace šta je u skupu i dopune ga, Po žanru izbaci
oba. Svaki finalni odeljak `.slice(0, 10)`.

**Render:**
- `RecommendationRow` proširiti: podržati ne-owned kartice (crvena ivica) i
  `onAcquire(related)` callback pored `onOpen(item)`.
- Ne-owned poster: `https://image.tmdb.org/t/p/w500` + `poster_path` (konstanta
  u fajlu). Ako `poster_path` == null → fallback blok (kao sad).
- Ne-owned klik → otvara `FilmiumAcquireModal` sa `prefill`.

### 4.3 Acquire modal prefill (`FilmiumAcquireModal.tsx`)

- Dodati opcioni `prefill?: { title; year; media_type; tmdb_id }` prop.
- Kad je prisutan pri otvaranju: popuniti `title`, `year`, `mediaType`,
  i sačuvati `tmdb_id` (nosi se u `createWishlistEntry`). Ostala polja prazna.
- Detalj-stranica drži state za otvoreni modal + prefill.

### 4.4 CSS

- `.filmium-details-poster-card.is-wishlist` — crvena ivica (npr.
  `border: 2px solid var(--filmium-danger, #e5484d)`) + suptilan badge/oznaka
  „Za preuzeti" opcionalno.

## 5. Testovi

- Backend: parser `_parse_recommendations` (prazno / film / serija / cap 20),
  round-trip repository (upis + čitanje `related_tmdb`), migracija primeni.
- Frontend: scorer za Preporučene (keyword > genre > title ponder; title token
  ≥4 ne daje lažan pogodak), kaskadni dedup (nema ponavljanja), owned vs
  ne-owned podela u Povezani.

## 6. Van opsega (YAGNI)

- „Prikaži još" / paginacija preko 10.
- Backfill starih naslova (svesno „samo unapred").
- TMDB `similar` endpoint (koristimo samo `recommendations`).
- Keširanje TMDB poster slika lokalno za ne-owned (koristi se TMDB CDN URL).

## 7. Dodirnuti fajlovi

Backend: `models.py`, `tmdb_client.py`, `migration_v30.py` (novo),
`migrations.py`, `repository.py`, `apps/api/schemas/filmium.py`, enrich/service
putanja.
Frontend: `types/…`, `FilmiumMediaDetailsPage.tsx`, `FilmiumAcquireModal.tsx`,
`filmium-pages.css` (ili odgovarajući CSS).
