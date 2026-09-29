// ==========          STATISTIKA BIBLIOTEKE (računica)          ==========
// Čist modul: samo brojanje, bez React-a. Odvojen od komponente jer fajl koji
// uz komponentu izvozi i nešto drugo gubi hot reload — a i ovako se testira
// bez renderovanja.
import type { FilmiumLibraryScanResult } from "../../../../types/filmiumLibrary";


export type FilmiumLibraryStatisticsValue = {
  attention: number;
  available: number;
  catalogOnly: number;
  newContent: number;
  subtitleRepairs: number;
  total: number;
  unavailable: number;
};


/**
 * Izračunava zajedničku statistiku svih trenutnih rezultata skeniranja.
 */
export function calculateLibraryStatistics(
  scanResults: Record<number, FilmiumLibraryScanResult>,
): FilmiumLibraryStatisticsValue {
  const entries = Object.values(scanResults).flatMap(
    (result) => result.entries,
  );

  return {
    total: entries.length,
    available: entries.filter(
      (entry) => entry.catalog_status === "available",
    ).length,
    unavailable: entries.filter(
      (entry) => entry.catalog_status === "unavailable",
    ).length,
    catalogOnly: entries.filter(
      (entry) => entry.catalog_status === "catalog_only",
    ).length,
    newContent: entries.filter(
      (entry) => entry.catalog_status === "new",
    ).length,
    subtitleRepairs: Object.values(scanResults).reduce(
      (total, result) => total + result.subtitle_repair_count,
      0,
    ),
    attention: entries.filter(
      (entry) =>
        !entry.can_import ||
        entry.catalog_status === "ambiguous",
    ).length,
  };
}
