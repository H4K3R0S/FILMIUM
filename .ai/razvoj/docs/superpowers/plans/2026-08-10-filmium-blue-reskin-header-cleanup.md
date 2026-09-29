---
id: filmium-0ed579cd-2026-08-10-filmium-blue-reskin-header-cleanup-md
type: plan
domain: filmium
namespace: global
visibility: global
tier: domain
title: Filmium plavi re-skin, čist CORE header i toggle naslova — Implementation Plan
summary: '> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development
  (recommended) or superpowers:executing-plans to implement this plan t'
keywords:
- filmium
- plavi
- skin
- čist
- core
- header
- toggle
- naslova
- implementation
- docs
tags:
- superpowers
- plans
source_path: docs/superpowers/plans/2026-08-10-filmium-blue-reskin-header-cleanup.md
---

# Filmium plavi re-skin, čist CORE header i toggle naslova — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Pod Filmium domenom svi akcenti su nijanse plave (iz jednog token sloja), CORE dashboard header je bez panel-chrome-a, a naslov programa je skriven po defaultu sa prekidačem u CORE Settings.

**Architecture:** Semantički RGB tokeni definisani u `styles/themes/core.css` (CORE default), a `styles/themes/filmium.css` prepisuje samo te kanale u plavo. Svi hardkodovani ljubičasti u Filmium CSS-u referenciraju tokene (alfa ostaje inline). CORE header gubi pozadinu/ivicu/blur. Globalno podešavanje (`localStorage`) kroz `useCoreSetting` hook kontroliše prikaz `.section-heading`, koji kada je uključen postaje sticky ispod trake.

**Tech Stack:** React 19 + react-router, TypeScript, Vitest + @testing-library, čist CSS (custom properties).

## Global Constraints

- Test runner: `npm test` (`vitest run`) iz `apps/gui/`. Watch: `npm run test:watch`.
- Sve komit poruke, kod, komentari, doc-ovi — normalna proza (srpski, u stilu postojećeg koda). Komentari u CSS/TSX na srpskom, sekcijski baneri `// ====… NASLOV ====` kao u okolnom kodu.
- Boje se referenciraju isključivo preko `rgba(var(--token), α)` / `rgb(var(--token))`; nema novih hardkodovanih heks/rgb akcenata u Filmium CSS-u.
- Opisi filmova i serija ostaju beli — ne migrirati bele/near-bele tekst boje (`#f8fafc`, `#e2e8f0`, `#cbd5e1`, slate sivi tonovi).
- Commit poruke završiti sa: `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`.
- Radi se na `apps/gui/`; svi putevi u planu su relativni na taj folder osim ako nije drugačije naznačeno.

### Kanonsko value→token mapiranje (koristi se u Task 2)

Primenjuje se na sve `.css` u `src/features/filmium/`:

| Izvorna vrednost (heks + rgb triplet) | Token |
|---|---|
| `#a855f7` / `168, 85, 247`, `#8b5cf6` / `139, 92, 246`, `#7c3aed` / `124, 58, 237` | `--domain-accent-rgb` |
| `#7e22ce` / `126, 34, 206`, `#6d28d9` / `109, 40, 217`, `#5b21b6` / `91, 33, 182`, `#581c87` / `88, 28, 135`, `88, 28, 172` | `--domain-accent-strong-rgb` |
| `#a78bfa` / `167, 139, 250`, `#c4b5fd` / `196, 181, 253`, `#d8b4fe` / `216, 180, 254`, `#c084fc` / `192, 132, 252` | `--domain-accent-soft-rgb` |
| `#f3e8ff` / `243, 232, 255`, `#e9d5ff` / `233, 213, 255` | `--domain-accent-contrast-rgb` |

Transformacija čuva omotač i alfu: `rgba(139, 92, 246, 0.5)` → `rgba(var(--domain-accent-rgb), 0.5)`; `rgb(139, 92, 246)` → `rgb(var(--domain-accent-rgb))`; `#a855f7` → `rgb(var(--domain-accent-rgb))`.

---

## Task 1: Token sloj (core.css default + filmium.css plavi override)

