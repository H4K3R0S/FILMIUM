import type { BrainNode } from "../../types/secondBrain";
import type { PositionedNode } from "./layout";

// ==========          RASPORED ĆELIJSKOG SECOND BRAIN-a          ==========
//
// Domen u CENTRU (kind "cell"), pa semantički obruči: Skills (kod), Memory
// (znanje), Alati (alati domena, kind "tool"). Za razliku od CORE `layoutGraph`
// (fiksni radijusi po CORE kind-ovima), ovde su radijusi po OBRUČU (grupi):
// fajlovi se ravnomerno slažu u luk svog obruča, alati na spoljni prsten,
// obruč-hubovi (kind "area") kao markeri na vrhu svog opsega.

const TWO_PI = Math.PI * 2;
const START = -Math.PI / 2;

// Opsezi obruča (radijusi u logičkim jedinicama, isti prostor kao CORE canvas).
export const CELL_RINGS: Record<string, { min: number; max: number }> = {
  skills: { min: 130, max: 300 },
  memory: { min: 345, max: 495 },
  alati: { min: 560, max: 560 },
};
const ROW_GAP = 16;

/** Krugovi-vodiči (slabi prstenovi) za ćelijski canvas. */
export const CELL_RING_GUIDES: number[] = [300, 495, 560];

/** Labele obruča na svom radijusu (uspravne, dekorativne). */
export const CELL_RING_LABELS: Array<{ label: string; r: number }> = [
  { label: "SKILLS", r: 300 },
  { label: "MEMORY", r: 495 },
  { label: "ALATI", r: 560 },
];

function polar(r: number, a: number) {
  return { x: r * Math.cos(a), y: r * Math.sin(a) };
}

/** Uredan raster u luku (redovi = koncentrični lukovi, kolone = ugao). */
function arcGrid(
  i: number,
  n: number,
  rMin: number,
  rMax: number,
  rowGap: number,
): { r: number; a: number } {
  const rows = Math.max(1, Math.floor((rMax - rMin) / rowGap) + 1);
  const cols = Math.max(1, Math.ceil(n / rows));
  const row = Math.min(rows - 1, Math.floor(i / cols));
  const col = i % cols;
  const r = rows === 1 ? (rMin + rMax) / 2 : rMin + (row / (rows - 1)) * (rMax - rMin);
  const a = START + ((col + 0.5) / cols) * TWO_PI;
  return { r, a };
}

export function layoutCellBrain(nodes: BrainNode[]): PositionedNode[] {
  // Stabilan indeks fajlova po obruču (sort po id-u).
  const filesByRing = new Map<string, string[]>();
  for (const node of nodes) {
    if (node.kind === "file" || node.kind === "routine") {
      const list = filesByRing.get(node.group) ?? [];
      list.push(node.id);
      filesByRing.set(node.group, list);
    }
  }
  const fileIndex = new Map<string, { i: number; n: number }>();
  for (const [, ids] of filesByRing) {
    ids.sort((a, b) => a.localeCompare(b));
    ids.forEach((id, i) => fileIndex.set(id, { i, n: ids.length }));
  }

  // Alati: ravnomerno po spoljnom prstenu (stabilan poredak po id-u).
  const toolIds = nodes.filter((n) => n.kind === "tool").map((n) => n.id).sort();
  const toolIndex = new Map<string, number>();
  toolIds.forEach((id, i) => toolIndex.set(id, i));

  return nodes.map((node) => {
    let out: { x: number; y: number; angle: number; ring: number };
    if (node.kind === "cell") {
      out = { x: 0, y: 0, angle: 0, ring: 0 };
    } else if (node.kind === "area") {
      // Hub obruča: marker na vrhu svog opsega (spoljna ivica).
      const band = CELL_RINGS[node.group] ?? CELL_RINGS.skills;
      out = { ...polar(band.max, START), angle: START, ring: band.max };
    } else if (node.kind === "tool") {
      const i = toolIndex.get(node.id) ?? 0;
      const n = Math.max(1, toolIds.length);
      // +0.5 koraka: nijedan alat ne pada tačno na vrh (gde je hub „Alati").
      const a = START + ((i + 0.5) / n) * TWO_PI;
      out = { ...polar(CELL_RINGS.alati.min, a), angle: a, ring: CELL_RINGS.alati.min };
    } else {
      // file / routine: u luku svog obruča (Skills ili Memory).
      const band = CELL_RINGS[node.group] ?? CELL_RINGS.memory;
      const meta = fileIndex.get(node.id) ?? { i: 0, n: 1 };
      const g = arcGrid(meta.i, meta.n, band.min, band.max, ROW_GAP);
      out = { ...polar(g.r, g.a), angle: g.a, ring: g.r };
    }
    return { ...node, ...out };
  });
}
