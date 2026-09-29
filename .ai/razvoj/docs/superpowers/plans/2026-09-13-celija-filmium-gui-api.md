# Ćelija FILMIUM — GUI i API (plan implementacije)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Da FILMIUM ćelija na `F:\FILMIUM\` pri pokretanju digne jedan proces koji služi i ceo FILMIUM API i FILMIUM GUI, otvori browser, i da se biblioteka stvarno koristi iz ćelijske baze.

**Architecture:** GUI ćelije je poseban Vite ulaz (`apps/gui/cell.html` → `src/cell/cellMain.tsx`) koji koristi iste FILMIUM stranice kao CORE, uz dve zamene CORE-only modula definisane u jednoj mapi (`apps/gui/cell-substitutions.json`). Python sklapač iz te iste mape računa zatvorenje GUI uvoza, kopira izvor u ćeliju i pravi gotov build. `cell_app.py` preusmerava putanje pre uvoza routera, montira 16 FILMIUM routera, ćelijske rute i statički build.

**Tech Stack:** Python 3.14, FastAPI, Starlette `StaticFiles`, pytest; React 19, react-router 8, Vite 8, TypeScript 6, Vitest 4.

**Spec:** `docs/superpowers/specs/2026-09-12-celijski-sistem-filmium-design.md` (odeljak 15 je izvor za ovaj plan; odeljci 1–14 i dalje važe)

## Global Constraints

- Pytest isključivo kroz venv: `./.venv/Scripts/python.exe -m pytest` (iz korena repoa). Vitest i build iz `apps/gui`: `npx vitest run <putanja>`, `npx tsc -b tsconfig.app.json tsconfig.node.json`, `npx vite build ...`.
- Bez novih pip i npm zavisnosti. Starlette `StaticFiles` radi bez `aiofiles` (provereno).
- Ništa se ne briše iz repoa. CORE ponašanje se ne menja: CORE GUI u Tauri prozoru radi isto kao pre; `apps/api/main.py` ne registruje ćelijske rute.
- Poznat zatečen pad: `tests/test_dependencies.py::test_every_installable_dependency_has_install_script`. Stanje pre ovog plana: `1 failed, 2260 passed, 38 skipped, 1 warning`.
- Poznat zatečen CORE GUI test status nije meren na početku — Task 1 ga meri pre prve izmene i zapisuje u izveštaj.
- Komentari i docstring-ovi na srpskom; korisnički tekst u GUI-ju na srpskom.
- Pravi TMDB ključ nikad ne ulazi u ćeliju, u izveštaje ni u commit poruke.
- Rad na grani `feat/celija-filmium-gui`.
- Port ćelije je 8781; API i GUI su na istom originu, `VITE_CORE_API_URL` je u ćelijskom buildu prazan string.
- Mapa zamena (`apps/gui/cell-substitutions.json`) je jedini izvor istine o zamenama; ni Vite konfiguracija ni Python ne smeju da je dupliraju.

---

### Task 1: `pathPicker` — biranje putanje u Tauri prozoru i u browseru

**Files:**
- Create: `apps/gui/src/lib/pathPicker.ts`
- Create: `apps/gui/src/lib/pathPicker.test.ts`
- Modify: `apps/gui/src/features/filmium/components/uploads/FilmiumAutoImportPanel.tsx` (uvoz `open` iz `@tauri-apps/plugin-dialog`, poziv oko linije 57)
- Modify: `apps/gui/src/features/filmium/components/uploads/FilmiumLibraryManager.tsx` (uvoz, poziv oko linije 170)
- Modify: `apps/gui/src/features/filmium/hooks/useFilmiumSeriesImport.ts` (uvoz, poziv oko linije 47)
- Modify: `apps/gui/src/features/filmium/utils/replaceArtwork.ts` (uvoz, poziv oko linije 19)
- Modify: `apps/gui/src/pages/FilmiumSharePage.tsx` (uvoz, pozivi oko linija 188 i 214)
- Modify: `apps/gui/src/features/filmium/components/uploads/FilmiumAutoImportPanel.test.tsx` (mock sa `@tauri-apps/plugin-dialog` prelazi na `lib/pathPicker`)

**Interfaces:**
- Consumes: ništa.
- Produces:
  - `isTauriRuntime(): boolean`
  - `openPathDialog(options?: OpenDialogOptions): Promise<string | string[] | null>` — isti oblik opcija kao Tauri `open`

- [ ] **Step 1: Izmeri zatečeno stanje GUI testova**

Run (iz `apps/gui`): `npx vitest run 2>&1 | tail -6`
Zapiši tačan zbir (prošlo/palo) u izveštaj. Ako nešto već pada, to je zatečeno stanje i ne sme da poraste.

- [ ] **Step 2: Napiši testove koji padaju**

```ts
// apps/gui/src/lib/pathPicker.test.ts
import { afterEach, describe, expect, it, vi } from "vitest";

const openMock = vi.fn();

vi.mock("@tauri-apps/plugin-dialog", () => ({
  open: (...args: unknown[]) => openMock(...args),
}));

import { isTauriRuntime, openPathDialog } from "./pathPicker";

type TauriWindow = Window & { __TAURI_INTERNALS__?: unknown };

afterEach(() => {
  delete (window as TauriWindow).__TAURI_INTERNALS__;
  openMock.mockReset();
  vi.restoreAllMocks();
});

describe("isTauriRuntime", () => {
  it("vraća false u običnom browseru", () => {
    expect(isTauriRuntime()).toBe(false);
  });

  it("vraća true kad postoji Tauri most", () => {
    (window as TauriWindow).__TAURI_INTERNALS__ = {};
    expect(isTauriRuntime()).toBe(true);
  });
});

describe("openPathDialog", () => {
  it("u Tauri prozoru zove pravi dijalog sa istim opcijama", async () => {
    (window as TauriWindow).__TAURI_INTERNALS__ = {};
    openMock.mockResolvedValue("F:\\Filmovi");

    const result = await openPathDialog({ directory: true, title: "Folder" });

    expect(openMock).toHaveBeenCalledWith({ directory: true, title: "Folder" });
    expect(result).toBe("F:\\Filmovi");
  });

  it("u browseru traži da se putanja upiše", async () => {
    const promptSpy = vi.spyOn(window, "prompt").mockReturnValue("  F:\\Filmovi  ");

    const result = await openPathDialog({ directory: true });

    expect(openMock).not.toHaveBeenCalled();
    expect(promptSpy).toHaveBeenCalledOnce();
    expect(result).toBe("F:\\Filmovi");
  });

  it("u browseru vraća null kad korisnik odustane ili ostavi prazno", async () => {
    vi.spyOn(window, "prompt").mockReturnValueOnce(null).mockReturnValueOnce("   ");

    expect(await openPathDialog({ directory: true })).toBeNull();
    expect(await openPathDialog({ directory: true })).toBeNull();
  });

  it("u browseru vraća niz kad je traženo više putanja", async () => {
    vi.spyOn(window, "prompt").mockReturnValue("F:\\a.jpg");

    expect(await openPathDialog({ multiple: true })).toEqual(["F:\\a.jpg"]);
  });
});
```

- [ ] **Step 3: Pokreni test i potvrdi da pada**

Run (iz `apps/gui`): `npx vitest run src/lib/pathPicker.test.ts`
Expected: FAIL — `Failed to resolve import "./pathPicker"`

- [ ] **Step 4: Napiši implementaciju**

```ts
// apps/gui/src/lib/pathPicker.ts
import { open, type OpenDialogOptions } from "@tauri-apps/plugin-dialog";


// ==========          BIRANJE PUTANJE          ==========

/**
 * Da li GUI radi u Tauri prozoru.
 *
 * Proverava se Tauri most na `window`, a ne uvozom window manager-a — ovaj
 * modul mora da radi i u FILMIUM ćeliji, koja nema CORE window sistem.
 */
export function isTauriRuntime(): boolean {
  return typeof window !== "undefined" && "__TAURI_INTERNALS__" in window;
}

/**
 * Otvara dijalog za izbor putanje.
 *
 * U Tauri prozoru je to pravi sistemski dijalog. U browseru (FILMIUM ćelija)
 * sistemski dijalog ne postoji, pa se putanja upisuje ručno. Prazan unos ili
 * odustajanje vraćaju `null`, isto kao zatvoren Tauri dijalog.
 */
export async function openPathDialog(
  options: OpenDialogOptions = {},
): Promise<string | string[] | null> {
  if (isTauriRuntime()) {
    return open(options);
  }

  const vrsta = options.directory ? "folder" : "fajl";
  const naslov = options.title ?? `Upiši punu putanju (${vrsta})`;
  const pocetna =
    typeof options.defaultPath === "string" ? options.defaultPath : "";

  const unos = window.prompt(naslov, pocetna)?.trim();

  if (!unos) {
    return null;
  }

  return options.multiple ? [unos] : unos;
}
```

Ako `OpenDialogOptions` nije izvezen iz `@tauri-apps/plugin-dialog` pod tim imenom, izvedi tip iz potpisa: `type OpenDialogOptions = NonNullable<Parameters<typeof open>[0]>;` i navedi to u izveštaju.

- [ ] **Step 5: Pokreni test i potvrdi da prolazi**

Run: `npx vitest run src/lib/pathPicker.test.ts`
Expected: PASS, 6 testova

- [ ] **Step 6: Prebaci pet FILMIUM fajlova na `openPathDialog`**

U svakom od pet fajlova iz liste `Modify` zameni `import { open } from "@tauri-apps/plugin-dialog";` uvozom `import { openPathDialog } from "<relativna putanja>/lib/pathPicker";` i svaki poziv `open({...})` pozivom `openPathDialog({...})` sa istim opcijama. Ne menjaj ništa drugo u tim fajlovima. Ako TypeScript prijavi da rezultat više nije uži tip (npr. mesto koje je očekivalo `string | null`), dodaj postojeću proveru `typeof selected === "string"` tamo gde je već nema — ne `as` kastovanje.

