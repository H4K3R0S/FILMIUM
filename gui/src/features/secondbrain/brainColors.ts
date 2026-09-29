import {
  Bot, Box, Boxes, Brain, Circle, Clock, Cog, Database, File, Film, Languages,
  Layers, Map as MapIcon, Plug, ScanSearch, Shield, ShoppingCart, Sparkles,
  Wallet, Wrench, type LucideIcon,
} from "lucide-react";

export const GROUP_COLORS: Record<string, string> = {
  codium: "#e3b341",   // žuto
  imperium: "#4f9df0", // plavo
  kalima: "#4fcf8a",   // zeleno
  filmium: "#b57be0",  // ljubičasto
  core: "#ff9d57",     // narandžasto
  // Ćelijski Second Brain — semantički obruči oko domena.
  skills: "#e3b341",   // žuto — moći/kod domena
  memory: "#b57be0",   // ljubičasto — znanje (.ai + docs)
  alati: "#4fcf8a",    // zeleno — alati koje domen koristi
  // Stari po-oblasti nazivi (zadržani radi kompatibilnosti).
  backend: "#7fd4e0",  // cian
  gui: "#e3b341",      // žuto
  domen: "#4f9df0",    // plavo
  atomi: "#b57be0",    // ljubičasto
  docs: "#8aa0b4",     // sivo-plavo
};
export const NEUTRAL = "#7fd4e0"; // cian — aplikacije / core rutine

export function groupColor(group: string): string {
  return GROUP_COLORS[group] ?? NEUTRAL;
}

/** Boja cvora: app i core-vezane rutine su neutralno; ostalo po grupi. */
export function nodeColor(node: { kind: string; group: string }): string {
  if (node.kind === "app") return NEUTRAL;
  if (node.kind === "routine" && node.group === "core") return NEUTRAL;
  return groupColor(node.group);
}

const ICONS: Record<string, LucideIcon> = {
  brain: Brain, sparkles: Sparkles, boxes: Boxes, box: Box, bot: Bot, file: File,
  plug: Plug, cog: Cog, database: Database, shield: Shield, map: MapIcon, layers: Layers,
  cart: ShoppingCart, wallet: Wallet, clock: Clock,
  // Ikone alata (Alati obruč).
  wrench: Wrench, scan: ScanSearch, languages: Languages, film: Film,
};
export function iconFor(name: string): LucideIcon { return ICONS[name] ?? Circle; }

/** Tacke pravilnog šestougla (za <polygon points>), centriran u (0,0). */
export function hexPoints(r: number): string {
  const pts: string[] = [];
  for (let i = 0; i < 6; i += 1) {
    const a = (Math.PI / 3) * i - Math.PI / 2;
    pts.push(`${(r * Math.cos(a)).toFixed(2)},${(r * Math.sin(a)).toFixed(2)}`);
  }
  return pts.join(" ");
}

/** 4-kraka zvezda (skills glyph). */
export function starPoints(r: number): string {
  const inner = r * 0.38;
  const pts: string[] = [];
  for (let i = 0; i < 8; i += 1) {
    const rad = i % 2 === 0 ? r : inner;
    const a = (Math.PI / 4) * i - Math.PI / 2;
    pts.push(`${(rad * Math.cos(a)).toFixed(2)},${(rad * Math.sin(a)).toFixed(2)}`);
  }
  return pts.join(" ");
}
