import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";

import react from "@vitejs/plugin-react";
import { defineConfig, type Plugin } from "vite";


// ==========          VITE — ĆELIJA (generički)          ==========

const ROOT = __dirname;

type CellGuiPolicy = {
  /** CORE-only modul -> ćelijska zamena, putanje relativne na `ROOT`. */
  substitutions: Record<string, string>;
  /** Prefiksi modula (relativni na `ROOT`) koje ćelija ne sme da nosi. */
  forbidden_prefixes: string[];
};

/** Politika GUI-ja ćelije; isti fajl čita i Python sklapač (`core/cell/gui.py`). */
const POLICY: CellGuiPolicy = JSON.parse(
  readFileSync(resolve(ROOT, "cell-substitutions.json"), "utf-8"),
);
const SUBSTITUTIONS = POLICY.substitutions;

/**
 * Normalizacija SAMO za poređenje putanja, ne za stvarno učitavanje: obrnute
 * kose crte (Windows), odbačen `?query` deo (Vite/Rolldown ume da doda sufiks
 * na razrešen id, npr. `?direct`), i mala slova — Windows diskovi ne
 * razlikuju velika/mala slova, pa `this.resolve` može da vrati isti fajl sa
 * drugačije napisanim slovom diska (`C:` vs `c:`) nego `resolve(ROOT, ...)`.
 * Bez ovoga bi poređenje ćutke promašilo i zabranjen CORE-only modul bi ušao
 * u ćelijski build bez ijedne greške pri build-u.
 */
const normalizeForMatch = (path: string): string =>
  path.replace(/\\/g, "/").split("?")[0].toLowerCase();

type Zamena = {
  /** Apsolutna putanja originala, neizmenjena — samo za poruke o grešci. */
  originalAbs: string;
  /** Normalizovan ključ za poređenje. */
  kljuc: string;
  /** Apsolutna putanja zamene — vraća se iz `resolveId` kao stvaran put. */
  zamenaAbs: string;
};

const ZAMENE_LISTA: Zamena[] = Object.entries(SUBSTITUTIONS).map(
  ([from, to]) => {
    const originalAbs = resolve(ROOT, from);
    return {
      originalAbs,
      kljuc: normalizeForMatch(originalAbs),
      zamenaAbs: resolve(ROOT, to),
    };
  },
);

const ZAMENE = new Map(ZAMENE_LISTA.map((z) => [z.kljuc, z.zamenaAbs]));

/** Normalizovan koren GUI projekta sa završnom kosom crtom, za relativne id-jeve. */
const KOREN_KLJUC = `${normalizeForMatch(ROOT).replace(/\/+$/, "")}/`;

const ZABRANJENI_PREFIKSI = POLICY.forbidden_prefixes.map((prefiks) => ({
  prefiks,
  kljuc: normalizeForMatch(prefiks),
}));

/** Moduli iz grafa (id-jevi) čija putanja relativna na koren počinje zabranjenim prefiksom. */
function zabranjeniModuli(idjevi: Iterable<string>): string[] {
  const nalazi: string[] = [];
  for (const id of idjevi) {
    const kljuc = normalizeForMatch(id);
    if (!kljuc.startsWith(KOREN_KLJUC)) {
      continue;
    }
    const relativno = kljuc.slice(KOREN_KLJUC.length);
    if (ZABRANJENI_PREFIKSI.some((z) => relativno.startsWith(z.kljuc))) {
      nalazi.push(relativno);
    }
  }
  return nalazi;
}

/** Sufiksi pod kojima relativan uvoz može da pogodi fajl — isto kao `core/cell/gui.py`. */
const KANDIDAT_SUFIKSI = ["", ".ts", ".tsx", ".js", "/index.ts", "/index.tsx"];

/**
 * Zamena za relativan uvoz, izračunata BEZ razrešavanja originala.
 *
 * U ćelijinom `gui/` originali (npr. `CoreAssistantChat.tsx`) namerno ne
 * postoje, a kopirani fajlovi ih i dalje uvoze — `this.resolve` bi tamo
 * vratio `null` i build bi pao na "Could not resolve". Zato se kandidat-putanje
 * porede sa mapom zamena pre nego što se išta traži na disku.
 */