**Files:**
- Modify: `src/styles/themes/core.css`
- Modify: `src/styles/themes/filmium.css`

**Interfaces:**
- Produces: CSS custom properties dostupne globalno — `--domain-accent-rgb`, `--domain-accent-strong-rgb`, `--domain-accent-soft-rgb`, `--domain-accent-contrast-rgb` (RGB kanali, npr. `88, 182, 255`) i izvedeni `--domain-accent-strong`, `--domain-accent-soft`, `--domain-accent-contrast`.

- [ ] **Step 1: Dodaj tokene u `core.css`**

Zameni telo `:root` bloka tako da ukey postojeći sadržaj + novi kanali:

```css
:root {
  /* Visina custom titlebara (bez OS okvira). */
  --titlebar-h: 34px;

  /* CORE potpisna boja — svetlo plava. */
  --domain-accent-rgb: 88, 182, 255;
  --domain-accent-2-rgb: 88, 182, 255;

  /* Semantički akcentni kanali — domeni prepisuju samo *-rgb. */
  --domain-accent-strong-rgb: 37, 99, 235;   /* zasićeni fill: aktivna dugmad/pozadine */
  --domain-accent-soft-rgb: 147, 197, 253;    /* svetli tekst/label: eyebrow, badge, sat */
  --domain-accent-contrast-rgb: 224, 240, 255; /* near-white akcent tekst */

  /* Izvedeni tokeni — domeni ih obično ne diraju, samo *-rgb kanale. */
  --domain-accent: rgb(var(--domain-accent-rgb));
  --domain-accent-2: rgb(var(--domain-accent-2-rgb));
  --domain-accent-strong: rgb(var(--domain-accent-strong-rgb));
  --domain-accent-soft: rgb(var(--domain-accent-soft-rgb));
  --domain-accent-contrast: rgb(var(--domain-accent-contrast-rgb));
  --domain-glow: rgba(var(--domain-accent-rgb), 0.16);
  --titlebar-title: var(--domain-accent);
}
```

- [ ] **Step 2: Dodaj plavi override u `filmium.css`**

Zameni telo `[data-domain="filmium"]`:

```css
[data-domain="filmium"] {
  /* Filmium plava paleta — prepisuje samo kanale, ostalo nasleđuje CORE. */
  --domain-accent-rgb: 43, 77, 200;          /* royal plava — ivice, glow, aktivni outline */
  --domain-accent-2-rgb: 43, 77, 200;
  --domain-accent-strong-rgb: 30, 58, 138;    /* tamnija plava — aktivni fill */
  --domain-accent-soft-rgb: 125, 165, 255;    /* svetlija plava — label/tekst */
  --domain-accent-contrast-rgb: 224, 236, 255; /* near-white plavkasti tekst */
}
```

- [ ] **Step 3: Verifikuj da build/typecheck prolazi**

Run: `npm test`
Expected: PASS (nema promena ponašanja; postojeći testovi zeleni).

- [ ] **Step 4: Commit**