U `FilmiumAutoImportPanel.test.tsx` zameni `vi.mock("@tauri-apps/plugin-dialog", ...)` mock-om `lib/pathPicker` modula koji izlaže `openPathDialog` sa istim ponašanjem koje je test do sada davao `open`-u, i `isTauriRuntime` koji vraća `true`.

- [ ] **Step 7: Proveri tipove i sve GUI testove**

Run (iz `apps/gui`): `npx tsc -b tsconfig.app.json tsconfig.node.json` — Expected: bez grešaka.
Run: `npx vitest run 2>&1 | tail -6` — Expected: isti broj padova kao u Step 1, broj prolaza veći za 6.
Run: `grep -rn "@tauri-apps/plugin-dialog" src --include=*.ts --include=*.tsx | grep -v "\.test\."` — Expected: samo `src/lib/pathPicker.ts`.

- [ ] **Step 8: Commit**

```bash
git add apps/gui/src/lib/pathPicker.ts apps/gui/src/lib/pathPicker.test.ts apps/gui/src/features/filmium apps/gui/src/pages/FilmiumSharePage.tsx
git commit -m "feat(gui): pathPicker — Tauri dijalog u prozoru, unos putanje u browseru"
```

---

### Task 2: FILMIUM rute kao deljeni blok

**Files:**
- Create: `apps/gui/src/features/filmium/filmiumRoutes.tsx`
- Modify: `apps/gui/src/App.tsx` (blok ispod komentara `FILMIUM WORKSPACE RUTE`, od `<Route path="/filmium" element={<FilmiumWorkspaceProvider />}>` do njegovog zatvarajućeg `</Route>`, i uvozi FILMIUM stranica na vrhu fajla)
- Test: `apps/gui/src/features/filmium/filmiumRoutes.test.tsx`

**Interfaces:**
- Consumes: ništa.
- Produces: `filmiumRoutes(): ReactElement` — vraća jedan `<Route path="/filmium">` element sa svim FILMIUM podrutama

`react-router` unutar `<Routes>` prihvata samo `<Route>` elemente, ne komponente koje ih vraćaju. Zato je ovo funkcija koja se poziva kao `{filmiumRoutes()}`, a ne komponenta `<FilmiumRoutes />`.

- [ ] **Step 1: Napiši test koji pada**

```tsx
// apps/gui/src/features/filmium/filmiumRoutes.test.tsx
import { describe, expect, it } from "vitest";
import { isValidElement } from "react";

import { filmiumRoutes } from "./filmiumRoutes";

describe("filmiumRoutes", () => {
  it("vraća jedan Route element sa putanjom /filmium", () => {
    const element = filmiumRoutes();

    expect(isValidElement(element)).toBe(true);
    expect((element.props as { path?: string }).path).toBe("/filmium");
  });

  it("nosi podrute biblioteke, torrenta i podešavanja", () => {
    const element = filmiumRoutes();
    const children = (element.props as { children: unknown }).children;
    const paths = (Array.isArray(children) ? children : [children])
      .map((child) => (child as { props?: { path?: string } }).props?.path)
      .filter(Boolean);

    expect(paths).toEqual(expect.arrayContaining(["library", "torrents", "settings"]));
  });
});
```

Ako FILMIUM podešavanja nisu pod putanjom `settings` u postojećem bloku, uskladi očekivanu listu sa stvarnim imenom putanje iz `App.tsx` i navedi to u izveštaju.

- [ ] **Step 2: Pokreni test i potvrdi da pada**

Run (iz `apps/gui`): `npx vitest run src/features/filmium/filmiumRoutes.test.tsx`
Expected: FAIL — `Failed to resolve import "./filmiumRoutes"`

- [ ] **Step 3: Premesti blok**

Napravi `filmiumRoutes.tsx` ovog oblika i u njega **doslovno premesti** ceo `<Route path="/filmium">…</Route>` blok iz `App.tsx`, zajedno sa uvozima FILMIUM stranica i `FilmiumWorkspaceProvider` koje taj blok koristi:

```tsx
// apps/gui/src/features/filmium/filmiumRoutes.tsx
import type { ReactElement } from "react";
import { Route } from "react-router";

// Uvozi FILMIUM stranica premešteni iz App.tsx — iste putanje, relativne
// na ovaj fajl (npr. "../../pages/FilmiumPage").


// ==========          FILMIUM RUTE          ==========

/**
 * Sve FILMIUM rute kao jedan `<Route>` element.
 *
 * Deli ih CORE (`App.tsx`) i FILMIUM ćelija (`cell/CellApp.tsx`), da isti
 * skup stranica ne postoji u dve kopije. Poziva se kao `{filmiumRoutes()}`.
 */
export function filmiumRoutes(): ReactElement {
  return (
    <Route path="/filmium" element={<FilmiumWorkspaceProvider />}>
      {/* doslovno premeštene podrute iz App.tsx */}
    </Route>
  );
}
```

U `App.tsx` na mesto bloka stavi `{filmiumRoutes()}`, dodaj `import { filmiumRoutes } from "./features/filmium/filmiumRoutes";` i ukloni uvoze FILMIUM stranica koji u `App.tsx` više nisu korišćeni. Uvozi koje `App.tsx` i dalje koristi van bloka (npr. `FilmiumTorrentStartupNotice`) ostaju.

- [ ] **Step 4: Proveri**

Run: `npx vitest run src/features/filmium/filmiumRoutes.test.tsx` — Expected: PASS, 2 testa.
Run: `npx tsc -b tsconfig.app.json tsconfig.node.json` — Expected: bez grešaka (`noUnusedLocals` hvata zaostale uvoze).
Run: `npx vitest run 2>&1 | tail -6` — Expected: broj padova isti kao na kraju Task 1, prolazi veći za 2; `src/App.test.tsx` prolazi.

- [ ] **Step 5: Commit**

```bash
git add apps/gui/src/features/filmium/filmiumRoutes.tsx apps/gui/src/features/filmium/filmiumRoutes.test.tsx apps/gui/src/App.tsx
git commit -m "refactor(gui): FILMIUM rute kao deljeni blok za CORE i celiju"
```

---

### Task 3: Ćelijski GUI ulaz, zamene i Vite konfiguracija

**Files:**
- Create: `apps/gui/cell-substitutions.json`
- Create: `apps/gui/cell.html`
- Create: `apps/gui/vite.cell.config.ts`
- Create: `apps/gui/src/cell/cellMain.tsx`
- Create: `apps/gui/src/cell/CellApp.tsx`
- Create: `apps/gui/src/cell/cellApi.ts`
- Create: `apps/gui/src/cell/CellAssistantChat.tsx`
- Create: `apps/gui/src/cell/CellSettingsPage.tsx`
- Test: `apps/gui/src/cell/CellAssistantChat.test.tsx`
- Test: `apps/gui/src/cell/CellSettingsPage.test.tsx`

**Interfaces:**
- Consumes: `filmiumRoutes()` (Task 2), `openPathDialog` (Task 1, posredno kroz FILMIUM stranice).
- Produces (koristi Task 4 i Task 5):
  - `apps/gui/cell-substitutions.json` — objekat `{ "<putanja u apps/gui>": "<zamenska putanja u apps/gui>" }`
  - `apps/gui/vite.cell.config.ts` — build ulaza `cell.html`, bez `outDir`-a u fajlu (prosleđuje se sa `--outDir`)
  - `cellApi.ts`: `askCurator(question: string): Promise<CuratorAnswer>`, `getCellStatus(): Promise<CellStatus>`, `listCellPersonas(): Promise<CellPersona[]>`, `saveCellPersona(id: string, markdown: string): Promise<CellPersona>`
  - tipovi `CuratorAnswer { answer: string; sources: string[]; is_fallback: boolean }`, `CellStatus { name: string; port: number; ai_endpoint: string; ai_curator_model: string | null }` (plus ostala polja iz `/cell/status`), `CellPersona { id: string; name: string; markdown: string; customized: boolean }`

- [ ] **Step 1: Mapa zamena, HTML ulaz i Vite konfiguracija**

```json
// apps/gui/cell-substitutions.json
{
  "src/features/chat/CoreAssistantChat.tsx": "src/cell/CellAssistantChat.tsx",
  "src/pages/FilmiumSettingsPage.tsx": "src/cell/CellSettingsPage.tsx"
}
```

```html
<!-- apps/gui/cell.html -->
<!doctype html>
<html lang="sr">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>FILMIUM</title>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/cell/cellMain.tsx"></script>
  </body>
</html>
```

```ts
// apps/gui/vite.cell.config.ts
import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import react from "@vitejs/plugin-react";
import { defineConfig, type Plugin } from "vite";


// ==========          VITE — FILMIUM ĆELIJA          ==========

const ROOT = __dirname;

/** Mapa zamena CORE-only modula; isti fajl čita i Python sklapač ćelije. */
const SUBSTITUTIONS: Record<string, string> = JSON.parse(
  readFileSync(resolve(ROOT, "cell-substitutions.json"), "utf-8"),
);

const normalize = (path: string): string => path.replace(/\\/g, "/");

const ZAMENE = new Map(
  Object.entries(SUBSTITUTIONS).map(([from, to]) => [
    normalize(resolve(ROOT, from)),
    resolve(ROOT, to),
  ]),
);

/**
 * Posle normalnog razrešenja uvoza, CORE-only modul menja ćelijskim.
 * Radi nad razrešenom apsolutnom putanjom, pa ne zavisi od toga kako je
 * uvoz napisan (`../chat/CoreAssistantChat`, sa ili bez ekstenzije).
 */
function cellSubstitutions(): Plugin {
  return {
    name: "filmium-cell-substitutions",
    enforce: "pre",
    async resolveId(source, importer, options) {
      if (!importer) {
        return null;
      }
      const resolved = await this.resolve(source, importer, {
        ...options,
        skipSelf: true,
      });
      if (!resolved) {
        return null;
      }
      return ZAMENE.get(normalize(resolved.id)) ?? null;
    },
  };
}

export default defineConfig({
  plugins: [cellSubstitutions(), react()],
  // Ćelija servira GUI i API sa istog origina, pa su API putanje relativne.
  define: {
    "import.meta.env.VITE_CORE_API_URL": JSON.stringify(""),
  },
  build: {
    emptyOutDir: true,
    rollupOptions: {
      input: resolve(ROOT, "cell.html"),
    },
  },
});
```

