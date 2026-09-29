// ==========          MAPS RASPOREDI — čiste funkcije (bez DOM-a, bez D3)          ==========
// Ulaz: vidljivi čvorovi + veze + dimenzije + vreme `t` (sekunde, za spor pokret).
// Izlaz: pozicije u pikselima (koordinatni sistem platna, centar = W/2,H/2).

import type { MapsKind, MapsLink, MapsNode } from "./mapsTypes";

export type Pt = { id: string; x: number; y: number; z: number; r: number; alpha: number };

export const RING_LABELS = ["SKILLS", "MEMORY", "ROUTINES", "APPLICATIONS"];
/** Radijus prstena po sloju kao deo poluprečnika platna (0 root … 4 APPLICATIONS). */
export const RING_FRAC = [0, 0.2, 0.5, 0.74, 0.92];
const RING_SPEED = [0, 0.05, 0.012, -0.02, 0.008]; // rad/s kad je `motion` uključen
const PAD = 44;

// Paleta oblasti (kao na referentnoj slici): plava · žuta · zelena · ljubičasta · roze · lime · siva …
const AREA_PALETTE = [
  "#4f8ef7", "#f5b731", "#34d399", "#a78bfa", "#f472b6", "#a3e635",
  "#22d3ee", "#fb923c", "#e879f9", "#2dd4bf", "#facc15", "#93c5fd",
];
const KIND_COLOR: Record<MapsKind, string> = {
  root: "#ff9d57", area: "#e2e8f0", skill: "#ff9d57", file: "#9aa3b2",
  routine: "#e3b341", run: "#6b7280", app: "#4f9df0",
};

export function areaColor(areaIndex: number): string {
  return AREA_PALETTE[areaIndex % AREA_PALETTE.length];
}

/** Boja čvora: oblast (ako je ima) inače boja vrste. */
export function nodeColor(node: MapsNode, areaIndex: Map<string, number>): string {
  if (node.area !== null && node.kind !== "area") {
    const i = areaIndex.get(node.area);
    if (i !== undefined) return areaColor(i);
  }
  if (node.kind === "area" && node.area !== null) {
    const i = areaIndex.get(node.area);
    if (i !== undefined) return areaColor(i);
  }
  return KIND_COLOR[node.kind];
}

/** Poluprečnik tačke: vrsta + blago po broju veza (kao u referenci: „dot size = link count"). */
export function nodeRadius(node: MapsNode): number {
  const base: Record<MapsKind, number> = { root: 16, area: 9, skill: 5, file: 3.2, routine: 4.5, run: 2, app: 6 };
  const bonus = node.kind === "file" || node.kind === "skill" ? Math.min(3, Math.sqrt(Math.max(0, node.links - 1)) * 0.6) : 0;
  return base[node.kind] + bonus;
}

