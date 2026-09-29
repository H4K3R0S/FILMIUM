import type { BrainNode, BrainNodeKind } from "../../types/secondBrain";

export const RING_RADIUS: Record<BrainNodeKind, number> & {
  file_min: number;
  file_max: number;
  core_mem_min: number;
  core_mem_max: number;
} = {
  core: 0,
  skill: 150,
  page: 150,
  domain: 300,
  file: 460,        // reprezentativni; stварni radius je u [file_min,file_max]
  routine: 640,
  app: 740,
  file_min: 360,
  file_max: 560,
  // Pojas CORE-memorije: izmedju skills-obruča (150) i domen-ikona (300).
  core_mem_min: 196,
  core_mem_max: 276,
};

export interface PositionedNode extends BrainNode { x: number; y: number; ring: number; angle: number; }

const TWO_PI = Math.PI * 2;
const START = -Math.PI / 2;
const DOMAIN_ORDER = ["codium", "filmium", "imperium", "kalima"];

// Memorija je uredan raster lukova unutar sektora domena; SECTOR_GAP je udeo
// praznine izmedju susednih sektora (vidljiv "spacer"), a *_ROW_GAP je razmak
// izmedju koncentricnih lukova unutar polja.
const SECTOR_GAP = 0.2;
const MEM_ROW_GAP = 15;
const CORE_ROW_GAP = 16;

/**
 * Uredan raspored tacaka u luku: `i`-ta od `n` tacaka pada u raster
 * red×kolona (redovi = koncentricni lukovi u [rMin,rMax], kolone = ugao unutar
 * `aSpan` oko `aCenter`). Determinizam dolazi iz stabilnog `i` (sort po id-u).
 */
function arcGrid(
  i: number,
  n: number,
  rMin: number,
  rMax: number,
  aCenter: number,
  aSpan: number,
  rowGap: number,
): { r: number; a: number } {
  const rows = Math.max(1, Math.floor((rMax - rMin) / rowGap) + 1);
  const cols = Math.max(1, Math.ceil(n / rows));
  const row = Math.min(rows - 1, Math.floor(i / cols));
  const col = i % cols;
  const r = rows === 1 ? (rMin + rMax) / 2 : rMin + (row / (rows - 1)) * (rMax - rMin);
  const a = aCenter + ((col + 0.5) / cols - 0.5) * aSpan;
  return { r, a };
}

function polar(r: number, a: number) { return { x: r * Math.cos(a), y: r * Math.sin(a) }; }

export function layoutGraph(nodes: BrainNode[]): PositionedNode[] {
  const domains = nodes.filter((x) => x.kind === "domain");
  const domainAngle = new Map<string, number>();
  // Stabilan ugao po grupi (ne po redosledu u nizu).
  domains.forEach((d) => {
    const i = DOMAIN_ORDER.indexOf(d.group);
    domainAngle.set(d.group, START + ((i < 0 ? 0 : i) / DOMAIN_ORDER.length) * TWO_PI);
  });
  const ring1 = nodes.filter((x) => x.kind === "skill" || x.kind === "page");
  const apps = nodes.filter((x) => x.kind === "app");
  const routines = nodes.filter((x) => x.kind === "routine");

  // Fajlovi (memorija): stabilan poredak po grupi (sort po id-u) da bi raspored
  // po lukovima bio uredan i deterministican, a ne razbacan.
  const filesByGroup = new Map<string, string[]>();
  for (const node of nodes) {
    if (node.kind === "file") {
      const list = filesByGroup.get(node.group) ?? [];
      list.push(node.id);
      filesByGroup.set(node.group, list);
    }
  }
  const fileIndex = new Map<string, { i: number; n: number }>();
  for (const [, ids] of filesByGroup) {
    ids.sort((a, b) => a.localeCompare(b));
    ids.forEach((id, i) => fileIndex.set(id, { i, n: ids.length }));
  }
  const sectorSpan = (TWO_PI / DOMAIN_ORDER.length) * (1 - SECTOR_GAP);

  const even = (list: BrainNode[], id: string, r: number): { x: number; y: number; angle: number; ring: number } => {
    const i = list.findIndex((x) => x.id === id);
    const angle = START + (i / Math.max(1, list.length)) * TWO_PI;
    return { ...polar(r, angle), angle, ring: r };
  };

  return nodes.map((node) => {
    let out: { x: number; y: number; angle: number; ring: number };
    if (node.kind === "core") out = { x: 0, y: 0, angle: 0, ring: 0 };
    else if (node.kind === "skill" || node.kind === "page") out = even(ring1, node.id, RING_RADIUS.skill);
    else if (node.kind === "domain") {
      const a = domainAngle.get(node.group) ?? START;
      out = { ...polar(RING_RADIUS.domain, a), angle: a, ring: RING_RADIUS.domain };
    } else if (node.kind === "app") out = even(apps, node.id, RING_RADIUS.app);
    else if (node.kind === "routine") out = even(routines, node.id, RING_RADIUS.routine);
    else {
      // file: uredan raster u polju memorije.
      const meta = fileIndex.get(node.id) ?? { i: 0, n: 1 };
      if (node.group === "core" || !domainAngle.has(node.group)) {
        // CORE-memorija: pun krug u pojasu izmedju skills i domena.
        const g = arcGrid(
          meta.i, meta.n, RING_RADIUS.core_mem_min, RING_RADIUS.core_mem_max, 0, TWO_PI, CORE_ROW_GAP,
        );
        out = { ...polar(g.r, g.a), angle: g.a, ring: g.r };
      } else {
        // Memorija domena: uredni lukovi unutar sektora te grupe (sa spacerom).
        const aCenter = domainAngle.get(node.group)!;
        const g = arcGrid(
          meta.i, meta.n, RING_RADIUS.file_min, RING_RADIUS.file_max, aCenter, sectorSpan, MEM_ROW_GAP,
        );
        out = { ...polar(g.r, g.a), angle: g.a, ring: g.r };
      }
    }
    return { ...node, ...out };
  });
}

/** LOD: svi ne-file cvorovi + uzorak fajlova (cap ukupno), proporcionalno po grupi. */
export function sampleVisible(nodes: BrainNode[], cap = 200): Set<string> {
  const visible = new Set<string>();
  const filesByGroup = new Map<string, BrainNode[]>();
  for (const node of nodes) {
    if (node.kind === "file") {
      const list = filesByGroup.get(node.group) ?? [];
      list.push(node);
      filesByGroup.set(node.group, list);
    } else {
      visible.add(node.id);
    }
  }
  const totalFiles = [...filesByGroup.values()].reduce((s, l) => s + l.length, 0) || 1;
  // Iterate groups in stable order to ensure determinism and enforce hard cap on visible files
  const groupKeys = Array.from(filesByGroup.keys()).sort();
  let remaining = cap;
  for (const groupKey of groupKeys) {
    if (remaining <= 0) break;
    const list = filesByGroup.get(groupKey)!;
    const sorted = [...list].sort((a, b) => a.id.localeCompare(b.id));
    const quota = Math.min(remaining, Math.max(1, Math.floor((list.length / totalFiles) * cap)));
    for (let i = 0; i < quota && i < sorted.length; i += 1) visible.add(sorted[i].id);
    remaining -= quota;
  }
  return visible;
}
