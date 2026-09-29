---
id: filmium-20f48ddd-2026-08-16-filmium-za-preuzeti-wishlist-md
type: plan
domain: filmium
namespace: global
visibility: global
tier: domain
title: FILMIUM „Za preuzeti" — plan implementacije
summary: 'Datum: 2026-08-16'
keywords:
- filmium
- preuzeti
- implementacije
- docs
- superpowers
- plans
tags:
- superpowers
- plans
source_path: docs/superpowers/plans/2026-08-16-filmium-za-preuzeti-wishlist.md
---

# FILMIUM „Za preuzeti" — plan implementacije

Datum: 2026-08-16
Grana: master

## Cilj

Novo dugme (veliki „+") u FILMIUM gornjoj traci, levo od filter ikone. Klik
otvara centralni modal (fade in / fade out, srednje spor) za planiranje filmova
i serija koje korisnik želi da nabavi u budućnosti. Podaci se čuvaju u **zasebnu
tabelu** (`filmium_wishlist`), a na Home ekranu se prikazuje red
**„FILMOVI ZA PREUZETI"**.

Modal NE upisuje u glavni katalog (`filmium_media_items`) — to je odvojena lista
želja.

## Odluke (potvrđene sa korisnikom)

- TMDB dugme: zove postojeći enrich (title + year) i popuni polja/opise/slike.
- Prevodi (Originalni / Domaći / Engleski): **fajl titla** (.srt/.sub),
  drag-and-drop ili klik.
- TITL / SINH: **dva nezavisna** toggla (oba mogu uklj/isklj).
- „Dodaj": upisuje red u zasebnu `filmium_wishlist` tabelu.
- „Zasebna baza podataka" = nova tabela u istoj core bazi (idiomatski za projekat;
  svi repozitorijumi koriste `core_database_connection`).

## Polja modala

- Kategorija (dugmad, sve isključene po defaultu, biraju gde pripada):
  **Strano / Domaće / Animirano**  → `content_category`: `regular|domestic|animated`.
- **TITL** toggle → `is_subtitled` (bool), **SINH** toggle → `is_synchronized` (bool).
- Tip: **Film / Serija** (potrebno za TMDB search rutu i za razvrstavanje).
- Ime (tekst), Godina (broj).
- Poster (drop/klik), Backdrop (drop/klik), Wallpaper (drop/klik).
- Dodatni sadržaj (više fajlova — opcionо).
- Prevodi: Originalni / Domaći / Engleski (fajl titla svaki).
- Engleski opis (textarea), Domaći opis (textarea).
- Dugme „Pretraži TMDB" (popuna), dugme „Dodaj" (čuvanje).
- Zatvaranje: klik van okvira ILI dugme „nazad" u gornjem uglu. Fade out pri gašenju.

## Backend

### 1. Migracija `migration_v28.py` — tabela `filmium_wishlist`
Kolone: `id`, `title`, `release_year`, `media_type` (movie|series),
`content_category` (regular|domestic|animated), `is_subtitled`,
`is_synchronized`, `tmdb_id`, `english_overview`, `local_overview`,
`poster_path`, `backdrop_path`, `wallpaper_path`,
`original_subtitle_path`, `domestic_subtitle_path`, `english_subtitle_path`,
`extra_assets` (JSON lista putanja), `created_at`, `updated_at`.
Registrovati u `migrations.py` (`FILMIUM_MIGRATION_V28`).

### 2. Domen: `wishlist_models.py`, `wishlist_repository.py`, `wishlist_service.py`
Pattern kopiran sa `collection_*`. Repo: `create`, `list_all`, `get_by_id`,
`delete`. Service tanka validacija (title obavezan).

### 3. Router `filmium_wishlist.py` (+ registracija u API app)
- `POST /api/v1/filmium/wishlist` — kreira red (Dodaj).
- `GET  /api/v1/filmium/wishlist` — lista za Home.
- `DELETE /api/v1/filmium/wishlist/{id}`.
- `POST /api/v1/filmium/wishlist/{id}/asset` — upload poster/backdrop/wallpaper/
  subtitle/extra (reuse obrazac iz `upload_media_asset`). Asseti pod zasebnim
  wishlist folderom.
- `POST /api/v1/filmium/wishlist/tmdb-preview` — telo `{title, year, kind}`;
  zove `tmdb_client.enrich_movie|enrich_series`; vraća naslove, opise (en/local),
  `poster_url`, `backdrop_url`, `genres`, `tmdb_id`. Bez upisa.
- Schemas u `schemas/filmium_wishlist.py`.

Redosled: asseti se otpremaju posle kreiranja reda (id potreban za folder), ili
draft-flow: kreiraj red pa upload. Modal: prvo „Dodaj" (kreira red iz tekst polja),
zatim upload izabranih fajlova na dobijeni id. TMDB slike (URL) preuzeti server-side
kao u `_persist_tmdb_visuals`.

## Frontend

### 4. `FilmiumTopBar.tsx`
Dodati `onAddClick` prop; dugme sa `Plus` (lucide) kao **prvo** u
`.filmium-top-actions` (levo od Funnel). `aria-label="Dodaj u listu za preuzeti"`.

### 5. Nova komponenta `components/uploads/FilmiumAcquireModal.tsx`
Overlay + centralni panel. Fade preko CSS klasa (`is-open`), mount/unmount sa
odloženim unmount da fade-out odradi (~280ms). Klik na overlay zatvara; klik unutar
panela ne propagira. Dugme „nazad" (`ChevronLeft`) u uglu.
Drag-and-drop zone za poster/backdrop/wallpaper (reuse obrazac; prikaz preview).
Toggle grupa kategorija + TITL/SINH (stil kao `ContentModeToggle`).
„Pretraži TMDB" → poziv preview API, popuni polja. „Dodaj" → create + uploads,
zatim `onAdded()` (osveži Home listu) i zatvori.

### 6. CSS `styles/filmium-acquire.css`
Overlay backdrop blur, panel centriran, `@keyframes` fade in/out (srednje spor,
~280–320ms `ease`). Import u komponenti.

### 7. Service `services/filmiumWishlistApi.ts`
`listWishlist`, `createWishlist`, `deleteWishlist`, `uploadWishlistAsset`,
`tmdbPreview`. Tipovi u `types/filmiumWishlist.ts`.

### 8. Wiring `FilmiumWorkspace.tsx`
State `acquireOpen`; `handleAddClick`; render `<FilmiumAcquireModal>` na kraju
workspace-a; prosledi `onAddClick` u `FilmiumTopBar`.

### 9. Home red „FILMOVI ZA PREUZETI"
Hook `useFilmiumWishlist` (fetch liste). U `FilmiumPage.tsx` novi red iznad/ispod
shelves-a: kartice sa posterom, imenom, godinom, oznakom kategorije + TITL/SINH.
Osvežava se posle „Dodaj".

## Testovi

- `wishlist_repository` unit (create/list/delete) sa temp bazom.
- `FilmiumTopBar` — novo „+" dugme zove `onAddClick`.
- `FilmiumAcquireModal` — otvara/zatvara, toggli default OFF, „Dodaj" zove API.
- `filmiumWishlistApi` — oblici zahteva.

## Redosled izrade

1. Backend migracija + domen + router + schemas (+ test repo).
2. Service + tipovi (frontend).
3. TopBar „+" dugme (+ test).
4. Modal komponenta + CSS (+ test).
5. Workspace wiring.
6. Home red.
7. Ručna provera u preview + dev-log unos.