```bash
git add src/styles/themes/core.css src/styles/themes/filmium.css
git commit -m "feat(gui): semantički akcentni tokeni + Filmium plavi override

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 2: Migracija Filmium CSS boja na tokene

Migracija koristi kanonsko mapiranje iz Global Constraints. Radi se u tri grupe fajlova; svaka grupa je zaseban commit sa grep-verifikacijom.

**Files (sve u `src/features/filmium/`):**
- Modify grupa A (browsing): `styles/filmium-layout.css`, `styles/filmium-catalog.css`, `styles/filmium-navigation.css`, `styles/filmium-library.css`, `styles/filmium-genres.css`, `components/layout/filmium-command.css`
- Modify grupa B (sadržaj/home): `styles/filmium-home.css`, `styles/filmium-assets.css`, `styles/filmium-pages.css`, `styles/filmium-media-editor.css`, `styles/filmium-history.css`, `styles/filmium-form.css`, `styles/filmium-library-picker.css`
- Modify grupa C (uploads/alati): `styles/filmium-uploads.css`, `styles/filmium-uploads-layout.css`, `styles/filmium-series-import.css`, `styles/filmium-library-scan-results.css`, `styles/filmium-subtitles.css`, `styles/filmium-share.css`

**Interfaces:**
- Consumes: tokeni iz Task 1.
- Produces: nema JS interfejsa; CSS sada plav pod Filmium domenom.

- [ ] **Step 1: Migriraj grupu A**

Za svaki fajl u grupi A primeni zamene po mapiranju. Deterministički `sed` po vrednosti (pokreni iz `apps/gui/`):

```bash
for f in \
  src/features/filmium/styles/filmium-layout.css \
  src/features/filmium/styles/filmium-catalog.css \
  src/features/filmium/styles/filmium-navigation.css \
  src/features/filmium/styles/filmium-library.css \
  src/features/filmium/styles/filmium-genres.css \
  src/features/filmium/components/layout/filmium-command.css; do
  sed -i -E \
    -e 's/168, ?85, ?247/var(--domain-accent-rgb)/g' \
    -e 's/139, ?92, ?246/var(--domain-accent-rgb)/g' \
    -e 's/124, ?58, ?237/var(--domain-accent-rgb)/g' \
    -e 's/126, ?34, ?206/var(--domain-accent-strong-rgb)/g' \
    -e 's/109, ?40, ?217/var(--domain-accent-strong-rgb)/g' \
    -e 's/91, ?33, ?182/var(--domain-accent-strong-rgb)/g' \
    -e 's/88, ?28, ?135/var(--domain-accent-strong-rgb)/g' \
    -e 's/88, ?28, ?172/var(--domain-accent-strong-rgb)/g' \
    -e 's/167, ?139, ?250/var(--domain-accent-soft-rgb)/g' \
    -e 's/196, ?181, ?253/var(--domain-accent-soft-rgb)/g' \
    -e 's/216, ?180, ?254/var(--domain-accent-soft-rgb)/g' \
    -e 's/192, ?132, ?252/var(--domain-accent-soft-rgb)/g' \
    -e 's/243, ?232, ?255/var(--domain-accent-contrast-rgb)/g' \
    -e 's/233, ?213, ?255/var(--domain-accent-contrast-rgb)/g' \
    -e 's/#a855f7/rgb(var(--domain-accent-rgb))/gi' \
    -e 's/#8b5cf6/rgb(var(--domain-accent-rgb))/gi' \
    -e 's/#7c3aed/rgb(var(--domain-accent-rgb))/gi' \
    -e 's/#7e22ce/rgb(var(--domain-accent-strong-rgb))/gi' \
    -e 's/#6d28d9/rgb(var(--domain-accent-strong-rgb))/gi' \
    -e 's/#5b21b6/rgb(var(--domain-accent-strong-rgb))/gi' \
    -e 's/#581c87/rgb(var(--domain-accent-strong-rgb))/gi' \
    -e 's/#a78bfa/rgb(var(--domain-accent-soft-rgb))/gi' \
    -e 's/#c4b5fd/rgb(var(--domain-accent-soft-rgb))/gi' \
    -e 's/#d8b4fe/rgb(var(--domain-accent-soft-rgb))/gi' \
    -e 's/#c084fc/rgb(var(--domain-accent-soft-rgb))/gi' \
    -e 's/#f3e8ff/rgb(var(--domain-accent-contrast-rgb))/gi' \
    -e 's/#e9d5ff/rgb(var(--domain-accent-contrast-rgb))/gi' \
    "$f"
done
```

Zatim ručno pregledaj `git diff` grupe A: potvrdi da je svaka zamena u ulozi koja odgovara tokenu (fill vs tekst vs ivica); ako je neki `-strong` iskorišćen kao svetli tekst ili obrnuto, ispravi na odgovarajući token. Beli/slate tonovi (opisi) ostaju netaknuti.

- [ ] **Step 2: Grep-verifikuj grupu A**

Run:
```bash
grep -rIiE "a855f7|8b5cf6|7c3aed|7e22ce|6d28d9|5b21b6|581c87|a78bfa|c4b5fd|d8b4fe|c084fc|f3e8ff|e9d5ff|168, ?85, ?247|139, ?92, ?246|124, ?58, ?237|126, ?34, ?206|109, ?40, ?217|91, ?33, ?182|88, ?28, ?135|88, ?28, ?172|167, ?139, ?250|196, ?181, ?253|216, ?180, ?254|192, ?132, ?252|243, ?232, ?255|233, ?213, ?255" \
  src/features/filmium/styles/filmium-layout.css \
  src/features/filmium/styles/filmium-catalog.css \
  src/features/filmium/styles/filmium-navigation.css \
  src/features/filmium/styles/filmium-library.css \
  src/features/filmium/styles/filmium-genres.css \
  src/features/filmium/components/layout/filmium-command.css
