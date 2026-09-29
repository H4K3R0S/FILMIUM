// ==========          WORKSPACE HOOK          ==========
// Odvojen od provajdera: fajl koji uz komponentu izvozi i nešto drugo gubi hot
// reload, pa bi svaka izmena provajdera rušila stanje celog FILMIUM ekrana.
import { useContext } from "react";

import { FilmiumWorkspaceContext } from "./filmiumWorkspaceContext";
import type { FilmiumWorkspaceContextValue } from "./FilmiumWorkspace";

/**
 * Vraća zajedničko stanje trenutnog FILMIUM radnog okruženja.
 */
export function useFilmiumWorkspace(): FilmiumWorkspaceContextValue {
  const context = useContext(FilmiumWorkspaceContext);

  if (context === null) {
    throw new Error(
      "useFilmiumWorkspace mora biti korišćen unutar "
      + "FilmiumWorkspaceProvider komponente.",
    );
  }

  return context;
}