- [ ] **Step 2: API sloj ćelije**

```ts
// apps/gui/src/cell/cellApi.ts
import { getJson, postJson, putJson } from "../services/httpClient";


// ==========          ĆELIJSKI API          ==========

export type CuratorAnswer = {
  answer: string;
  sources: string[];
  is_fallback: boolean;
};

export type CellStatus = {
  domain_id: string;
  name: string;
  domain_version: string;
  kernel_version: string;
  port: number;
  operating_system: string;
  node_name: string;
  database_path: string;
  rag_enabled: boolean;
  rag_namespace: string;
  pending_upgrades: number;
  ai_endpoint: string;
  ai_curator_model: string | null;
};

export type CellPersona = {
  id: string;
  name: string;
  markdown: string;
  customized: boolean;
};

/** Pitanje Kuratoru nad lokalnom Ollamom ćelije. */
export function askCurator(question: string): Promise<CuratorAnswer> {
  return postJson<CuratorAnswer, { question: string }>(
    "/api/v1/filmium/curator/ask",
    { question },
  );
}

/** Stanje ćelije, uključujući Ollama model i adresu iz cell.json. */
export function getCellStatus(): Promise<CellStatus> {
  return getJson<CellStatus>("/cell/status");
}

/** Persone FILMIUM opsega. */
export function listCellPersonas(): Promise<CellPersona[]> {
  return getJson<CellPersona[]>("/cell/personas");
}

/** Upisuje izmenjen tekst persone. */
export function saveCellPersona(id: string, markdown: string): Promise<CellPersona> {
  return putJson<CellPersona, { markdown: string }>(
    `/cell/personas/${encodeURIComponent(id)}`,
    { markdown },
  );
}
```

- [ ] **Step 3: Napiši testove koji padaju**

```tsx
// apps/gui/src/cell/CellAssistantChat.test.tsx
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

const askCurator = vi.fn();

vi.mock("./cellApi", () => ({
  askCurator: (question: string) => askCurator(question),
}));

import CellAssistantChat from "./CellAssistantChat";

beforeEach(() => {
  askCurator.mockReset();
});

describe("CellAssistantChat", () => {
  it("šalje pitanje Kuratoru i prikazuje odgovor sa izvorima", async () => {
    askCurator.mockResolvedValue({
      answer: "Pogledaj Arrival.",
      sources: ["Arrival"],
      is_fallback: false,
    });

    render(<CellAssistantChat scope="filmium" title="Kurator" />);

    await userEvent.type(screen.getByRole("textbox"), "Šta da gledam?{Enter}");

    expect(askCurator).toHaveBeenCalledWith("Šta da gledam?");
    expect(await screen.findByText(/Pogledaj Arrival\./)).toBeInTheDocument();
    expect(await screen.findByText(/Arrival/)).toBeInTheDocument();
  });

  it("jasno kaže kad Ollama nije dostupna", async () => {
    askCurator.mockRejectedValue(new Error("connection refused"));

    render(<CellAssistantChat scope="filmium" title="Kurator" />);

    await userEvent.type(screen.getByRole("textbox"), "Zdravo{Enter}");

    expect(await screen.findByText(/Kurator nije dostupan/)).toBeInTheDocument();
  });
});
```

```tsx
// apps/gui/src/cell/CellSettingsPage.test.tsx
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

const getCellStatus = vi.fn();
const listCellPersonas = vi.fn();
const saveCellPersona = vi.fn();

vi.mock("./cellApi", () => ({
  getCellStatus: () => getCellStatus(),
  listCellPersonas: () => listCellPersonas(),
  saveCellPersona: (id: string, markdown: string) => saveCellPersona(id, markdown),
}));

vi.mock("../features/filmium/components/torrents/FilmiumTorrentSettingsPanel", () => ({
  default: () => <div>torrent-podesavanja</div>,
}));

import CellSettingsPage from "./CellSettingsPage";

beforeEach(() => {
  getCellStatus.mockResolvedValue({
    name: "FILMIUM",
    port: 8781,
    ai_endpoint: "http://localhost:11434",
    ai_curator_model: "llama3",
  });
  listCellPersonas.mockResolvedValue([
    { id: "kurator", name: "Kurator", markdown: "# Kurator\n\nTekst", customized: false },
  ]);
  saveCellPersona.mockImplementation(async (id: string, markdown: string) => ({
    id, name: "Kurator", markdown, customized: true,
  }));
});

describe("CellSettingsPage", () => {
  it("nema CORE panele za modele, API ključeve i chat", async () => {
    render(<CellSettingsPage />);

    expect(screen.queryByText("API ključevi")).not.toBeInTheDocument();
    expect(screen.queryByText("AI modeli")).not.toBeInTheDocument();
    expect(screen.queryByText("Kurator (chat)")).not.toBeInTheDocument();
  });

  it("prikazuje Ollama model i adresu iz stanja ćelije", async () => {
    render(<CellSettingsPage />);

    await userEvent.click(screen.getByRole("button", { name: /Kurator/ }));

    expect(await screen.findByText("llama3")).toBeInTheDocument();
    expect(screen.getByText("http://localhost:11434")).toBeInTheDocument();
  });

  it("čuva izmenjen tekst persone", async () => {
    render(<CellSettingsPage />);

    await userEvent.click(screen.getByRole("button", { name: /Persona/ }));
    const editor = await screen.findByRole("textbox");
    await userEvent.clear(editor);
    await userEvent.type(editor, "# Kurator\n\nNovi tekst");
    await userEvent.click(screen.getByRole("button", { name: "Sačuvaj" }));

    expect(saveCellPersona).toHaveBeenCalledWith("kurator", "# Kurator\n\nNovi tekst");
  });
});
```

Kategorije u `SettingsShell` se biraju dugmetom sa nazivom kategorije. Ako `SettingsShell` renderuje kategorije drugom ulogom (npr. `tab`), uskladi `getByRole` u testu sa stvarnim markup-om `features/settings/SettingsShell.tsx` i navedi to u izveštaju.

- [ ] **Step 4: Pokreni testove i potvrdi da padaju**

Run (iz `apps/gui`): `npx vitest run src/cell`
Expected: FAIL — `Failed to resolve import "./CellAssistantChat"` i `"./CellSettingsPage"`

- [ ] **Step 5: Kurator chat ćelije**

`CellAssistantChat` prima isti skup props-a koji `FilmiumKuratorChat` prosleđuje `CoreAssistantChat`-u (`scope`, `title`, `variant`, `forcePos`, `suggestions`), da zamena bude nevidljiva za FILMIUM kod. Iscrtava CORE-ov `components/chat/CoreChat` (koji je samostalan), a slanje ide na Kuratora.

```tsx
// apps/gui/src/cell/CellAssistantChat.tsx
import CoreChat, { type ChatSuggestion } from "../components/chat/CoreChat";
import { askCurator } from "./cellApi";


// ==========          KURATOR — ĆELIJA          ==========
/*
 * Zamena za CORE-ov CoreAssistantChat u FILMIUM ćeliji. CORE verzija razgovara
 * sa CORE asistentom i vuče CODIUM, window manager i CORE podešavanja; ćelija
 * nema ništa od toga. Ovde isti chat okvir razgovara direktno sa FILMIUM
 * Kuratorom nad lokalnom Ollamom (`POST /api/v1/filmium/curator/ask`).
 */

type CellAssistantChatProps = {
  scope?: string;
  title?: string;
  variant?: string;
  forcePos?: string;
  suggestions?: ChatSuggestion[];
};

function formatAnswer(answer: string, sources: string[]): string {
  if (sources.length === 0) {
    return answer;
  }
  return `${answer}\n\nIzvori: ${sources.join(", ")}`;
}

function CellAssistantChat({
  title = "Kurator",
  variant,
  suggestions,
}: CellAssistantChatProps) {
  async function posalji(text: string): Promise<string> {
    try {
      const { answer, sources } = await askCurator(text);
      return formatAnswer(answer, sources);
    } catch {
      return (
        "Kurator nije dostupan. Proveri da li Ollama radi i da li je model "
        + "upisan u cell.json (ai.curator_model)."
      );
    }
  }

  return (
    <CoreChat
      title={title}
      variant={variant}
      suggestions={suggestions}
      showModelPicker={false}
      onSend={posalji}
    />
  );
}

export default CellAssistantChat;
```

Proveri stvarne props-e `CoreChat`-a u `components/chat/CoreChat.tsx` (tip `CoreChatProps` oko linije 54). Ako `title` nije prop, izostavi ga; ako `CoreChat` očekuje još neki obavezan prop, prosledi mu neutralnu vrednost i navedi to u izveštaju. `forcePos` i `scope` se namerno ne koriste — pozicioniranje vodi `FilmiumKuratorChat`, a ćelija ima samo jedan opseg.

- [ ] **Step 6: Podešavanja ćelije**