```
Expected: prazan izlaz (nula pogodaka).

- [ ] **Step 3: Commit grupe A**

```bash
git add src/features/filmium/styles/filmium-layout.css src/features/filmium/styles/filmium-catalog.css src/features/filmium/styles/filmium-navigation.css src/features/filmium/styles/filmium-library.css src/features/filmium/styles/filmium-genres.css src/features/filmium/components/layout/filmium-command.css
git commit -m "refactor(gui): Filmium browsing CSS na akcentne tokene (plavo)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

- [ ] **Step 4: Migriraj grupu B** — isti `sed` blok kao Step 1, ali sa listom fajlova grupe B. Zatim ručni pregled `git diff` (isti kriterijum).

- [ ] **Step 5: Grep-verifikuj grupu B** — isti grep kao Step 2, sa fajlovima grupe B. Expected: prazan izlaz.

- [ ] **Step 6: Commit grupe B**

```bash
git add src/features/filmium/styles/filmium-home.css src/features/filmium/styles/filmium-assets.css src/features/filmium/styles/filmium-pages.css src/features/filmium/styles/filmium-media-editor.css src/features/filmium/styles/filmium-history.css src/features/filmium/styles/filmium-form.css src/features/filmium/styles/filmium-library-picker.css
git commit -m "refactor(gui): Filmium sadržaj/home CSS na akcentne tokene (plavo)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

- [ ] **Step 7: Migriraj grupu C** — isti `sed` blok, lista fajlova grupe C. Ručni pregled `git diff`.

- [ ] **Step 8: Grep-verifikuj grupu C** — isti grep, fajlovi grupe C. Expected: prazan izlaz.

- [ ] **Step 9: Globalna grep-verifikacija celog Filmium foldera**

Run:
```bash
grep -rIiE "a855f7|8b5cf6|7c3aed|7e22ce|6d28d9|5b21b6|581c87|a78bfa|c4b5fd|d8b4fe|c084fc|f3e8ff|e9d5ff|168, ?85, ?247|139, ?92, ?246|124, ?58, ?237|126, ?34, ?206|109, ?40, ?217|91, ?33, ?182|88, ?28, ?135|167, ?139, ?250|196, ?181, ?253|216, ?180, ?254|192, ?132, ?252|243, ?232, ?255|233, ?213, ?255" src/features/filmium --include=*.css
```
Expected: prazan izlaz. Ako nešto ostane, migriraj taj fajl istim `sed`-om.

- [ ] **Step 10: Testovi prolaze**

Run: `npm test`
Expected: PASS.

- [ ] **Step 11: Commit grupe C**

```bash
git add src/features/filmium/styles/filmium-uploads.css src/features/filmium/styles/filmium-uploads-layout.css src/features/filmium/styles/filmium-series-import.css src/features/filmium/styles/filmium-library-scan-results.css src/features/filmium/styles/filmium-subtitles.css src/features/filmium/styles/filmium-share.css
git commit -m "refactor(gui): Filmium uploads/alati CSS na akcentne tokene (plavo)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 3: CORE header bez chrome-a + tokenizacija sata

**Files:**
- Modify: `src/styles/core-shell.css` (`.top-bar` ~528, `.header-clock-*` ~556-645)

**Interfaces:**
- Consumes: tokeni iz Task 1.
- Produces: `.top-bar` bez pozadine/ivice/blur; sat koristi `--domain-accent-soft`.

- [ ] **Step 1: Skini chrome sa `.top-bar`**

Zameni `.top-bar` pravilo (core-shell.css:528):

```css
.top-bar {
  position: relative;
  height: 128px;
}
```

