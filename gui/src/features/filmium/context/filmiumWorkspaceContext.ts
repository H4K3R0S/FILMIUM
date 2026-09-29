// ==========          FILMIUM WORKSPACE KONTEKST          ==========
// Sam kontekst; provajder je u `FilmiumWorkspace.tsx`, hook u
// `useFilmiumWorkspace.ts`. Podela postoji zbog hot reload-a: modul koji uz
// komponentu izvozi i nešto drugo Vite ne ume da osveži bez gubitka stanja.
//
// Tip dolazi iz fajla provajdera — uvoz je samo tipski, pa ga build briše i
// nema kruženja u izvršnom kodu.
import { createContext } from "react";

import type { FilmiumWorkspaceContextValue } from "./FilmiumWorkspace";

export const FilmiumWorkspaceContext =
  createContext<FilmiumWorkspaceContextValue | null>(null);
