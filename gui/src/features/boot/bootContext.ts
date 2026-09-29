// ==========          BOOT KONTEKST          ==========
/*
 * Kontekst i hook stoje odvojeno od komponente namerno: fajl koji uz
 * komponentu izvozi i nešto drugo gubi hot reload — Vite tada ne ume da
 * osveži samo komponentu, nego ponovo učitava ceo modul i sa njim briše
 * stanje ekrana.
 */
import { createContext } from "react";

/**
 * Boot sekvenca je centralni tajmer paljenja CORE GUI-ja. Beleži trenutak
 * kada je aplikacija "upaljena" i omogućava komponentama da se pojavljuju
 * postepeno (sidebar, sat, dock...). Isti mehanizam koriste i CORE i buduće
 * Domain stranice koje će imati svoje jedinstvene dizajne.
 */
export type BootContextValue = {
  /** Timestamp (ms) kada je boot sekvenca započela. */
  startedAt: number;
};

export const BootContext = createContext<BootContextValue | null>(null);