```tsx
// apps/gui/src/cell/CellSettingsPage.tsx
import { useEffect, useState, type ReactNode } from "react";
import { Bot, Download, Sparkles, UserRound } from "lucide-react";

import FilmiumTorrentSettingsPanel from "../features/filmium/components/torrents/FilmiumTorrentSettingsPanel";
import SettingsShell, { type SettingsCategory } from "../features/settings/SettingsShell";
import { useAmbientSettings } from "../features/theme/ambientEffect";
import { clockSettingKey, defaultClockVisible } from "../lib/domainTheme";
import { useCoreSetting } from "../lib/useCoreSetting";
import {
  getCellStatus,
  listCellPersonas,
  saveCellPersona,
  type CellPersona,
  type CellStatus,
} from "./cellApi";


// ==========          FILMIUM ĆELIJA — PODEŠAVANJA          ==========
// Zamena za CORE-ov FilmiumSettingsPage. Ćelija ne nosi API ključeve, izbor
// modela ni CORE chat podešavanja (spec §5.1, §15.1): Kurator radi nad lokalnom
// Ollamom čiji su model i adresa upisani u cell.json.

function ToggleRow({
  title,
  on,
  onToggle,
  children,
}: {
  title: string;
  on: boolean;
  onToggle: () => void;
  children: ReactNode;
}) {
  return (
    <div className="core-settings-row">
      <div className="core-settings-copy">
        <strong>{title}</strong>
        <span>{children}</span>
      </div>
      <button
        aria-checked={on}
        aria-label={title}
        className={`core-settings-toggle ${on ? "on" : ""}`}
        onClick={onToggle}
        role="switch"
        type="button"
      >
        <span aria-hidden="true" className="core-settings-toggle-knob" />
      </button>
    </div>
  );
}

function KuratorPanel() {
  const [status, setStatus] = useState<CellStatus | null>(null);
  const [greska, setGreska] = useState<string | null>(null);

  useEffect(() => {
    getCellStatus().then(setStatus).catch(() => setGreska("Stanje ćelije nije dostupno."));
  }, []);

  return (
    <section className="cset-panel">
      <header className="cset-panel-head">
        <div>
          <h2 className="cset-panel-title">Kurator</h2>
          <p className="cset-panel-sub">
            Kurator radi nad lokalnom Ollamom. Model i adresa se menjaju u
            cell.json (ai.curator_model, ai.endpoint), pa ćeliju treba ponovo
            pokrenuti.
          </p>
        </div>
      </header>
      {greska && <p>{greska}</p>}
      {status && (
        <dl>
          <dt>Model</dt>
          <dd>{status.ai_curator_model ?? "nije upisan"}</dd>
          <dt>Ollama adresa</dt>
          <dd>{status.ai_endpoint}</dd>
        </dl>
      )}
    </section>
  );
}

function PersonaEditor() {
  const [persona, setPersona] = useState<CellPersona | null>(null);
  const [tekst, setTekst] = useState("");
  const [poruka, setPoruka] = useState<string | null>(null);

  useEffect(() => {
    listCellPersonas()
      .then((lista) => {
        const prva = lista[0] ?? null;
        setPersona(prva);
        setTekst(prva?.markdown ?? "");
      })
      .catch(() => setPoruka("Persone nisu dostupne."));
  }, []);

  async function sacuvaj(): Promise<void> {
    if (!persona) {
      return;
    }
    try {
      const nova = await saveCellPersona(persona.id, tekst);
      setPersona(nova);
      setPoruka("Sačuvano. Važi od sledeće poruke.");
    } catch {
      setPoruka("Čuvanje nije uspelo.");
    }
  }

  return (
    <section className="cset-panel">
      <header className="cset-panel-head">
        <div>
          <h2 className="cset-panel-title">Persona</h2>
          <p className="cset-panel-sub">
            Sistemski prompt Kuratora. Prvi naslov (# ...) je naziv profila.
          </p>
        </div>
      </header>
      <textarea
        aria-label="Tekst persone"
        onChange={(event) => setTekst(event.target.value)}
        rows={14}
        value={tekst}
      />
      <button onClick={() => void sacuvaj()} type="button">
        Sačuvaj
      </button>
      {poruka && <p>{poruka}</p>}
    </section>
  );
}

function CellSettingsPage() {
  const [showPageTitle, setShowPageTitle] = useCoreSetting("core.filmium.showPageTitle", false);
  const [clockVisible, setClockVisible] = useCoreSetting(
    clockSettingKey("filmium"),
    defaultClockVisible("filmium"),
  );
  const { settings: ambient, setDomain: setAmbientDomain } = useAmbientSettings();

  const kategorije: SettingsCategory[] = [
    { id: "kurator", label: "Kurator", icon: Bot, render: () => <KuratorPanel /> },
    { id: "persona", label: "Persona", icon: UserRound, render: () => <PersonaEditor /> },
    {
      id: "prikaz",
      label: "Prikaz",
      icon: Sparkles,
      render: () => (
        <section className="cset-panel">
          <header className="cset-panel-head">
            <div>
              <h2 className="cset-panel-title">Prikaz</h2>
              <p className="cset-panel-sub">Naslovi, sat i pozadinski efekat.</p>
            </div>
          </header>
          <ToggleRow
            title="Naslov programa"
            on={showPageTitle}
            onToggle={() => setShowPageTitle(!showPageTitle)}
          >
            Prikaži naslov trenutnog prikaza iznad kataloga.
          </ToggleRow>
          <ToggleRow
            title="Sat"
            on={clockVisible}
            onToggle={() => setClockVisible(!clockVisible)}
          >
            {clockVisible ? "Sat je prikazan na vrhu." : "Sat je sakriven."}
          </ToggleRow>
          <ToggleRow
            title="Pozadinski efekat"
            on={ambient.all || ambient.domains.filmium}
            onToggle={() => setAmbientDomain("filmium", !ambient.domains.filmium)}
          >
            Povezane tačke i glow spotovi u boji FILMIUM-a.
          </ToggleRow>
        </section>
      ),
    },
    { id: "torrenti", label: "Torrenti", icon: Download, render: () => <FilmiumTorrentSettingsPanel /> },
  ];

  return (
    <SettingsShell
      eyebrow="FILMIUM Ćelija"
      title="FILMIUM — Podešavanja"
      note="Podešavanja samostalne FILMIUM ćelije. API ključevi i izbor modela ostaju u CORE-u."
      categories={kategorije}
    />
  );
}

export default CellSettingsPage;
```

Ako `SettingsShell` prima drugačiji skup props-a nego što ovaj kod pretpostavlja, uskladi se sa `features/settings/SettingsShell.tsx` — potpis u tom fajlu je merodavan.

- [ ] **Step 7: Ulaz aplikacije ćelije**

```tsx
// apps/gui/src/cell/CellApp.tsx
import { Navigate, Route, Routes } from "react-router";

import { filmiumRoutes } from "../features/filmium/filmiumRoutes";


// ==========          FILMIUM ĆELIJA — APLIKACIJA          ==========
// Samo FILMIUM rute, bez CORE sidebar-a i ostalih domena.

function CellApp() {
  return (
    <Routes>
      {filmiumRoutes()}
      <Route path="*" element={<Navigate replace to="/filmium" />} />
    </Routes>
  );
}

export default CellApp;
```

```tsx
// apps/gui/src/cell/cellMain.tsx
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { HashRouter } from "react-router";

import CellApp from "./CellApp";
import "../index.css";


// ==========          FILMIUM ĆELIJA — ULAZ          ==========

const rootElement = document.getElementById("root");

if (!rootElement) {
  throw new Error("FILMIUM ćelija: root element nije pronađen.");
}

createRoot(rootElement).render(
  <StrictMode>
    <HashRouter>
      <CellApp />
    </HashRouter>
  </StrictMode>,
);
```

`main.tsx` uvozi i `./lib/monacoSetup`; ćelija ga namerno ne uvozi, jer FILMIUM ne koristi Monaco.

- [ ] **Step 8: Pokreni testove i build ćelije**

Run (iz `apps/gui`): `npx vitest run src/cell` — Expected: PASS, 5 testova.
Run: `npx tsc -b tsconfig.app.json tsconfig.node.json` — Expected: bez grešaka.
Run: `npx vite build --config vite.cell.config.ts --outDir ../../.superpowers/cell-gui-proba` — Expected: build uspeva i `index.html` postoji u izlazu.
Run: `grep -l "CoreAssistantChat\|ApiKeysPanel\|ModelsPanel\|windowManager" ../../.superpowers/cell-gui-proba/assets/*.js` — Expected: bez pogodaka (zamene su stvarno primenjene). Ako `grep` nađe pogodak zbog imena u stringu, a ne modula, navedi tačan kontekst u izveštaju.
Run: `npx vitest run 2>&1 | tail -6` — Expected: padovi isti kao ranije, prolazi veći za 5.

Posle provere obriši `.superpowers/cell-gui-proba`.

- [ ] **Step 9: Commit**

```bash
git add apps/gui/cell-substitutions.json apps/gui/cell.html apps/gui/vite.cell.config.ts apps/gui/src/cell
git commit -m "feat(gui): GUI ulaz FILMIUM celije sa zamenama CORE-only modula"
```

---

### Task 4: Zatvorenje GUI uvoza i provera u Python sklapaču

**Files:**
- Create: `core/cell/gui.py`
- Test: `tests/test_cell_gui.py`

**Interfaces:**
- Consumes: `apps/gui/cell-substitutions.json`, `apps/gui/src/cell/cellMain.tsx` (Task 3).
- Produces:
  - `CELL_GUI_ENTRY: str = "src/cell/cellMain.tsx"`
  - `FORBIDDEN_GUI_PREFIXES: tuple[str, ...]`
  - `@dataclass(frozen=True) class GuiClosure: files: tuple[str, ...]; npm_packages: tuple[str, ...]` — putanje relativne na `apps/gui`, sa `/`
  - `load_substitutions(gui_root: Path) -> dict[str, str]`
  - `collect_gui_closure(gui_root: Path, entries: Iterable[str] = (CELL_GUI_ENTRY,)) -> GuiClosure`
  - `find_forbidden_gui_modules(closure: GuiClosure) -> tuple[str, ...]`

- [ ] **Step 1: Napiši testove koji padaju**