(uklonjeni `border-bottom`, `background`, `backdrop-filter`; zone `.top-bar-lead`, `.header-clock`, `.top-bar-status` ostaju netaknute).

- [ ] **Step 2: Tokenizuj sat**

U istom fajlu zameni ljubičaste u sat pravilima:
- `.header-clock-face:hover` — `border-color: rgba(168, 85, 247, 0.28);` → `rgba(var(--domain-accent-rgb), 0.28);`, `background: rgba(168, 85, 247, 0.06);` → `rgba(var(--domain-accent-rgb), 0.06);`
- `.header-clock-colon` — `color: #c084fc;` → `color: rgb(var(--domain-accent-soft-rgb));`
- `.header-clock-seconds` — `color: #c084fc;` → `color: rgb(var(--domain-accent-soft-rgb));`

- [ ] **Step 3: Grep-verifikuj header**

Run: `grep -nIiE "168, ?85, ?247|c084fc" src/styles/core-shell.css`
Expected: prazan izlaz.

- [ ] **Step 4: Testovi prolaze**

Run: `npm test`
Expected: PASS (`AppShell.test.tsx` zelen — JSX nepromenjen).

- [ ] **Step 5: Commit**

```bash
git add src/styles/core-shell.css
git commit -m "feat(gui): CORE header bez panel-chrome-a + sat na akcentne tokene

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 4: `useCoreSetting` hook (bool podešavanje u localStorage)

**Files:**
- Create: `src/lib/useCoreSetting.ts`
- Test: `src/lib/useCoreSetting.test.ts`

**Interfaces:**
- Produces: `useCoreSetting(key: string, defaultValue: boolean): [boolean, (next: boolean) => void]` — čita/piše `localStorage`, ključ prosleđen direktno; tolerantan na nedostupan/nevalidan storage (pada na `defaultValue`).

- [ ] **Step 1: Napiši failing test**

```ts
import { act, renderHook } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { useCoreSetting } from "./useCoreSetting";

describe("useCoreSetting", () => {
  afterEach(() => {
    window.localStorage.clear();
  });

  it("vraća default kada nema zapisane vrednosti", () => {
    const { result } = renderHook(() =>
      useCoreSetting("core.test.flag", false),
    );

    expect(result.current[0]).toBe(false);
  });

  it("čita zapisanu vrednost iz localStorage", () => {
    window.localStorage.setItem("core.test.flag", "true");

    const { result } = renderHook(() =>
      useCoreSetting("core.test.flag", false),
    );

    expect(result.current[0]).toBe(true);
  });

  it("upisuje novu vrednost i pamti je", () => {
    const { result } = renderHook(() =>
      useCoreSetting("core.test.flag", false),
    );

    act(() => {
      result.current[1](true);
    });

    expect(result.current[0]).toBe(true);
    expect(window.localStorage.getItem("core.test.flag")).toBe("true");
  });
});
```

- [ ] **Step 2: Pokreni test — mora da padne**

Run: `npm test -- useCoreSetting`
Expected: FAIL ("Cannot find module './useCoreSetting'").

- [ ] **Step 3: Napiši `useCoreSetting.ts`**

```ts
import { useCallback, useState } from "react";


// ==========          GLOBALNO CORE PODEŠAVANJE          ==========

/**
 * Čita i pamti jedno bulean CORE podešavanje u localStorage.
 *
 * Tolerantan na nedostupan ili nevalidan storage — u tom slučaju pada na
 * prosleđenu podrazumevanu vrednost bez bacanja greške.
 */
export function useCoreSetting(
  key: string,
  defaultValue: boolean,
): [boolean, (next: boolean) => void] {
  const [value, setValue] = useState<boolean>(() => {
    if (typeof window === "undefined") {
      return defaultValue;
    }

    const stored = window.localStorage.getItem(key);

    if (stored === null) {
      return defaultValue;
    }

    return stored === "true";
  });

  const update = useCallback(
    (next: boolean) => {
      setValue(next);

      if (typeof window !== "undefined") {
        window.localStorage.setItem(key, String(next));
      }
    },
    [key],
  );

  return [value, update];
}
```

- [ ] **Step 4: Pokreni test — mora da prođe**

Run: `npm test -- useCoreSetting`
Expected: PASS (3 testa).

- [ ] **Step 5: Commit**

```bash
git add src/lib/useCoreSetting.ts src/lib/useCoreSetting.test.ts
git commit -m "feat(gui): useCoreSetting hook za bulean localStorage podešavanja

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 5: CORE Settings prekidač za naslov programa

