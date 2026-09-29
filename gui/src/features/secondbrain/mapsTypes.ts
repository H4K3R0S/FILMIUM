// ==========          MAPS GRAF — tipovi (oblik `/api/v1/second-brain/maps`)          ==========
// Isti oblik kao referentni `data/brain.json` iz MAPS vodiča, prošireno sa `links`/`status`.

export type MapsKind = "root" | "area" | "skill" | "file" | "routine" | "run" | "app";

export interface MapsNode {
  id: string;
  kind: MapsKind;
  label: string;
  area: string | null;
  /** 0 root · 1 SKILLS · 2 MEMORY (area/file) · 3 ROUTINES (routine/run) · 4 APPLICATIONS */
  layer: number;
  path: string | null;
  note: string;
  /** ISO datum poslednje izmene / vreme run-a; null = nepoznato */
  changed: string | null;
  /** stepen čvora (broj veza) */
  links: number;
  status: string | null;
}

export interface MapsLink {
  source: string;
  target: string;
}

export interface MapsArea {
  key: string;
  label: string;
  count: number;
}

export interface MapsGraph {
  center: { id: string; label: string };
  nodes: MapsNode[];
  links: MapsLink[];
  areas: MapsArea[];
  stats: { files: number; links: number; runs: number };
}

/** Drugi sistem sa Second Brain-om (sfera na obodu prozora). */
export interface Sphere {
  id: string;
  label: string;
  port: number;
  url: string;
  online: boolean;
  total: number;
  areas: MapsArea[];
}

export type MapsView = "rings" | "circle" | "areas" | "links" | "timeline" | "orbit";
export const MAPS_VIEWS: Array<{ id: MapsView; label: string }> = [
  { id: "rings", label: "RINGS" },
  { id: "circle", label: "CIRCLE" },
  { id: "areas", label: "AREAS" },
  { id: "links", label: "LINKS" },
  { id: "timeline", label: "TIMELINE" },
  { id: "orbit", label: "3D ORBIT" },
];
export const MAPS_KINDS: MapsKind[] = ["skill", "file", "routine", "app", "run"];
