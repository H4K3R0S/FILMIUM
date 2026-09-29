import { type ComponentType, type ReactNode } from "react";
import { type LucideIcon } from "lucide-react";


// ==========          NAVIGACIJA ĆELIJE (generički opis)          ==========
//
// Domen-agnostičan opis sidebara ćelije. Svaki domen izloži jedan `CellNav`
// objekat u `features/<domen>/<domen>Nav.tsx`; generički `CellSidebar` ga
// renderuje istim App.css klasama kao CORE `Sidebar`. Bez ijednog domenskog
// imena u okviru ćelije — sve što je specifično stiže kroz ovaj opis.

export type CellNavItem = {
  id: string;
  label: string;
  icon: LucideIcon;
  path: string;
};

export type CellNavSection = {
  label: string;
  items: CellNavItem[];
};

/** Prečica u gornjem ikonskom redu sidebara. */
export type CellRailItem = {
  label: string;
  icon: LucideIcon;
  path: string;
  /** `end` za tačnu rutu (npr. početna `/kalima`). */
  end?: boolean;
};

export type CellNav = {
  /** Brend u zaglavlju i naslovima (npr. "KALIMA"). */
  brand: string;
  /** Početna ruta domena (npr. "/kalima"). */
  homePath: string;
  /** Ruta podešavanja domena (npr. "/kalima/settings"), ili `null` ako ih nema. */
  settingsPath: string | null;
  /** Prečice u gornjem ikonskom redu. */
  railItems: CellRailItem[];
  /** Srednji pojas: sekcije sa stavkama. */
  sections: CellNavSection[];
  /**
   * Opcioni provajder konteksta koji obavija ceo domenski sadržaj ćelije
   * (npr. CODIUM `CodiumUiProvider`). Domeni bez konteksta (KALIMA, IMPERIUM)
   * ga izostave — `CellApp` tada koristi prolaznu obertku.
   */
  Wrapper?: ComponentType<{ children: ReactNode }>;
  /** Globalni dock (dole-centar) sa domenskim Agentom — jedan po ceo shell. */
  AgentDock?: ComponentType;
};


// ==========          SERIJALIZOVAN NAV (za CORE preko postMessage)          ==========
//
// Kad ćelija radi chromeless (embed u CORE), ne može da pošalje komponente
// ikona kroz `postMessage` — pa se ikone svode na lucide IME (`displayName`),
// a CORE ih vraća u komponente lookup-om po imenu.

export type SerializedCellNavItem = { id: string; label: string; icon: string; path: string };
export type SerializedCellRailItem = { label: string; icon: string; path: string; end?: boolean };
export type SerializedCellNav = {
  brand: string;
  homePath: string;
  settingsPath: string | null;
  railItems: SerializedCellRailItem[];
  sections: { label: string; items: SerializedCellNavItem[] }[];
};

function iconName(icon: LucideIcon): string {
  return (icon as { displayName?: string }).displayName ?? "";
}

/** Serijalizuje nav (ikone → lucide imena) za slanje CORE-u preko postMessage. */
export function serializeCellNav(nav: CellNav): SerializedCellNav {
  return {
    brand: nav.brand,
    homePath: nav.homePath,
    settingsPath: nav.settingsPath,
    railItems: nav.railItems.map((r) => ({ label: r.label, icon: iconName(r.icon), path: r.path, end: r.end })),
    sections: nav.sections.map((s) => ({
      label: s.label,
      items: s.items.map((i) => ({ id: i.id, label: i.label, icon: iconName(i.icon), path: i.path })),
    })),
  };
}