function zamenaZaRelativanUvoz(source: string, importer: string): string | null {
  if (!source.startsWith(".")) {
    return null;
  }
  const baza = resolve(dirname(importer.split("?")[0]), source);
  for (const sufiks of KANDIDAT_SUFIKSI) {
    const zamena = ZAMENE.get(normalizeForMatch(baza + sufiks));
    if (zamena) {
      return zamena;
    }
  }
  return null;
}

/**
 * CORE-only modul menja ćelijskim. Relativan uvoz se prvo poredi po
 * kandidat-putanjama (radi i kad original ne postoji — u ćeliji); tek ako tu
 * nema pogotka, uvoz se normalno razreši i porede se razrešene apsolutne
 * putanje, pa zamena ne zavisi od toga kako je uvoz napisan
 * (`../chat/CoreAssistantChat`, sa ili bez ekstenzije).
 *
 * `buildEnd` je bezbednosna mreža nezavisna od `resolveId`-a iznad: proverava
 * STVARNE module koje je build video (`this.getModuleIds()`), pa i kad bi
 * poređenje u `resolveId`-u iz nekog razloga promašilo, zabranjen CORE-only
 * modul u grafu prekida build umesto da tiho ode u paket. Isti `buildEnd`
 * prekida build i ako ijedan modul iz grafa (relativno na koren GUI-ja)
 * počinje prefiksom iz `forbidden_prefixes` — ista lista koju proverava
 * Python sklapač.
 */
function cellSubstitutions(): Plugin {
  return {
    name: "cell-substitutions",
    enforce: "pre",
    async resolveId(source, importer, options) {
      if (!importer) {
        return null;
      }
      const direktnaZamena = zamenaZaRelativanUvoz(source, importer);
      if (direktnaZamena) {
        return direktnaZamena;
      }
      const resolved = await this.resolve(source, importer, {
        ...options,
        skipSelf: true,
      });
      if (!resolved) {
        return null;
      }
      return ZAMENE.get(normalizeForMatch(resolved.id)) ?? null;
    },
    buildEnd() {
      const idjevi = Array.from(this.getModuleIds());
      const vidjeniModuli = new Set(idjevi.map((id) => normalizeForMatch(id)));
      const procureli = ZAMENE_LISTA.filter((z) => vidjeniModuli.has(z.kljuc));

      const zabranjeni = zabranjeniModuli(idjevi);
      if (zabranjeni.length > 0) {
        this.error(
          "Ćelijski build je učitao modul koji ćelija ne sme da nosi "
          + "(forbidden_prefixes u apps/gui/cell-substitutions.json): "
          + zabranjeni.join(", ")
          + ". Ukloni uvoz ili dodaj ćelijsku zamenu u substitutions.",
        );
      }

      if (procureli.length > 0) {
        this.error(
          "Ćelijski build je učitao zabranjen CORE-only modul uprkos mapi "
          + "zamena (apps/gui/cell-substitutions.json), umesto ćelijske "
          + "zamene: "
          + procureli.map((z) => z.originalAbs).join(", ")
          + ". Ovo ne sme da se desi — proveri podudaranje putanja (velika/"
          + "mala slova diska, query deo) u cell-substitutions.json.",
        );
      }
    },
  };
}

/**
 * `cell.html` ostaje ime izvornog fajla u repou (ne sme da preklopi CORE-ov
 * `index.html`), ali izlaz build-a mora da se zove `index.html`: FastAPI
 * ćelije servira build sa `StaticFiles(directory=dist, html=True)`, koje
 * `index.html` traži na `/`, a Python sklapač proverava baš to ime da utvrdi
 * da je build uspeo. `enforce: "post"` osigurava da plugin radi pošto je
 * Vite-ov ugrađeni HTML plugin već upisao `cell.html` u paket.
 */
function cellHtmlAsIndex(): Plugin {
  return {
    name: "cell-html-as-index",
    enforce: "post",
    generateBundle(_options, bundle) {
      // Samo menja `fileName` na mestu — Rolldown (za razliku od Rollup-a) ne
      // podržava presklapanje ključeva `bundle` objekta u ovoj kuki; sam upis
      // na disk ionako ide po `fileName` svakog stavka, ne po ključu mape.
      for (const asset of Object.values(bundle)) {
        if (asset.fileName === "cell.html") {
          asset.fileName = "index.html";
        }
      }
    },
  };
}

export default defineConfig({
  plugins: [cellSubstitutions(), react(), cellHtmlAsIndex()],
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