**Files:**
- Modify: `src/pages/CoreSettingsPage.tsx`
- Test: `src/pages/CoreSettingsPage.test.tsx` (novi)

**Interfaces:**
- Consumes: `useCoreSetting` (Task 4).
- Produces: ključ podešavanja `core.filmium.showPageTitle` (default `false`) upisan u localStorage kroz UI prekidač (`role="switch"`, `aria-checked`).

- [ ] **Step 1: Napiši failing test**

```tsx
import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import CoreSettingsPage from "./CoreSettingsPage";

describe("CoreSettingsPage", () => {
  afterEach(() => {
    window.localStorage.clear();
  });

  it("prekidač za naslov je isključen po defaultu", () => {
    render(<CoreSettingsPage />);

    const toggle = screen.getByRole("switch", {
      name: /naslov programa/i,
    });

    expect(toggle).toHaveAttribute("aria-checked", "false");
  });

  it("uključivanje prekidača pamti podešavanje", () => {
    render(<CoreSettingsPage />);

    const toggle = screen.getByRole("switch", {
      name: /naslov programa/i,
    });

    fireEvent.click(toggle);

    expect(toggle).toHaveAttribute("aria-checked", "true");
    expect(
      window.localStorage.getItem("core.filmium.showPageTitle"),
    ).toBe("true");
  });
});
```

- [ ] **Step 2: Pokreni test — mora da padne**

Run: `npm test -- CoreSettingsPage`
Expected: FAIL (nema `switch` role — trenutna strana je placeholder).

- [ ] **Step 3: Implementiraj prekidač**

Zameni `CoreSettingsPage.tsx`:

```tsx
import { useCoreSetting } from "../lib/useCoreSetting";


// ==========          CORE PODEŠAVANJA EKRAN          ==========

/**
 * Globalna CORE podešavanja. Trenutno: prikaz naslova programa u Filmium
 * bibliotečkim prikazima (podrazumevano isključen).
 */
function CoreSettingsPage() {
  const [showPageTitle, setShowPageTitle] = useCoreSetting(
    "core.filmium.showPageTitle",
    false,
  );

  return (
    <section className="filmium-section filmium-placeholder-page">
      <div className="section-heading">
        <p className="eyebrow">CORE System</p>
        <h2>Core Settings</h2>
      </div>

      <div className="core-settings-row">
        <div className="core-settings-copy">
          <strong>Naslov programa (Filmium)</strong>
          <span>
            Prikaži naslov trenutnog prikaza iznad kataloga. Podrazumevano
            isključeno radi čistijeg interfejsa.
          </span>
        </div>

        <button
          aria-checked={showPageTitle}
          aria-label="Naslov programa (Filmium)"
          className={`core-settings-toggle ${
            showPageTitle ? "on" : ""
          }`}
          onClick={() => setShowPageTitle(!showPageTitle)}
          role="switch"
          type="button"
        >
          <span aria-hidden="true" className="core-settings-toggle-knob" />
        </button>
      </div>
    </section>
  );
}

export default CoreSettingsPage;
```

- [ ] **Step 4: Dodaj stil prekidača**

Dodaj na kraj `src/styles/core-shell.css`:

```css
/* ==========          CORE SETTINGS PREKIDAČ          ========== */

.core-settings-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 24px;
  max-width: 560px;
  margin-top: 22px;
  padding: 16px 18px;
  border: 1px solid rgba(148, 163, 184, 0.16);
  border-radius: 14px;
  background: rgba(15, 23, 42, 0.34);
}

.core-settings-copy {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.core-settings-copy strong {
  color: #f8fafc;
  font-size: 0.9rem;
}

.core-settings-copy span {
  color: #94a3b8;
  font-size: 0.76rem;
}

.core-settings-toggle {
  position: relative;
  flex: 0 0 auto;
  width: 46px;
  height: 26px;
  padding: 0;
  border: 1px solid rgba(148, 163, 184, 0.24);
  border-radius: 999px;
  background: rgba(15, 23, 42, 0.6);
  cursor: pointer;
  transition:
    border-color 150ms ease,
    background 150ms ease;
}

.core-settings-toggle.on {
  border-color: rgba(var(--domain-accent-rgb), 0.6);
  background: rgba(var(--domain-accent-rgb), 0.32);
}

.core-settings-toggle-knob {
  position: absolute;
  top: 50%;
  left: 3px;
  width: 18px;
  height: 18px;
  transform: translateY(-50%);
  border-radius: 50%;
  background: #e2e8f0;
  transition: left 150ms ease;
}

.core-settings-toggle.on .core-settings-toggle-knob {
  left: 23px;
  background: rgb(var(--domain-accent-contrast-rgb));
}
```

- [ ] **Step 5: Pokreni test — mora da prođe**

Run: `npm test -- CoreSettingsPage`
Expected: PASS (2 testa).

- [ ] **Step 6: Commit**

```bash
git add src/pages/CoreSettingsPage.tsx src/pages/CoreSettingsPage.test.tsx src/styles/core-shell.css
git commit -m "feat(gui): CORE Settings prekidač za prikaz naslova programa

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 6: Uslovni prikaz naslova + sticky offset

Naslov (`.section-heading`) skriva/pokazuje se globalno preko atributa na Filmium radnom kontejneru; CSS radi skrivanje i sticky. Time se dira samo `FilmiumWorkspace.tsx` (jedan izvor), ne svaka strana.

**Files:**
- Modify: `src/features/filmium/context/FilmiumWorkspace.tsx`
- Modify: `src/features/filmium/styles/filmium-layout.css`
- Modify: `src/features/filmium/context/FilmiumWorkspace.test.tsx`

**Interfaces:**
- Consumes: `useCoreSetting` (Task 4), ključ `core.filmium.showPageTitle`.
- Produces: atribut `data-page-title="on"|"off"` na `.filmium-domain-workspace`; CSS promenljiva `--filmium-topbar-h`.

- [ ] **Step 1: Napiši failing test**

Dodaj u `FilmiumWorkspace.test.tsx` (unutar postojećeg opisa; prilagodi import helpera renderu koji test fajl već koristi):

```tsx
it("naslov programa je skriven po defaultu (data-page-title off)", () => {
  const { container } = renderWorkspace();

  const workspace = container.querySelector(".filmium-domain-workspace");

  expect(workspace).toHaveAttribute("data-page-title", "off");
});

it("uključeno podešavanje prikazuje naslov (data-page-title on)", () => {
  window.localStorage.setItem("core.filmium.showPageTitle", "true");

  const { container } = renderWorkspace();

  const workspace = container.querySelector(".filmium-domain-workspace");

  expect(workspace).toHaveAttribute("data-page-title", "on");
});
```

Ako postojeći test fajl nema `renderWorkspace` helper, koristi isti render obrazac (router + provider) koji test fajl već koristi za montiranje `FilmiumWorkspaceProvider`, i očisti `localStorage` u `afterEach`.

- [ ] **Step 2: Pokreni test — mora da padne**

Run: `npm test -- FilmiumWorkspace`
Expected: FAIL (nema `data-page-title` atributa).

- [ ] **Step 3: Postavi atribut u `FilmiumWorkspace.tsx`**

Dodaj import na vrh:

```tsx
import { useCoreSetting } from "../../../lib/useCoreSetting";
```

Unutar `FilmiumWorkspaceProvider`, pre `return`, pročitaj podešavanje:

```tsx
const [showPageTitle] = useCoreSetting(
  "core.filmium.showPageTitle",
  false,
);
```

Dodaj atribut na `.filmium-domain-workspace` div:

```tsx
<div
  className="filmium-domain-workspace"
  data-page-title={showPageTitle ? "on" : "off"}