```python
# tests/test_cell_gui.py
import json
from pathlib import Path

import pytest

from core.cell.gui import (
    CELL_GUI_ENTRY,
    GuiClosure,
    collect_gui_closure,
    find_forbidden_gui_modules,
    load_substitutions,
)
from core.foundation.paths import core_paths

GUI_ROOT = core_paths.root / "apps" / "gui"


def write(root: Path, relative: str, text: str) -> None:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_real_closure_has_no_forbidden_modules() -> None:
    closure = collect_gui_closure(GUI_ROOT)

    assert find_forbidden_gui_modules(closure) == ()


def test_real_closure_carries_filmium_services_and_types() -> None:
    closure = collect_gui_closure(GUI_ROOT)

    assert CELL_GUI_ENTRY in closure.files
    assert "src/services/filmiumApi.ts" in closure.files
    assert "src/types/filmium.ts" in closure.files
    assert "src/cell/CellAssistantChat.tsx" in closure.files
    assert "src/features/chat/CoreAssistantChat.tsx" not in closure.files
    assert "src/pages/FilmiumSettingsPage.tsx" not in closure.files


def test_real_closure_npm_packages() -> None:
    closure = collect_gui_closure(GUI_ROOT)

    assert set(closure.npm_packages) >= {"react", "react-dom", "react-router", "lucide-react"}
    assert "monaco-editor" not in closure.npm_packages
    assert "@xterm/xterm" not in closure.npm_packages


def test_substitution_map_is_read_from_json(tmp_path: Path) -> None:
    write(tmp_path, "cell-substitutions.json", json.dumps({"src/a.ts": "src/b.ts"}))

    assert load_substitutions(tmp_path) == {"src/a.ts": "src/b.ts"}


def test_substitution_replaces_module_and_follows_replacement(tmp_path: Path) -> None:
    write(tmp_path, "cell-substitutions.json", json.dumps({"src/core.ts": "src/cell.ts"}))
    write(tmp_path, "src/entry.ts", 'import x from "./core";\n')
    write(tmp_path, "src/core.ts", 'import y from "./corevuce";\n')
    write(tmp_path, "src/corevuce.ts", "export default 1;\n")
    write(tmp_path, "src/cell.ts", 'import z from "./celijsko";\n')
    write(tmp_path, "src/celijsko.ts", "export default 2;\n")

    closure = collect_gui_closure(tmp_path, entries=("src/entry.ts",))

    assert "src/cell.ts" in closure.files
    assert "src/celijsko.ts" in closure.files
    assert "src/core.ts" not in closure.files
    assert "src/corevuce.ts" not in closure.files


def test_resolves_extensions_index_css_dynamic_and_export_from(tmp_path: Path) -> None:
    write(tmp_path, "cell-substitutions.json", "{}")
    write(
        tmp_path,
        "src/entry.tsx",
        'import "./style.css";\n'
        'export { a } from "./lib";\n'
        'const lazy = () => import("./lazy");\n'
        'import type { T } from "./tipovi";\n'
        'import pkg from "@scope/pkg/sub";\n'
        'import plain from "plain-pkg";\n',
    )
    write(tmp_path, "src/style.css", '@import "./base.css";\n')
    write(tmp_path, "src/base.css", "body{}\n")
    write(tmp_path, "src/lib/index.ts", "export const a = 1;\n")
    write(tmp_path, "src/lazy.tsx", "export default 1;\n")
    write(tmp_path, "src/tipovi.ts", "export type T = 1;\n")

    closure = collect_gui_closure(tmp_path, entries=("src/entry.tsx",))

    assert set(closure.files) == {
        "src/entry.tsx", "src/style.css", "src/base.css",
        "src/lib/index.ts", "src/lazy.tsx", "src/tipovi.ts",
    }
    assert closure.npm_packages == ("@scope/pkg", "plain-pkg")


def test_unresolvable_relative_import_raises(tmp_path: Path) -> None:
    write(tmp_path, "cell-substitutions.json", "{}")
    write(tmp_path, "src/entry.ts", 'import x from "./nema";\n')

    with pytest.raises(FileNotFoundError) as error:
        collect_gui_closure(tmp_path, entries=("src/entry.ts",))

    assert "./nema" in str(error.value)


def test_forbidden_modules_are_reported() -> None:
    closure = GuiClosure(
        files=("src/features/codium/x.ts", "src/services/coreApi.ts", "src/types/filmium.ts"),
        npm_packages=(),
    )

    assert find_forbidden_gui_modules(closure) == (
        "src/features/codium/x.ts",
        "src/services/coreApi.ts",
    )
```

- [ ] **Step 2: Pokreni testove i potvrdi da padaju**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_cell_gui.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'core.cell.gui'`

- [ ] **Step 3: Napiši implementaciju**

```python
# core/cell/gui.py
"""Zatvorenje GUI uvoza FILMIUM ćelije.

Polazi od ćelijskog ulaza i prati relativne uvoze kroz TypeScript, TSX i CSS,
primenjujući istu mapu zamena koju koristi Vite (`apps/gui/cell-substitutions.json`).
Rezultat je tačan skup izvornih fajlova koje ćelija nosi i skup npm paketa koje
taj izvor traži. Nerazrešiv relativni uvoz je greška, ne tiho preskakanje —
upravo tako se ranije izgubio `CoreAssistantChat.tsx`.
"""

from __future__ import annotations

import json
import re
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

CELL_GUI_ENTRY = "src/cell/cellMain.tsx"
SUBSTITUTIONS_FILENAME = "cell-substitutions.json"

# Moduli koje ćelija ne sme da nosi: CORE asistent, window sistem, CODIUM,
# glas i CORE podešavanja modela/ključeva (spec §15.2).
FORBIDDEN_GUI_PREFIXES: tuple[str, ...] = (
    "src/features/codium/",
    "src/features/window/",
    "src/features/voice/",
    "src/features/chat/CoreAssistantChat",
    "src/features/settings/ApiKeysPanel",
    "src/features/settings/ApiKeyDialog",
    "src/features/settings/ChatPanel",
    "src/features/settings/ModelsPanel",
    "src/features/settings/openrouterCatalog",
    "src/services/coreApi",
    "src/services/codiumApi",
    "src/pages/FilmiumSettingsPage",
)

_SCRIPT_IMPORT = re.compile(
    r"""(?:^|[;\s])(?:import|export)\s+(?:type\s+)?(?:[^'";]*?\s+from\s+)?['"]([^'"]+)['"]"""
    r"""|import\(\s*['"]([^'"]+)['"]\s*\)""",
    re.MULTILINE,
)
_CSS_IMPORT = re.compile(r"""@import\s+(?:url\()?['"]([^'"]+)['"]""")
_CANDIDATE_SUFFIXES = ("", ".ts", ".tsx", ".js", ".jsx", ".css", "/index.ts", "/index.tsx")


@dataclass(frozen=True)
class GuiClosure:
    """Izvorni fajlovi (relativni na `apps/gui`) i npm paketi ćelijskog GUI-ja."""

    files: tuple[str, ...]
    npm_packages: tuple[str, ...]


def load_substitutions(gui_root: Path) -> dict[str, str]:
    """Učitava mapu zamena CORE-only modula."""

    return json.loads((gui_root / SUBSTITUTIONS_FILENAME).read_text(encoding="utf-8"))


def _relative(gui_root: Path, path: Path) -> str:
    return path.resolve().relative_to(gui_root.resolve()).as_posix()


def _resolve(importer: Path, specifier: str) -> Path | None:
    base = importer.parent / specifier
    for suffix in _CANDIDATE_SUFFIXES:
        candidate = Path(f"{base}{suffix}")
        if candidate.is_file():
            return candidate.resolve()
    return None


def _package_name(specifier: str) -> str:
    parts = specifier.split("/")
    return "/".join(parts[:2]) if specifier.startswith("@") else parts[0]


def collect_gui_closure(
    gui_root: Path,
    entries: Iterable[str] = (CELL_GUI_ENTRY,),
) -> GuiClosure:
    """
    Računa zatvorenje uvoza od zadatih ulaza.

    Args:
        gui_root: Koren GUI projekta (`apps/gui`).
        entries: Ulazni fajlovi, relativni na `gui_root`.

    Returns:
        Sortirani fajlovi i npm paketi.

    Raises:
        FileNotFoundError: Ako se relativni uvoz ne može razrešiti.
    """
    substitutions = {
        (gui_root / source).resolve(): (gui_root / target).resolve()
        for source, target in load_substitutions(gui_root).items()
    }

    seen: set[Path] = set()
    packages: set[str] = set()
    stack = [(gui_root / entry).resolve() for entry in entries]

    while stack:
        current = stack.pop()
        current = substitutions.get(current, current)
        if current in seen:
            continue
        seen.add(current)

        text = current.read_text(encoding="utf-8", errors="replace")
        pattern = _CSS_IMPORT if current.suffix == ".css" else _SCRIPT_IMPORT

        for match in pattern.finditer(text):
            specifier = next(group for group in match.groups() if group)

            if specifier.startswith("."):
                resolved = _resolve(current, specifier)
                if resolved is None:
                    raise FileNotFoundError(
                        f"{_relative(gui_root, current)}: ne mogu da razrešim uvoz {specifier!r}"
                    )
                stack.append(substitutions.get(resolved, resolved))
            elif current.suffix != ".css":
                packages.add(_package_name(specifier))

    return GuiClosure(
        files=tuple(sorted(_relative(gui_root, path) for path in seen)),
        npm_packages=tuple(sorted(packages)),
    )


def find_forbidden_gui_modules(closure: GuiClosure) -> tuple[str, ...]:
    """Vraća fajlove zatvorenja koje ćelija ne sme da nosi."""

    return tuple(
        path
        for path in closure.files
        if any(path.startswith(prefix) for prefix in FORBIDDEN_GUI_PREFIXES)
    )
