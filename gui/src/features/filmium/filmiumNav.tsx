import {
  Award,
  CalendarDays,
  Clapperboard,
  Download,
  Flame,
  Heart,
  History,
  LayoutDashboard,
  Library,
  Brain,
  Settings,
  Sparkles,
  Star,
  Tv,
  Upload,
  Users,
  type LucideIcon,
} from "lucide-react";
import { NavLink } from "react-router";

import { type CellNav } from "../../cell/cellNav";
import FilmiumKuratorDock from "./FilmiumKuratorDock";


// ==========          FILMIUM NAVIGACIJA (deljeni izvor)          ==========
//
// Jedini izvor FILMIUM stavki sidebara: koristi ga i CORE `Sidebar` (kad je
// FILMIUM aktivan domen) i `CellSidebar` (samostalna ćelija). Bez ovog modula
// bi se liste duplirale i vremenom razišle.

export type NavigationItem = {
  id: string;
  label: string;
  icon: LucideIcon;
  path: string | null;
};


// ==========          GLAVNE STAVKE          ==========

export const filmiumNavigationItems: NavigationItem[] = [
  { id: "filmium-uploads", label: "Uploads", icon: Upload, path: "/filmium/uploads" },
  { id: "filmium-strano", label: "Strano", icon: Clapperboard, path: "/filmium/strano" },
  { id: "filmium-domace", label: "Domaće", icon: Tv, path: "/filmium/domace" },
  { id: "filmium-animated", label: "Animirano", icon: Sparkles, path: "/filmium/animirano" },
  { id: "filmium-favorites", label: "Favoriti", icon: Heart, path: "/filmium/favorites" },
  { id: "filmium-collections", label: "Kolekcije", icon: Library, path: "/filmium/collections" },
  { id: "filmium-actors", label: "Glumci", icon: Users, path: "/filmium/actors" },
  { id: "filmium-torrents", label: "Torrenti", icon: Download, path: "/filmium/torrents" },
  { id: "filmium-history", label: "Istorija", icon: History, path: "/filmium/history" },
];


// ==========          ISTRAŽI          ==========

export const filmiumDiscoveryItems: NavigationItem[] = [
  { id: "filmium-recommended", label: "Preporučeno", icon: Star, path: "/filmium/recommended" },
  { id: "filmium-trending", label: "U trendu", icon: Flame, path: "/filmium/trending" },
  { id: "filmium-top-rated", label: "Najbolje ocenjeni", icon: Award, path: "/filmium/top-rated" },
  { id: "filmium-upcoming", label: "Nadolazeći", icon: CalendarDays, path: "/filmium/upcoming" },
];


// ==========          CELLNAV ADAPTER (ćelija + CORE embed)          ==========
//
// Generički opis sidebara koji troše i `CellSidebar` (samostalna ćelija) i CORE
// most (chromeless embed). FILMIUM je odcepljen pre generalizacije, pa svoje
// stavke drži u listama gore; ovde ih sklapamo u `CellNav`. Samo stavke sa
// stvarnom rutom (path !== null) ulaze.

function toCellItems(items: NavigationItem[]) {
  return items
    .filter((item): item is NavigationItem & { path: string } => item.path !== null)
    .map((item) => ({ id: item.id, label: item.label, icon: item.icon, path: item.path }));
}

export const filmiumNav: CellNav = {
  brand: "FILMIUM",
  homePath: "/filmium",
  settingsPath: "/filmium/settings",
  railItems: [
    { label: "Početna", icon: LayoutDashboard, path: "/filmium", end: true },
    { label: "Second Brain", icon: Brain, path: "/second-brain" },
    { label: "Podešavanja", icon: Settings, path: "/filmium/settings" },
  ],
  sections: [
    { label: "FILMIUM", items: toCellItems(filmiumNavigationItems) },
    { label: "ISTRAŽI", items: toCellItems(filmiumDiscoveryItems) },
  ],
  AgentDock: FilmiumKuratorDock,
};


// ==========          NAVIGACIONA STAVKA          ==========

type SidebarNavigationItemProps = {
  item: NavigationItem;
};

/**
 * Prikazuje aktivnu ili trenutno nedostupnu (path === null) navigacionu stavku.
 */
export function SidebarNavigationItem({ item }: SidebarNavigationItemProps) {
  const Icon = item.icon;

  if (item.path === null) {
    return (
      <button className="navigation-item" disabled type="button">
        <Icon aria-hidden="true" className="navigation-icon" size={19} strokeWidth={1.8} />
        <span>{item.label}</span>
        <span className="navigation-badge">USKORO</span>
      </button>
    );
  }

  return (
    <NavLink
      className={({ isActive }) => `navigation-item ${isActive ? "active" : ""}`}
      end
      to={item.path}
    >
      <Icon aria-hidden="true" className="navigation-icon" size={19} strokeWidth={1.8} />
      <span>{item.label}</span>
    </NavLink>
  );
}