function mulberry32(seed: number): () => number {
  let a = seed >>> 0;
  return () => {
    a = (a + 0x6d2b79f5) >>> 0;
    let t = a;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

function radius(W: number, H: number): number {
  return Math.max(60, Math.min(W, H) / 2 - PAD);
}

/** Ključ klastera: oblast, a čvorovi bez oblasti se grupišu po vrsti. */
function clusterKey(n: MapsNode): string {
  return n.area ?? n.kind;
}

function groupBy(nodes: MapsNode[]): Map<string, MapsNode[]> {
  const m = new Map<string, MapsNode[]>();
  for (const n of nodes) {
    const k = clusterKey(n);
    const arr = m.get(k);
    if (arr) arr.push(n);
    else m.set(k, [n]);
  }
  return m;
}

function pt(n: MapsNode, x: number, y: number, z = 0, alpha = 1): Pt {
  return { id: n.id, x, y, z, r: nodeRadius(n), alpha };
}

// ----------          RINGS          ----------

/** Koncentrični prstenovi po sloju; MEMORY sloj je podeljen u sektore po oblasti (hub u sredini
 *  sektora, fajlovi u više gustih pod-prstenova). Ostali slojevi ravnomerno po krugu. */
export function layoutRings(nodes: MapsNode[], W: number, H: number, t: number): Pt[] {
  const out: Pt[] = [];
  if (nodes.length === 0) return out;
  const cx = W / 2;
  const cy = H / 2;
  const R = radius(W, H);
  const byLayer = new Map<number, MapsNode[]>();
  for (const n of nodes) {
    const arr = byLayer.get(n.layer);
    if (arr) arr.push(n);
    else byLayer.set(n.layer, [n]);
  }
  for (const n of byLayer.get(0) ?? []) out.push(pt(n, cx, cy));

  // MEMORY: sektori po oblasti
  const mem = (byLayer.get(2) ?? []).filter((n) => n.kind !== "area");
  const hubs = (byLayer.get(2) ?? []).filter((n) => n.kind === "area");
  const groups = groupBy(mem);
  for (const h of hubs) if (!groups.has(h.area ?? "")) groups.set(h.area ?? h.id, []);
  const keys = [...groups.keys()];
  const total = keys.reduce((s, k) => s + Math.max(1, groups.get(k)?.length ?? 0), 0);
  const GAP = keys.length > 12 ? 0.02 : 0.06; // rad između sektora (mnogo oblasti → tesnije)
  let a0 = -Math.PI / 2 + t * RING_SPEED[2];
  const rIn = R * 0.4;
  const rOut = R * 0.62;
  for (const k of keys) {
    const items = groups.get(k) ?? [];
    const span = ((2 * Math.PI - GAP * keys.length) * Math.max(1, items.length)) / total;
    const mid = a0 + span / 2;
    const hub = hubs.find((h) => h.area === k);
    if (hub) out.push(pt(hub, cx + Math.cos(mid) * (rIn - 18), cy + Math.sin(mid) * (rIn - 18)));
    // gusti pod-prstenovi unutar sektora
    const arc = Math.max(1, span * rIn);
    const perRow = Math.max(3, Math.floor(arc / 13));
    const rows = Math.max(1, Math.ceil(items.length / perRow));
    const step = rows > 1 ? Math.min(14, (rOut - rIn) / (rows - 1)) : 0;
    items.forEach((n, i) => {
      const row = Math.floor(i / perRow);
      const inRow = Math.min(perRow, items.length - row * perRow);
      const col = i - row * perRow;
      const frac = inRow === 1 ? 0.5 : (col + 0.5) / inRow;
      const ang = a0 + span * (0.06 + 0.88 * frac);
      const rr = rIn + row * step + (row % 2) * 3;
      out.push(pt(n, cx + Math.cos(ang) * rr, cy + Math.sin(ang) * rr));
    });
    a0 += span + GAP;
  }

  // Ostali slojevi ravnomerno; run-ovi na malo većem radijusu unutar ROUTINES prstena.
  for (const L of [1, 3, 4]) {
    const arr = byLayer.get(L) ?? [];
    const main = arr.filter((n) => n.kind !== "run");
    const runs = arr.filter((n) => n.kind === "run");
    const place = (list: MapsNode[], rr: number, phase: number) => {
      list.forEach((n, i) => {
        const ang = -Math.PI / 2 + phase + (i / Math.max(1, list.length)) * 2 * Math.PI + t * RING_SPEED[L];
        out.push(pt(n, cx + Math.cos(ang) * rr, cy + Math.sin(ang) * rr));
      });
    };
    place(main, R * RING_FRAC[L], 0);
    place(runs, R * (RING_FRAC[L] + 0.06), 0.03);
  }
  return out;
}

// ----------          CIRCLE          ----------

/** Svi čvorovi na jednom krugu (grupisano po oblasti/vrsti), root u centru; veze = tetive. */
export function layoutCircle(nodes: MapsNode[], W: number, H: number, t: number): Pt[] {
  const out: Pt[] = [];
  if (nodes.length === 0) return out;
  const cx = W / 2;
  const cy = H / 2;
  const R = radius(W, H) * 0.92;
  const ring = nodes.filter((n) => n.kind !== "root");
  for (const n of nodes) if (n.kind === "root") out.push(pt(n, cx, cy));
  const groups = groupBy(ring);
  const ordered: MapsNode[] = [];
  for (const arr of groups.values()) {
    const hub = arr.find((n) => n.kind === "area");
    ordered.push(...(hub ? [hub] : []), ...arr.filter((n) => n.kind !== "area"));
  }
  ordered.forEach((n, i) => {
    const ang = -Math.PI / 2 + (i / ordered.length) * 2 * Math.PI + t * 0.01;
    const rr = n.kind === "area" ? R + 14 : R;
    out.push(pt(n, cx + Math.cos(ang) * rr, cy + Math.sin(ang) * rr));
  });
  return out;
}

// ----------          AREAS          ----------

/** Klaster po oblasti (hub + filotaksa oko huba), root u centru; vrste bez oblasti = svoj klaster. */
export function layoutAreas(nodes: MapsNode[], W: number, H: number, t: number): Pt[] {
  const out: Pt[] = [];
  if (nodes.length === 0) return out;
  const cx = W / 2;
  const cy = H / 2;
  const R = radius(W, H);
  for (const n of nodes) if (n.kind === "root") out.push(pt(n, cx, cy));
  const groups = groupBy(nodes.filter((n) => n.kind !== "root"));
  const keys = [...groups.keys()];
  const golden = 2.399963;
  keys.forEach((k, gi) => {
    const items = groups.get(k) ?? [];
    const hub = items.find((n) => n.kind === "area");
    const rest = items.filter((n) => n.kind !== "area");
    const ang = -Math.PI / 2 + (gi / keys.length) * 2 * Math.PI + t * 0.006;
    const dist = R * (keys.length <= 6 ? 0.55 : 0.68);
    const hx = cx + Math.cos(ang) * dist;
    const hy = cy + Math.sin(ang) * dist;
    if (hub) out.push(pt(hub, hx, hy));
    const spread = Math.min(R * 0.24, 7 + 2.4 * Math.sqrt(rest.length) * 3);
    rest.forEach((n, i) => {
      const rr = Math.min(spread, 6 * Math.sqrt(i + 1));
      const a = i * golden;
      out.push(pt(n, hx + Math.cos(a) * rr, hy + Math.sin(a) * rr));
    });
  });
  return out;
}

// ----------          LINKS (force)          ----------

/** Mala force-simulacija: odbijanje (mreža ćelija, O(n)), opruge po vezama, gravitacija ka centru.
 *  Deterministička (seed), fiksan broj iteracija — računa se jednom po grafu, ne po frejmu. */
export function layoutLinks(nodes: MapsNode[], links: MapsLink[], W: number, H: number): Pt[] {
  if (nodes.length === 0) return [];
  const cx = W / 2;
  const cy = H / 2;
  const R = radius(W, H);
  const rnd = mulberry32(7);
  const idx = new Map<string, number>();
  nodes.forEach((n, i) => idx.set(n.id, i));
  const xs = new Float64Array(nodes.length);
  const ys = new Float64Array(nodes.length);
  const vx = new Float64Array(nodes.length);
  const vy = new Float64Array(nodes.length);
  const start = layoutRings(nodes, W, H, 0);
  const startById = new Map(start.map((p) => [p.id, p]));
  nodes.forEach((n, i) => {
    const p = startById.get(n.id);
    xs[i] = (p?.x ?? cx) + (rnd() - 0.5) * 8;
    ys[i] = (p?.y ?? cy) + (rnd() - 0.5) * 8;
  });
  const edges: Array<[number, number]> = [];
  for (const l of links) {
    const a = idx.get(l.source);
    const b = idx.get(l.target);
    if (a !== undefined && b !== undefined && a !== b) edges.push([a, b]);
  }
  const n = nodes.length;
  const ITER = n > 1500 ? 80 : 220;
  const CELL = 70;
  const REP = 3200;
  const grid = new Map<number, number[]>();
  for (let it = 0; it < ITER; it += 1) {
    const cool = 1 - it / ITER;
    grid.clear();
    for (let i = 0; i < n; i += 1) {
      const key = Math.floor(xs[i] / CELL) * 73856 + Math.floor(ys[i] / CELL);
      const cell = grid.get(key);
      if (cell) cell.push(i);
      else grid.set(key, [i]);
    }
    for (let i = 0; i < n; i += 1) {
      const gx = Math.floor(xs[i] / CELL);
      const gy = Math.floor(ys[i] / CELL);
      for (let ox = -1; ox <= 1; ox += 1) {
        for (let oy = -1; oy <= 1; oy += 1) {
          const cell = grid.get((gx + ox) * 73856 + (gy + oy));
          if (!cell) continue;
          for (const j of cell) {
            if (j === i) continue;
            let dx = xs[i] - xs[j];
            let dy = ys[i] - ys[j];
            let d2 = dx * dx + dy * dy;
            if (d2 < 0.01) { dx = rnd() - 0.5; dy = rnd() - 0.5; d2 = 0.5; }
            const f = (REP / d2) * cool;
            const d = Math.sqrt(d2);
            vx[i] += (dx / d) * f;
            vy[i] += (dy / d) * f;
          }
        }
      }
      // gravitacija ka centru (root jače)
      const g = nodes[i].kind === "root" ? 0.12 : 0.004;
      vx[i] += (cx - xs[i]) * g;
      vy[i] += (cy - ys[i]) * g;
    }
    for (const [a, b] of edges) {
      const dx = xs[b] - xs[a];
      const dy = ys[b] - ys[a];
      const d = Math.sqrt(dx * dx + dy * dy) || 1;
      const want = nodes[a].kind === "root" || nodes[b].kind === "root" ? 160 : 40;
      const f = ((d - want) / d) * 0.05;
      vx[a] += dx * f; vy[a] += dy * f;
      vx[b] -= dx * f; vy[b] -= dy * f;
    }
    for (let i = 0; i < n; i += 1) {
      if (nodes[i].kind === "root") { xs[i] = cx; ys[i] = cy; vx[i] = 0; vy[i] = 0; continue; }
      vx[i] *= 0.6; vy[i] *= 0.6;
      xs[i] += Math.max(-12, Math.min(12, vx[i]));
      ys[i] += Math.max(-12, Math.min(12, vy[i]));
      const ddx = xs[i] - cx;
      const ddy = ys[i] - cy;
      const dd = Math.sqrt(ddx * ddx + ddy * ddy);
      if (dd > R) { xs[i] = cx + (ddx / dd) * R; ys[i] = cy + (ddy / dd) * R; }
    }
  }
  return nodes.map((nd, i) => pt(nd, xs[i], ys[i]));
}

// ----------          TIMELINE          ----------

const NO_DATE_FRAC = 0.06; // levi „?" pojas za čvorove bez datuma

/** X = vreme (`changed`), Y = red: gore run-ovi/rutine/app-ovi, dole oblasti (jedan red po oblasti).
 *  Bez datuma → levi „?" pojas. Root levo u sredini, hub oblasti na početku svog reda. */
export function layoutTimeline(nodes: MapsNode[], W: number, H: number): Pt[] {
  const out: Pt[] = [];
  if (nodes.length === 0) return out;
  const left = W * (NO_DATE_FRAC + 0.04);
  const right = W - 32;
  const times = nodes.map((n) => (n.changed ? Date.parse(n.changed) : NaN)).filter((v) => !Number.isNaN(v));
  const tMin = times.length ? Math.min(...times) : 0;
  const tMax = times.length ? Math.max(...times) : 1;
  const span = Math.max(1, tMax - tMin);
  const xOf = (n: MapsNode, i: number): number => {
    const v = n.changed ? Date.parse(n.changed) : NaN;
    if (Number.isNaN(v)) return 16 + ((i * 37) % Math.max(1, Math.floor(W * NO_DATE_FRAC - 24)));
    return left + ((v - tMin) / span) * (right - left);
  };
  // Redovi: gore (run, routine, app, skill), dole oblasti redom pojavljivanja.
  const topRows: MapsKind[] = ["run", "routine", "app", "skill"];
  const areaKeys: string[] = [];
  for (const n of nodes) if (n.kind === "file" && n.area && !areaKeys.includes(n.area)) areaKeys.push(n.area);
  const rows = topRows.length + areaKeys.length;
  const top = 96;
  const rowH = Math.max(18, (H - top - 40) / Math.max(1, rows));
  const yOfRow = (r: number) => top + rowH * (r + 0.5);
  nodes.forEach((n, i) => {
    if (n.kind === "root") { out.push(pt(n, 28, H / 2)); return; }
    if (n.kind === "area") {
      const r = areaKeys.indexOf(n.area ?? "");
      out.push(pt(n, W * NO_DATE_FRAC + 8, yOfRow(topRows.length + Math.max(0, r))));
      return;
    }
    const r = n.kind === "file" ? topRows.length + Math.max(0, areaKeys.indexOf(n.area ?? "")) : topRows.indexOf(n.kind);
    const jitter = ((i * 7919) % 11) - 5;
    out.push(pt(n, xOf(n, i), yOfRow(r) + jitter * 0.8));
  });
  return out;
}

/** Granice vremenske ose (za crtanje oznaka datuma); null kad nema datuma. */
export function timelineRange(nodes: MapsNode[]): { min: number; max: number } | null {
  const times = nodes.map((n) => (n.changed ? Date.parse(n.changed) : NaN)).filter((v) => !Number.isNaN(v));
  if (!times.length) return null;
  return { min: Math.min(...times), max: Math.max(...times) };
}
export const TIMELINE_LEFT_FRAC = NO_DATE_FRAC + 0.04;

// ----------          3D ORBIT          ----------

/** Rings pozicije projektovane 2.5D: rotacija oko vertikalne ose (`t`), nagib, dubina → veličina/alfa. */
export function layoutOrbit(nodes: MapsNode[], W: number, H: number, t: number): Pt[] {
  const base = layoutRings(nodes, W, H, 0);
  const cx = W / 2;
  const cy = H / 2;
  const R = radius(W, H);
  const rot = t * 0.18;
  const TILT = 0.5;
  return base.map((p) => {
    const dx = p.x - cx;
    const dy = p.y - cy;
    const x3 = dx * Math.cos(rot) - dy * Math.sin(rot);
    const z3 = dx * Math.sin(rot) + dy * Math.cos(rot); // dubina (+ = bliže)
    const depth = z3 / R; // -1 … 1
    const scale = 0.72 + 0.28 * (depth + 1) / 2;
    return {
      ...p,
      x: cx + x3 * scale,
      y: cy + (-z3) * TILT * scale, // nagnut disk: dubina daje visinu na ekranu
      z: depth,
      r: p.r * (0.7 + 0.5 * (depth + 1) / 2),
      alpha: 0.35 + 0.65 * (depth + 1) / 2,
    };
  });
}