```

`_SCRIPT_IMPORT` ne sme da hvata `from` unutar komentara ili stringova koji nisu uvoz; ako stvarno zatvorenje nad `apps/gui` baci `FileNotFoundError` za nešto što nije uvoz, suzi obrazac i dodaj test za taj slučaj.

- [ ] **Step 4: Pokreni testove i potvrdi da prolaze**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_cell_gui.py -v`
Expected: PASS, 8 testova

Ako `test_real_closure_has_no_forbidden_modules` padne, nalaz je stvaran: neki FILMIUM ili ćelijski fajl i dalje vodi u CORE-only granu. Ispiši putanju uvoza koja je dovela do zabranjenog modula i reši je dodavanjem zamene u `cell-substitutions.json` (uz odgovarajući ćelijski modul) — nikad brisanjem prefiksa iz `FORBIDDEN_GUI_PREFIXES`.

- [ ] **Step 5: Commit**

```bash
git add core/cell/gui.py tests/test_cell_gui.py
git commit -m "feat(cell): zatvorenje GUI uvoza celije sa proverom CORE-only modula"
```

---

### Task 5: API ćelije — routeri, persone, statički GUI

**Files:**
- Modify: `apps/api/routers/cell.py` (dodati `GET /cell/personas`, `PUT /cell/personas/{persona_id}`)
- Modify: `apps/api/schemas/cell.py` (`CellStatusResponse` dobija `ai_endpoint`, `ai_curator_model`; nove `CellPersonaResponse`, `CellPersonaUpdateRequest`)
- Modify: `core/cell/status.py` (`build_cell_status` vraća `ai_endpoint`, `ai_curator_model`)
- Modify: `scripts/cell/templates/cell_app.py.tpl`
- Modify: `core/cell/build.py` (`apps/api/dependencies.py` ponovo obavezan; `CELL_API_ROUTERS` lista)
- Test: `tests/test_cell_status.py` (dopuna)
- Test: `tests/test_cell_app.py` (nov)

**Interfaces:**
- Consumes: `CellManifest` (`ai_endpoint`, `ai_curator_model`), `PersonaStore` iz `core/ai/persona_store.py` (`list(scope) -> list[PersonaDoc]`, `save(scope, persona_id, markdown) -> PersonaDoc`, `PersonaDoc(id, scope, name, markdown, customized)`), `build_cell` (prethodni plan).
- Produces:
  - `GET /cell/personas -> list[CellPersonaResponse]` za opseg `filmium`
  - `PUT /cell/personas/{persona_id}` telo `{"markdown": str}` → `CellPersonaResponse`; prazan tekst → HTTP 422
  - `CELL_API_ROUTERS: tuple[str, ...]` u `core/cell/build.py` — imena modula `apps.api.routers.filmium*` koje ćelija montira

- [ ] **Step 1: Dopuni testove statusa i napiši testove persona**

U `tests/test_cell_status.py` dopuni `test_status_payload_has_expected_keys` proverama:

```python
    assert status["ai_endpoint"] == "http://localhost:11434"
    assert status["ai_curator_model"] is None
```

i dodaj:

```python
def test_personas_list_and_save(tmp_path: Path, monkeypatch) -> None:
    from apps.api.routers import cell as cell_router
    from core.ai.persona_store import PersonaStore

    store = PersonaStore(root=tmp_path / "personas")
    monkeypatch.setattr(cell_router, "_persona_store", lambda: store)
    cell_router.bind_manifest(make_manifest(tmp_path / "FILMIUM"))

    app = FastAPI()
    app.include_router(cell_router.router)
    client = TestClient(app)

    listed = client.get("/cell/personas")
    assert listed.status_code == 200
    personas = listed.json()
    assert personas and {"id", "name", "markdown", "customized"} <= set(personas[0])

    persona_id = personas[0]["id"]
    saved = client.put(f"/cell/personas/{persona_id}", json={"markdown": "# Kurator\n\nNovo"})
    assert saved.status_code == 200
    assert saved.json()["customized"] is True

    empty = client.put(f"/cell/personas/{persona_id}", json={"markdown": "   "})
    assert empty.status_code == 422
```

Ako `PersonaStore.__init__` ne prima `root`, uskladi test sa stvarnim potpisom iz `core/ai/persona_store.py:150`.

- [ ] **Step 2: Napiši test pokretanja sklopljene ćelije**

Sklopljena ćelija ima sopstveni paket `core`, koji se sudara sa već uvezenim `core` iz repoa u pytest procesu. Zato se ćelija proverava u **zasebnom procesu**.

```python
# tests/test_cell_app.py
import json
import subprocess
import sys
from pathlib import Path

from core.cell.build import build_cell
from core.cell.extraction import extract_domain_data
from core.cell.manifest import load_cell_manifest
from core.database.runtime import initialize_core_database
from core.foundation.paths import core_paths

PROBE = r"""
import json, sys
from pathlib import Path
root = Path(sys.argv[1])
sys.path.insert(0, str(root))
from fastapi.testclient import TestClient
import cell_app
with TestClient(cell_app.app) as client:
    out = {
        "status": client.get("/cell/status").status_code,
        "media": client.get("/api/v1/filmium/media").status_code,
        "genres": client.get("/api/v1/filmium/genres").status_code,
        "personas": client.get("/cell/personas").status_code,
        "index": client.get("/").status_code,
        "index_html": "<div id=\"root\">" in client.get("/").text,
    }
print(json.dumps(out))
"""


def fake_gui_builder(repo_root: Path, out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "index.html").write_text('<div id="root"></div>', encoding="utf-8")


def test_assembled_cell_serves_api_and_gui(tmp_path: Path) -> None:
    target = tmp_path / "FILMIUM"
    build_cell(
        "filmium",
        target,
        repo_root=core_paths.root,
        port=8781,
        detached_from="abc1234",
        gui_builder=fake_gui_builder,
    )

    source = tmp_path / "core.db"
    initialize_core_database(source)
    extract_domain_data(source, load_cell_manifest(target))

    result = subprocess.run(
        [sys.executable, "-c", PROBE, str(target)],
        cwd=target,
        capture_output=True,
        text=True,
        timeout=180,
    )

    assert result.returncode == 0, result.stderr[-3000:]
    out = json.loads(result.stdout.strip().splitlines()[-1])
    assert out == {
        "status": 200,
        "media": 200,
        "genres": 200,
        "personas": 200,
        "index": 200,
        "index_html": True,
    }
```

Ovaj test zavisi od `gui_builder` parametra iz Task 6. Dok Task 6 ne postoji, pokreni ga u Step 3 samo da potvrdiš da pada zbog tog parametra, pa ga ostavi — prolaz se traži na kraju Task 6.

- [ ] **Step 3: Pokreni testove i potvrdi da padaju**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_cell_status.py tests/test_cell_app.py -v`
Expected: FAIL — nedostaju ključevi `ai_endpoint`, ruta `/cell/personas`, i `build_cell() got an unexpected keyword argument 'gui_builder'`

- [ ] **Step 4: Status i persone**

U `core/cell/status.py` dodaj u vraćeni rečnik:

```python
        "ai_endpoint": manifest.ai_endpoint,
        "ai_curator_model": manifest.ai_curator_model,
```

U `apps/api/schemas/cell.py` dodaj u `CellStatusResponse` polja `ai_endpoint: str` i `ai_curator_model: str | None`, i nove sheme:

```python
class CellPersonaResponse(BaseModel):
    """Persona FILMIUM opsega, onako kako je vidi ekran podešavanja ćelije."""

    id: str
    name: str
    markdown: str
    customized: bool


class CellPersonaUpdateRequest(BaseModel):
    """Nov tekst persone."""

    markdown: str
```

U `apps/api/routers/cell.py` dodaj:

```python
from apps.api.schemas.cell import CellPersonaResponse, CellPersonaUpdateRequest
from core.ai.persona_store import PersonaStore

_PERSONA_SCOPE = "filmium"


def _persona_store() -> PersonaStore:
    """Persona store ćelije; zasebna funkcija da bi test mogao da je zameni."""

    return PersonaStore()


@router.get("/personas", response_model=list[CellPersonaResponse])
def list_cell_personas() -> list[CellPersonaResponse]:
    """Vraća persone FILMIUM opsega."""

    return [
        CellPersonaResponse(id=doc.id, name=doc.name, markdown=doc.markdown, customized=doc.customized)
        for doc in _persona_store().list(_PERSONA_SCOPE)
    ]


@router.put("/personas/{persona_id}", response_model=CellPersonaResponse)
def save_cell_persona(persona_id: str, body: CellPersonaUpdateRequest) -> CellPersonaResponse:
    """Upisuje izmenjen tekst persone; prazan tekst se odbija."""

    try:
        doc = _persona_store().save(_PERSONA_SCOPE, persona_id, body.markdown)
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(error)) from error
    except KeyError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Nepoznata persona: {persona_id}") from error

    return CellPersonaResponse(id=doc.id, name=doc.name, markdown=doc.markdown, customized=doc.customized)
```

Ako `PersonaStore.save` za nepoznatu personu baca drugi tip izuzetka, uhvati taj tip i navedi ga u izveštaju.

- [ ] **Step 5: Šablon `cell_app.py`**

```python
# scripts/cell/templates/cell_app.py.tpl
"""Ulazna tačka ćelije {{DOMAIN_ID}}.

Jedan proces služi ceo API domena i GUI build na istom originu. Putanje se
preusmeravaju i baza inicijalizuje PRE uvoza routera: `apps/api/dependencies.py`
pravi repozitorijume i servise već pri uvozu, pa bi inače gađali CORE putanje.
"""

import importlib
import sys
from pathlib import Path

CELL_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(CELL_ROOT))

from core.cell.database import initialize_cell_database  # noqa: E402
from core.cell.manifest import load_cell_manifest  # noqa: E402
from core.cell.paths import apply_cell_paths  # noqa: E402

MANIFEST = load_cell_manifest(CELL_ROOT)
apply_cell_paths(MANIFEST)
initialize_cell_database(MANIFEST)

from fastapi import FastAPI  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
from starlette.staticfiles import StaticFiles  # noqa: E402