>
```

- [ ] **Step 4: Dodaj CSS za skrivanje + sticky**

Na kraj `src/features/filmium/styles/filmium-layout.css` dodaj (i definiši `--filmium-topbar-h` u `.filmium-workspace-content`):

```css
/* ==========          NASLOV PROGRAMA (TOGGLE)          ========== */

.filmium-workspace-content {
  --filmium-topbar-h: 82px;
}

/* Skriven po defaultu — čist interfejs, bez preklapanja sa sticky trakom. */
.filmium-domain-workspace[data-page-title="off"] .section-heading {
  display: none;
}

/* Uključen — zaključava se ispod sticky trake, sa malim odvajanjem. */
.filmium-domain-workspace[data-page-title="on"] .section-heading {
  position: sticky;
  top: var(--filmium-topbar-h);
  z-index: 10;
}
```

- [ ] **Step 5: Pokreni test — mora da prođe**

Run: `npm test -- FilmiumWorkspace`
Expected: PASS.

- [ ] **Step 6: Ceo test paket prolazi**

Run: `npm test`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add src/features/filmium/context/FilmiumWorkspace.tsx src/features/filmium/context/FilmiumWorkspace.test.tsx src/features/filmium/styles/filmium-layout.css
git commit -m "feat(gui): naslov programa skriven default + sticky kad je uključen

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 7: Vizuelna verifikacija i finalno štimovanje

**Files:** (samo eventualne korekcije boja u `src/styles/themes/filmium.css`)

- [ ] **Step 1: Pokreni dev server u preview alatu**

Napravi/koristi `.claude/launch.json` unos za GUI dev server (`npm run dev` u `apps/gui/`, port po Vite konfiguraciji) i otvori preview.

- [ ] **Step 2: Filmium plava provera**

Navigiraj na `/filmium/library`. Potvrdi: search bar ivica, aktivna FILM/SERIJE dugmad, žanr čipovi, hover stanja, notifikacione tačke — sve plavo; nijedan ljubičasti akcenat. Opisi filmova/serija ostaju beli. Ako je neka nijansa pretamna/presvetla, štimuj kanale u `filmium.css` i ponovi.

- [ ] **Step 3: CORE header provera**

Navigiraj na `/dashboard`. Potvrdi: nema linije razdvajanja ni panel-pozadine na vrhu; tri elementa (levo CORE control+naslov, centar sat, desno System status) na svojim pozicijama; colon/sekunde sata plavi.

- [ ] **Step 4: Toggle naslova provera**

Na `/filmium/library` skroluj — bez naslova nema preklapanja. Uključi prekidač na `/settings`, vrati se na `/filmium/library`, skroluj — naslov se zaključava ispod trake sa odvajanjem, oba vidljiva. Ako je offset (`--filmium-topbar-h`) premali/preveliki, koriguj i ponovi.

- [ ] **Step 5: Screenshot dokaz** — snimi Filmium library i CORE dashboard i podeli sa korisnikom.

- [ ] **Step 6: Finalni commit (ako je bilo štimovanja)**

```bash
git add src/styles/themes/filmium.css src/features/filmium/styles/filmium-layout.css
git commit -m "fix(gui): štimovanje Filmium plave palete i offset naslova

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Self-Review (popunjeno)

**Spec coverage:**
- Filmium plavo / token izvor istine → Task 1 + Task 2. ✓
- CORE header bez chrome-a, tri zone ostaju → Task 3. ✓
- Sat tokenizacija (sitno) → Task 3. ✓
- Naslov skriven default + CORE Settings toggle → Task 4 + 5 + 6. ✓
- Sticky bez preklapanja kad je naslov uključen → Task 6. ✓
- Opisi ostaju beli → Global Constraint + Task 2 ručni pregled. ✓

**Placeholder scan:** Nema TBD/TODO; svi koraci imaju konkretan kod ili tačne komande. ✓

**Type consistency:** `useCoreSetting(key, default): [boolean, (next: boolean) => void]` — isti potpis u Task 4 (definicija), Task 5 i Task 6 (potrošnja); ključ `core.filmium.showPageTitle` identičan svuda; atribut `data-page-title` sa vrednostima `on`/`off` dosledno u TSX (Task 6 Step 3) i CSS (Task 6 Step 4). ✓
