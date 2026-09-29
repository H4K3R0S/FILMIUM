---
id: filmium-0b831aa1-2026-08-10-filmium-blue-reskin-header-cleanup-design-md
type: spec
domain: filmium
namespace: global
visibility: global
tier: domain
title: Filmium plavi re-skin, čist CORE header i toggle naslova — dizajn
summary: 'Datum: 2026-08-10'
keywords:
- filmium
- plavi
- skin
- čist
- core
- header
- toggle
- naslova
- dizajn
- docs
tags:
- superpowers
- specs
source_path: docs/superpowers/specs/2026-08-10-filmium-blue-reskin-header-cleanup-design.md
---

# Filmium plavi re-skin, čist CORE header i toggle naslova — dizajn

Datum: 2026-08-10
Domen: `apps/gui`

## Problem

Tri povezana zahteva na CORE GUI-ju:

1. **Filmium nije dosledno plav.** Kada je aktivan Filmium domen, sidebar identitet (CORE tekst, verzija, ikonice, hover, separator, ivica) treba da bude plav, ali unutrašnjost radnog prostora i dalje koristi ljubičaste/violet akcente (search bar, ivice prozora i dugmadi, naslovi, aktivna stanja). U Filmium CSS-u ima ~93 hardkodovanih ljubičastih vrednosti. Opisi filmova i serija treba da ostanu beli.
2. **CORE dashboard header izgleda kao poseban panel.** `.top-bar` ima pozadinu, `backdrop-filter` i donju liniju razdvajanja, pa deluje kao zaseban element. Treba da ostanu samo tri elementa na svojim pozicijama (levo: CORE control + naslov strane; centar: sat/Vreme; desno: System online status), bez panel-pozadine i linije.
3. **Sticky Filmium traka prelazi preko naslova programa.** Pri skrolovanju, `.filmium-top-bar` (search + akcije) se zaključa na `top: 0` i prekrije naslov programa (`.section-heading` na library stranama). Naslov ovde nije potreban — treba da bude skriven po defaultu, sa prekidačem u CORE Settings koji ga pali. Kada je upaljen, traka i naslov treba da budu razdvojeni i oba vidljiva.

## Cilj / ne-cilj

**Cilj:**
- Jedan token sloj po domenu kao izvor istine za boje; svi Filmium CSS fajlovi čitaju te tokene.
- Pod Filmium domenom sve akcentne boje su nijanse plave; ništa ljubičasto ne ostaje.
- CORE header bez chrome-a (pozadina/ivica/blur), zadržane tri pozicione zone.
- Naslov programa skriven po defaultu, prekidač u CORE Settings; kada je upaljen, ne preklapa se sa sticky trakom.

**Ne-cilj:**
- Redizajn rasporeda sidebara ili sadržaja stranica.
- Menjanje boja drugih domena (codium, kalima, imperium) osim što nasleđuju prošireni token skup.
- Menjanje ponašanja pretrage, filtera ili navigacije.

## Arhitektura

### 1. Token sloj (izvor istine po domenu)

`styles/themes/core.css` (`:root`, CORE default) dobija semantičke RGB kanale pored postojećih:

| Token | Uloga | CORE default (plava) |
|-------|-------|----------------------|
| `--domain-accent-rgb` | primarni akcenat: ivice, glow, aktivni outline (postoji) | `88, 182, 255` |
| `--domain-accent-strong-rgb` | zasićeni fill: aktivna dugmad/pozadine | `37, 99, 235` |
| `--domain-accent-soft-rgb` | svetli tekst/label: eyebrow, badge, sat | `147, 197, 253` |
| `--domain-accent-contrast-rgb` | near-white akcent tekst | `224, 240, 255` |

Izvedeni tokeni (npr. `--domain-accent`, `--domain-glow`) ostaju kako jesu; dodaju se izvedeni po potrebi (`--domain-accent-strong`, `--domain-accent-soft`, `--domain-accent-contrast`).

`styles/themes/filmium.css` prepisuje samo `*-rgb` kanale u plave nijanse (tamnija/zasićenija plava paleta domena). Ostali domeni ne diraju nove tokene osim ako ne žele svoju vrednost.

### 2. Migracija hardkodovanih boja

Svih ~93 ljubičastih/violet vrednosti u `src/features/filmium/**/*.css` (i `filmium-*.css` u `styles/`) zamenjuju se referencom na token, uz zadržavanje inline alfe:

- `rgba(168, 85, 247, α)` i `#a855f7` → `rgba(var(--domain-accent-rgb), α)` / `rgb(var(--domain-accent-rgb))`
- `#7c3aed`, `#6d28d9`, `rgba(109, 40, 217, α)`, `rgba(126, 34, 206, α)`, `rgba(88, 28, 135, α)`, `rgba(124, 58, 237, α)` → `--domain-accent-strong-rgb`
- `#a78bfa`, `#d8b4fe`, `#c4b5fd`, `#c084fc` → `--domain-accent-soft-rgb`
- `#f3e8ff`, `#e9d5ff`, `#faf5ff` → `--domain-accent-contrast-rgb`

Mapiranje je po ulozi (fill/tekst/ivica), ne mehanički po heksu — pri migraciji svakog fajla proverava se kontekst pravila. Opisi filmova i serija (beli `#f8fafc` / slično) se **ne** diraju.

Sidebar, separator (`.glow-separator`) i ivica već koriste `--domain-accent`, pa automatski postaju plavi pod Filmium domenom — nema dodatnog rada tamo osim provere.

### 3. CORE header bez chrome-a

`.top-bar` (`styles/core-shell.css`): uklanjaju se `background`, `border-bottom` i `backdrop-filter`; ostaje `position: relative` i visina radi pozicioniranja. Tri zone (`.top-bar-lead`, `.header-clock`, `.top-bar-status`) ostaju apsolutno pozicionirane kao sada. JSX u `AppShell.tsx` se ne menja.

### 4. Naslov programa: skriven default + toggle

- Novi hook `useCoreSetting` (`components/layout/` ili `lib/`), obrazac po uzoru na `useSidebarVisibility` (localStorage + `useState`). Ključ: `core.filmium.showPageTitle`, default `false`.
- `.section-heading` na Filmium library stranama renderuje se samo kada je podešavanje uključeno. Kontrola se čita u `FilmiumLibraryPage` (i drugim stranama sa `.section-heading` unutar Filmium radnog prostora) i uslovljava prikaz.
- `CoreSettingsPage` zamenjuje placeholder pravim prekidačem (toggle) koji čita/piše to podešavanje.
- Kada je **uključen**: `.section-heading` dobija `position: sticky; top: var(--filmium-topbar-h)` uz mali gap, pa se zaključa ispod sticky trake — traka i naslov su razdvojeni i oba vidljiva.
- Kada je **isključen** (default): naslov se ne renderuje, nema preklapanja.
- Uvodi se CSS promenljiva `--filmium-topbar-h` (visina sticky trake + gap) za offset.

## Tok podataka

Aktivni domen već postavlja `data-domain` na `<html>` (postojeći `resolveDomainId` helper), što aktivira odgovarajući theme fajl i time menja vrednosti `*-rgb` tokena. Sve akcentne boje su izvedene iz tih tokena, pa promena domena re-skinuje ceo interfejs bez dodatne logike.

Podešavanje naslova živi u localStorage; hook ga čita pri montiranju i emituje promene komponentama koje uslovljavaju prikaz `.section-heading`.

## Rukovanje greškama

- `useCoreSetting`: ako localStorage nije dostupan ili vrednost nije validna, pada na default (`false`) bez bacanja.
- Token migracija je čisto CSS; nedostajuća promenljiva pada na CORE default iz `:root`, pa najgori ishod nije ljubičasto već CORE plavo.

## Testiranje

- `useCoreSetting`: unit test — default kada nema vrednosti, čitanje/pisanje, tolerancija na nevalidan localStorage.
- `CoreSettingsPage`: prekidač menja podešavanje (render test).
- `FilmiumLibraryPage`: `.section-heading` odsutan po defaultu, prisutan kada je podešavanje uključeno.
- Vizuelna provera preview alatom: Filmium radni prostor je plav (search bar, ivice, aktivna dugmad, naslovi), opisi ostaju beli; CORE header bez linije/pozadine; sticky traka ne preklapa naslov kada je uključen.
- Postojeći testovi (`AppShell.test.tsx`, `Sidebar.test.tsx`, `FilmiumTopBar.test.tsx`) i dalje prolaze.

## Fajlovi (okvirno)

- `styles/themes/core.css` — novi tokeni.
- `styles/themes/filmium.css` — plavi override kanala.
- `src/features/filmium/**/*.css`, `styles/filmium-*.css` — migracija ~93 vrednosti na tokene.
- `styles/core-shell.css` — `.top-bar` bez chrome-a; `--filmium-topbar-h`.
- `src/features/filmium/styles/filmium-layout.css` — sticky offset naslova.
- Novi hook `useCoreSetting`.
- `src/pages/CoreSettingsPage.tsx` — prekidač.
- `src/pages/FilmiumLibraryPage.tsx` (i ostale strane sa `.section-heading`) — uslovni prikaz naslova.