from apps.api.routers import cell as cell_router  # noqa: E402

API_ROUTERS = ({{API_ROUTERS}})

app = FastAPI(title=MANIFEST.name, version=MANIFEST.domain_version)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

cell_router.bind_manifest(MANIFEST)
app.include_router(cell_router.router)

for module_name in API_ROUTERS:
    app.include_router(importlib.import_module(module_name).router)

GUI_DIST = CELL_ROOT / "gui" / "dist"
if (GUI_DIST / "index.html").is_file():
    # Poslednje, da GUI nikad ne zakloni API rutu.
    app.mount("/", StaticFiles(directory=GUI_DIST, html=True), name="gui")
```

U `core/cell/build.py`:
- dodaj `CELL_API_ROUTERS` sa imenima modula svih `apps/api/routers/{domain_id}*.py` fajlova koje `build_cell` već kopira (izračunaj ga iz iste glob liste, ne ručnom listom), i pri renderovanju šablona zameni `{{API_ROUTERS}}` sa `", ".join(repr(name) for name in ...) + ","`;
- vrati `apps/api/dependencies.py` u obavezne module: nedostajući fajl mora da podigne `FileNotFoundError`, isto kao `KERNEL_PYTHON_MODULES` (parkiran nalaz iz prethodnog plana). Zadrži ga u `DOMAIN_RUNTIME_MODULES` sa prepisivanjem, ali ukloni tiho preskakanje za njega.

Proveri da li neki od 16 routera u svom modulu pri uvozu gađa nešto što ćelija nema (npr. `apps.api.core_ai_runtime`); `find_forbidden_module_imports` to već hvata pri sklapanju.

- [ ] **Step 6: Pokreni testove statusa i persona**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_cell_status.py tests/test_cell_build.py -v`
Expected: PASS. `tests/test_cell_app.py` i dalje pada samo na `gui_builder` — to se rešava u Task 6.

- [ ] **Step 7: Commit**

```bash
git add apps/api/routers/cell.py apps/api/schemas/cell.py core/cell/status.py core/cell/build.py scripts/cell/templates/cell_app.py.tpl tests/test_cell_status.py tests/test_cell_app.py
git commit -m "feat(cell): celija montira FILMIUM routere, persone i GUI build"
```

---

### Task 6: GUI u sklapanju, režim ažuriranja i pokretanje

**Files:**
- Modify: `core/cell/build.py`
- Modify: `scripts/cell/build_cell.py`
- Modify: `scripts/cell/templates/start.bat.tpl`
- Test: `tests/test_cell_build.py` (dopuna)
- Test: `tests/test_cell_app.py` (sada mora da prođe)

**Interfaces:**
- Consumes: `collect_gui_closure`, `find_forbidden_gui_modules` (Task 4); `vite.cell.config.ts`, `cell.html`, `cell-substitutions.json` (Task 3).
- Produces:
  - `GuiBuilder = Callable[[Path, Path], None]` — `(repo_root, out_dir)`
  - `build_gui_dist(repo_root: Path, out_dir: Path) -> None` — pravi Vite build ćelije
  - `build_cell(domain_id, target, *, repo_root, port, detached_from, gui_builder: GuiBuilder = build_gui_dist, update: bool = False) -> CellManifest`
  - `PRESERVED_ON_UPDATE: tuple[str, ...] = ("data", "config", "cell.json")`
  - CLI: `build_cell.py <domain_id> <ciljni-folder> <port> [--update]`

- [ ] **Step 1: Napiši testove koji padaju**

Dodaj u `tests/test_cell_build.py` (koristi `fake_gui_builder` kao u `tests/test_cell_app.py`; izdvoj ga u `tests/cell_helpers.py` ako ga oba fajla koriste):

```python
def test_gui_source_and_dist_are_assembled(tmp_path: Path) -> None:
    target = tmp_path / "FILMIUM"
    build_cell("filmium", target, repo_root=core_paths.root, port=8781,
               detached_from="abc1234", gui_builder=fake_gui_builder)

    assert (target / "gui" / "src" / "cell" / "cellMain.tsx").is_file()
    assert (target / "gui" / "src" / "services" / "filmiumApi.ts").is_file()
    assert (target / "gui" / "src" / "types" / "filmium.ts").is_file()
    assert (target / "gui" / "cell.html").is_file()
    assert (target / "gui" / "vite.cell.config.ts").is_file()
    assert (target / "gui" / "cell-substitutions.json").is_file()
    assert (target / "gui" / "dist" / "index.html").is_file()
    assert not (target / "gui" / "src" / "features" / "codium").exists()


def test_gui_package_json_is_trimmed(tmp_path: Path) -> None:
    target = tmp_path / "FILMIUM"
    build_cell("filmium", target, repo_root=core_paths.root, port=8781,
               detached_from="abc1234", gui_builder=fake_gui_builder)

    package = json.loads((target / "gui" / "package.json").read_text(encoding="utf-8"))

    assert "react" in package["dependencies"]
    assert "monaco-editor" not in package["dependencies"]
    assert "@xterm/xterm" not in package["dependencies"]
    assert "build" in package["scripts"]


def test_missing_dist_fails_build(tmp_path: Path) -> None:
    def broken_builder(repo_root: Path, out_dir: Path) -> None:
        out_dir.mkdir(parents=True, exist_ok=True)

    with pytest.raises(FileNotFoundError):
        build_cell("filmium", tmp_path / "FILMIUM", repo_root=core_paths.root,
                   port=8781, detached_from="abc1234", gui_builder=broken_builder)


def test_update_replaces_code_and_preserves_data_and_config(tmp_path: Path) -> None:
    target = tmp_path / "FILMIUM"
    build_cell("filmium", target, repo_root=core_paths.root, port=8781,
               detached_from="stari", gui_builder=fake_gui_builder)

    (target / "data").mkdir(exist_ok=True)
    (target / "data" / "filmium.db").write_bytes(b"baza")
    (target / "config" / "tmdb.json").write_text('{"api_key": "[Here put api_key]"}', encoding="utf-8")
    (target / "core" / "zastareo.py").write_text("x = 1\n", encoding="utf-8")

    manifest = build_cell("filmium", target, repo_root=core_paths.root, port=8781,
                          detached_from="novi", gui_builder=fake_gui_builder, update=True)

    assert (target / "data" / "filmium.db").read_bytes() == b"baza"
    assert json.loads((target / "config" / "tmdb.json").read_text(encoding="utf-8")) == {"api_key": "[Here put api_key]"}
    assert not (target / "core" / "zastareo.py").exists()
    assert manifest.detached_from == "novi"


def test_update_keeps_port_and_ai_settings_from_existing_manifest(tmp_path: Path) -> None:
    target = tmp_path / "FILMIUM"
    build_cell("filmium", target, repo_root=core_paths.root, port=8781,
               detached_from="stari", gui_builder=fake_gui_builder)

    manifest_path = target / "cell.json"
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    data["ai"]["curator_model"] = "llama3"
    manifest_path.write_text(json.dumps(data), encoding="utf-8")

    manifest = build_cell("filmium", target, repo_root=core_paths.root, port=9999,
                          detached_from="novi", gui_builder=fake_gui_builder, update=True)

    assert manifest.port == 8781
    assert manifest.ai_curator_model == "llama3"


def test_update_refuses_folder_without_manifest(tmp_path: Path) -> None:
    target = tmp_path / "NIJE_CELIJA"
    target.mkdir()
    (target / "nesto.txt").write_text("x", encoding="utf-8")

    with pytest.raises(FileNotFoundError):
        build_cell("filmium", target, repo_root=core_paths.root, port=8781,
                   detached_from="novi", gui_builder=fake_gui_builder, update=True)

    assert (target / "nesto.txt").exists()


def test_start_bat_starts_server_and_opens_browser(tmp_path: Path) -> None:
    target = tmp_path / "FILMIUM"
    build_cell("filmium", target, repo_root=core_paths.root, port=8781,
               detached_from="abc1234", gui_builder=fake_gui_builder)

    text = (target / "start.bat").read_text(encoding="utf-8")

    assert "uvicorn cell_app:app" in text
    assert "--port 8781" in text
    assert "http://127.0.0.1:8781/#/filmium" in text
```

Postojeći testovi u `tests/test_cell_build.py` koji zovu `build_cell` bez `gui_builder` bi pokretali pravi Vite build u svakom testu. Prosledi im `gui_builder=fake_gui_builder` (preko zajedničke pomoćne funkcije `build`), da pravi build ostane isključivo u Task 7.

- [ ] **Step 2: Pokreni testove i potvrdi da padaju**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_cell_build.py tests/test_cell_app.py -v`
Expected: FAIL — `unexpected keyword argument 'gui_builder'` / `'update'`

- [ ] **Step 3: Implementacija u `core/cell/build.py`**

Dodaj, uz postojeći kod:

```python
import subprocess
from collections.abc import Callable

from core.cell.gui import collect_gui_closure, find_forbidden_gui_modules

GuiBuilder = Callable[[Path, Path], None]

PRESERVED_ON_UPDATE: tuple[str, ...] = ("data", "config", "cell.json")

# Fajlovi GUI projekta koje ćelija nosi pored izvornog zatvorenja.
CELL_GUI_PROJECT_FILES: tuple[str, ...] = (
    "cell.html",
    "vite.cell.config.ts",
    "cell-substitutions.json",
    "tsconfig.json",
    "tsconfig.app.json",
    "tsconfig.node.json",
)

# Alati za ponovni build u ćeliji; verzije se čitaju iz repoa.
CELL_GUI_DEV_DEPENDENCIES: tuple[str, ...] = (
    "vite",
    "@vitejs/plugin-react",
    "typescript",
    "@types/react",
    "@types/react-dom",
    "@types/node",
)


