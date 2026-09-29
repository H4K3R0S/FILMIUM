import { useCallback } from "react";

import type { DomainId } from "../../lib/domainTheme";
import { useCoreSetting } from "../../lib/useCoreSetting";


// ==========          THEME EFFECT: AMBIENT POZADINA          ==========
/*
 * "Connected Dots" ambijentalna pozadina (povezane tačke + lebdeći glow
 * spotovi na crnoj podlozi). Korisnik u Core Settings → Theme bira gde je
 * efekat aktivan:
 *   - "CORE (sve stranice)" — globalno, na svakom ekranu, ili
 *   - po pojedinačnom domenu (štiklirani domen dobija efekat).
 * Boje tačaka prati aktivni domen preko --ambient-dot-* tokena teme.
 */


// ==========          localStorage KLJUČEVI          ==========

/** Efekat na svim stranicama (CORE kontekst = globalno). */
export const AMBIENT_ALL_KEY = "core.theme.ambient.all";

/** Zadrži pozadinsku sliku ispod tačaka (umesto pune crne podloge). */
export const AMBIENT_KEEP_IMAGE_KEY = "core.theme.ambient.keepImage";

/** Ključ za pojedinačni domen. */
export function ambientDomainKey(domain: AmbientDomain): string {
  return `core.theme.ambient.domain.${domain}`;
}


// ==========          DOMENI KOJI NOSE EFEKAT          ==========

/**
 * Domeni koji mogu ponaosob da nose efekat. 'core' nije u listi — CORE
 * kontekst (dashboard, settings...) pokriva globalni prekidač "sve stranice".
 */
export const AMBIENT_DOMAINS = [
  "codium",
  "filmium",
  "imperium",
  "kalima",
] as const;

export type AmbientDomain = (typeof AMBIENT_DOMAINS)[number];

/** Čitljive oznake domena za prikaz u podešavanjima. */
export const AMBIENT_DOMAIN_LABELS: Record<AmbientDomain, string> = {
  codium: "CODIUM",
  filmium: "FILMIUM",
  imperium: "IMPERIUM",
  kalima: "KALIMA",
};

export type AmbientSettings = {
  /** Globalno: efekat na svim stranicama. */
  all: boolean;
  /** Efekat po pojedinačnom domenu. */
  domains: Record<AmbientDomain, boolean>;
  /** Zadrži pozadinsku sliku ispod tačaka. */
  keepImage: boolean;
};


// ==========          CILJANJE EFEKTA          ==========

/**
 * Odlučuje da li je ambijentalni efekat aktivan za dati domen. Globalni
 * prekidač ("sve stranice") ima prednost; inače važi štikliranje domena.
 * CORE kontekst nema poseban domenski prekidač — pokriva ga samo globalni.
 */
export function isAmbientActive(
  domainId: DomainId,
  settings: AmbientSettings,
): boolean {
  // Ova ćelija (FILMIUM) NEMA ambijentalni background (Connected Dots).
  // Efekat postoji samo u CODIUM ćeliji. (Uklonjeno 2026-09-17.)
  return false;

  if (settings.all) {
    return true;
  }

  if (domainId === "core") {
    return false;
  }

  return settings.domains[domainId] === true;
}


// ==========          HOOK: PODEŠAVANJA          ==========

export type AmbientControls = {
  settings: AmbientSettings;
  setAll: (next: boolean) => void;
  setDomain: (domain: AmbientDomain, next: boolean) => void;
  setKeepImage: (next: boolean) => void;
};

/**
 * Čita i pamti sva podešavanja ambijentalnog efekta u localStorage. Broj
 * poziva hook-ova je fiksan (po jedan po domenu) da bi redosled ostao stabilan.
 */
export function useAmbientSettings(): AmbientControls {
  const [all, setAll] = useCoreSetting(AMBIENT_ALL_KEY, false);
  const [keepImage, setKeepImage] = useCoreSetting(
    AMBIENT_KEEP_IMAGE_KEY,
    false,
  );

  const [codium, setCodium] = useCoreSetting(ambientDomainKey("codium"), false);
  const [filmium, setFilmium] = useCoreSetting(
    ambientDomainKey("filmium"),
    false,
  );
  const [imperium, setImperium] = useCoreSetting(
    ambientDomainKey("imperium"),
    false,
  );
  const [kalima, setKalima] = useCoreSetting(ambientDomainKey("kalima"), false);

  const setDomain = useCallback(
    (domain: AmbientDomain, next: boolean) => {
      switch (domain) {
        case "codium":
          setCodium(next);
          return;
        case "filmium":
          setFilmium(next);
          return;
        case "imperium":
          setImperium(next);
          return;
        case "kalima":
          setKalima(next);
          return;
      }
    },
    [setCodium, setFilmium, setImperium, setKalima],
  );

  return {
    settings: {
      all,
      keepImage,
      domains: { codium, filmium, imperium, kalima },
    },
    setAll,
    setDomain,
    setKeepImage,
  };
}
