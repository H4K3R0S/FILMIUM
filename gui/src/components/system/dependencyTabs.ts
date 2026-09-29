// ==========          TABOVI PO PRIORITETU          ==========
// Čist modul: filtriranje i brojanje zavisnosti po prioritetu.
// Bez React-a, da bi logika panela mogla da se testira zasebno.

import type { SystemDependency } from "../../types/system";


export type DependencyTabId =
  | "all"
  | "critical"
  | "important"
  | "optional";

export interface DependencyTab {
  id: DependencyTabId;
  label: string;
}

/** Redosled tabova u panelu: prvo sve, pa od najhitnijeg ka opcionom. */
export const DEPENDENCY_TABS: readonly DependencyTab[] = [
  { id: "all", label: "Sve" },
  { id: "critical", label: "Hitno" },
  { id: "important", label: "Važno" },
  { id: "optional", label: "Opciono" },
];


/**
 * Vraća zavisnosti za dati tab, sa onim što nedostaje na vrhu.
 *
 * Ulazni niz se ne menja — sortira se kopija.
 */
export function selectForTab(
  dependencies: SystemDependency[],
  tab: DependencyTabId,
): SystemDependency[] {
  const rows = tab === "all"
    ? [...dependencies]
    : dependencies.filter((row) => row.severity === tab);

  // Ono što traži akciju mora biti prvo; ostalo zadržava zatečen redosled.
  return rows.sort((left, right) => {
    if (left.installed === right.installed) {
      return 0;
    }

    return left.installed ? 1 : -1;
  });
}


/** Broj zavisnosti koje nedostaju u datom tabu (za značku na tabu). */
export function countMissing(
  dependencies: SystemDependency[],
  tab: DependencyTabId,
): number {
  return selectForTab(dependencies, tab).filter(
    (row) => !row.installed,
  ).length;
}