def build_gui_dist(repo_root: Path, out_dir: Path) -> None:
    """
    Pravi Vite build ćelijskog GUI-ja iz repoa, CORE-ovim `node_modules`.

    Raises:
        RuntimeError: Ako build ne uspe; poruka nosi kraj Vite izlaza.
    """
    gui_root = repo_root / "apps" / "gui"
    result = subprocess.run(
        ["npx", "vite", "build", "--config", "vite.cell.config.ts", "--outDir", str(out_dir)],
        cwd=gui_root,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        shell=sys.platform == "win32",
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(f"Vite build ćelije nije uspeo:\n{(result.stdout + result.stderr)[-4000:]}")


def _write_gui_package_json(repo_root: Path, target: Path, npm_packages: Iterable[str]) -> None:
    """Upisuje `package.json` ćelije sa samo onim paketima koje GUI stvarno traži."""

    source = json.loads((repo_root / "apps" / "gui" / "package.json").read_text(encoding="utf-8"))
    dependencies = source.get("dependencies", {})
    dev_dependencies = source.get("devDependencies", {})

    package = {
        "name": "filmium-cell-gui",
        "private": True,
        "version": "0.0.0",
        "type": "module",
        "scripts": {"build": "vite build --config vite.cell.config.ts --outDir dist"},
        "dependencies": {name: dependencies[name] for name in sorted(npm_packages) if name in dependencies},
        "devDependencies": {
            name: dev_dependencies[name] for name in CELL_GUI_DEV_DEPENDENCIES if name in dev_dependencies
        },
    }
    (target / "gui" / "package.json").write_text(
        json.dumps(package, indent=2, ensure_ascii=False) + "\n", encoding="utf-8",
    )


def _assemble_gui(repo_root: Path, target: Path, gui_builder: GuiBuilder) -> None:
    """Kopira izvorno zatvorenje GUI-ja, projektne fajlove i pravi build."""

    gui_root = repo_root / "apps" / "gui"
    closure = collect_gui_closure(gui_root)

    forbidden = find_forbidden_gui_modules(closure)
    if forbidden:
        raise ValueError("GUI ćelije vuče CORE-only module: " + ", ".join(forbidden))

    for relative in closure.files:
        _copy(gui_root / relative, target / "gui" / relative)

    for relative in CELL_GUI_PROJECT_FILES:
        source = gui_root / relative
        if not source.is_file():
            raise FileNotFoundError(f"GUI projekat nema {relative}")
        _copy(source, target / "gui" / relative)

    _write_gui_package_json(repo_root, target, closure.npm_packages)

    dist = target / "gui" / "dist"
    gui_builder(repo_root, dist)
    if not (dist / "index.html").is_file():
        raise FileNotFoundError(f"GUI build nije napravio {dist / 'index.html'}")
```

Uz to izmeni `build_cell`:

- nov potpis sa `gui_builder: GuiBuilder = build_gui_dist` i `update: bool = False`;
- kad je `update=False`, ponašanje prema postojećem folderu ostaje isto (neprazan folder → `FileExistsError`);
- kad je `update=True`: folder mora da sadrži `cell.json` (inače `FileNotFoundError`, bez ikakve izmene foldera); pročitaj postojeći manifest; obriši sve u folderu **osim** stavki iz `PRESERVED_ON_UPDATE`; sklopi ćeliju kao i inače; `cell.json` prepiši tako da `detached_from`, `kernel_version` i `created_at` budu novi, a `port`, `core_url`, `ai` i `rag` ostanu iz postojećeg manifesta; `config/tmdb.json` se ne prepisuje ako već postoji;
- `_assemble_gui` se zove posle kopiranja Python dela, pre upisa manifesta.

Brisanje pri ažuriranju mora da ide kroz eksplicitnu listu stavki u korenu ćelije (`for child in target.iterdir(): if child.name not in PRESERVED_ON_UPDATE: ...`), nikad `shutil.rmtree(target)`.

- [ ] **Step 4: `start.bat` i CLI**

```bat
@echo off
REM FILMIUM celija: jedan proces sluzi API i GUI na istom portu.
REM API ostaje dostupan CORE-u dok god je ovaj prozor otvoren.
cd /d "%~dp0"
start "" /b cmd /c "timeout /t 3 /nobreak >nul & start "" http://127.0.0.1:{{PORT}}/#/filmium"
python -m uvicorn cell_app:app --host 127.0.0.1 --port {{PORT}}
```

`scripts/cell/build_cell.py` dobija opcioni argument `--update` (preko `argparse`) koji se prosleđuje u `build_cell(..., update=True)`, i posle sklapanja ispisuje broj GUI fajlova i putanju `gui/dist`.

- [ ] **Step 5: Pokreni testove i potvrdi da prolaze**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_cell_build.py tests/test_cell_app.py tests/test_cell_gui.py tests/test_cell_status.py -v`
Expected: PASS — uključujući `test_assembled_cell_serves_api_and_gui`.

Run: `./.venv/Scripts/python.exe -m pytest tests/ -q`
Expected: `1 failed` (zatečen), prolazi veći nego na početku plana, bez novih padova.

- [ ] **Step 6: Commit**

```bash
git add core/cell/build.py scripts/cell/build_cell.py scripts/cell/templates/start.bat.tpl tests/test_cell_build.py tests/test_cell_app.py tests/cell_helpers.py
git commit -m "feat(cell): GUI izvor i build u celiji, azuriranje koje cuva data i config"
```

---

### Task 7: Živa ćelija na `F:\FILMIUM\` — GUI, API i provera u browseru

**Files:**
- Modify: `.ai/dev-log/entries/2026-09-12-celija-filmium.md` (nova dopuna na kraju)

**Interfaces:**
- Consumes: sve prethodne zadatke.
- Produces: `F:\FILMIUM\` sa GUI build-om i punim API-jem; zapis provere.

Ovo je jedini zadatak koji dira `F:\`. Postojeći `F:\FILMIUM\data\filmium.db` (21529 redova) i `F:\FILMIUM\config\` **ne smeju** da budu obrisani ni prepisani.

- [ ] **Step 1: Zapamti stanje baze pre ažuriranja**

```bash
./.venv/Scripts/python.exe -c "import hashlib; print(hashlib.sha256(open('F:/FILMIUM/data/filmium.db','rb').read()).hexdigest())"
```

Zapiši sažetak.

- [ ] **Step 2: Ažuriraj ćeliju sa pravim GUI build-om**

```bash
./.venv/Scripts/python.exe scripts/cell/build_cell.py filmium F:/FILMIUM 8781 --update
```

Expected: izlazni kod 0; ispis broja GUI fajlova; `F:\FILMIUM\gui\dist\index.html` postoji.

- [ ] **Step 3: Potvrdi da baza i config nisu dirani**

Ponovi Step 1 — sažetak mora biti isti. Proveri da `F:\FILMIUM\config\tmdb.json` postoji.

- [ ] **Step 4: Pokreni ćeliju i proveri API**

Pokreni u pozadini iz `F:\FILMIUM`: `<venv python> -m uvicorn cell_app:app --host 127.0.0.1 --port 8781`. Sačekaj da odgovori, pa:

```bash
curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8781/cell/status
curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8781/api/v1/filmium/media
curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8781/api/v1/filmium/genres
curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8781/cell/personas
curl -s http://127.0.0.1:8781/ | head -c 300
```

Expected: `200` za sve četiri rute; `/` vraća HTML sa `<div id="root">`.

- [ ] **Step 5: Proveri GUI u browseru**

Otvori `http://127.0.0.1:8781/#/filmium` u browser panelu. Proveri, i za svaku stavku sačuvaj dokaz (tekst stranice ili screenshot):
- stranica se učitava bez grešaka u konzoli koje ruše prikaz;
- biblioteka (`#/filmium/library`) prikazuje naslove iz ćelijske baze — bar jedan naslov koji postoji u bazi (npr. neki od „The Hunger Games");
- mrežni zahtevi idu na `127.0.0.1:8781`, ne na `:8000`;
- stranica podešavanja (`#/filmium/settings` ili stvarna putanja) nema „API ključevi" ni „AI modeli";
- nema CORE sidebar-a ni ruta drugih domena.

Ako nešto od ovoga ne radi, uzrok se rešava u izvoru repoa (Task 1–6), uz test, pa se ponavlja od Step 2 — nikad ručnom izmenom fajlova u `F:\FILMIUM`.

- [ ] **Step 6: Ugasi server i proveri CORE**

Ugasi uvicorn. Run: `./.venv/Scripts/python.exe -m pytest tests/ -q` — Expected: `1 failed` (zatečen), bez novih padova. Run (iz `apps/gui`): `npx vitest run 2>&1 | tail -6` — Expected: padovi isti kao na početku Task 1.

- [ ] **Step 7: Dev-log i commit**

Dopiši na kraj `.ai/dev-log/entries/2026-09-12-celija-filmium.md` odeljak „Dopuna — GUI i API ćelije" sa: šta se sad pokreće jednim `start.bat`-om, rezultati Step 4 i Step 5, broj GUI fajlova, potvrda da baza nije dirana (sažetak pre i posle), i šta ostaje (CORE Settings „Ćelijski sistem", beleške o nadogradnji, RAG nad atomima, sopstveni git ćelije).

```bash
git add .ai/dev-log/entries/2026-09-12-celija-filmium.md
git commit -m "docs(dev-log): FILMIUM celija na F:\ sluzi GUI i ceo API"
```

---

## Šta ovaj plan namerno ne radi

- CORE Settings ekran „Ćelijski sistem" (tabela `cells`, skeniranje, „Poveži / Dodaj domen").
- Beleške o nadogradnji (`cell_upgrade_notes`, `POST /cell/upgrades`, pozadinski radnik).
- RAG nad `.ai/atomi/`.
- Sopstveni git repozitorijum ćelije i prepisivanje istorije.
- Folder-browser nad `/api/v1/filmium/filesystem/browse` kao lepša zamena za ručni unos putanje.
- Brisanje FILMIUM koda iz CORE-a.
