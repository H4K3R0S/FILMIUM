import {
  memo,
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type PointerEvent as ReactPointerEvent,
  type WheelEvent as ReactWheelEvent,
} from "react";

import {
  getBrainRegionFile,
  getBrainRegionNodes,
  getBrainRegions,
  getBrainResolve,
  getBrainSearch,
} from "../../services/secondBrainApi";
import type { BrainRegion, BrainRegionNode, BrainSearchHit } from "../../types/secondBrain";

const CX = 500;
const CY = 500;
const CORE_R = 52;
const SEG_IN = 104;
const SEG_OUT = 172;
const SKILL_R = 84; // zvezdice skilova između centra i regiona
const TOOL_R = 440; // heksagoni alata SEDE na spoljnom obruču (linija 440)
const NODE_MAX_R = 418; // podaci NIKAD ne prelaze ovaj radijus (unutar obruča)
const ORBIT_EDGE = 470;

const REGION_COLORS: Record<string, string> = {
  glumci: "#38bdf8", filmovi: "#f472b6", serije: "#a78bfa",
  anime: "#fbbf24", kolekcije: "#34d399",
};
function colorFor(key: string, i: number): string {
  return REGION_COLORS[key] ?? `hsl(${(i * 67) % 360} 72% 62%)`;
}
function polar(r: number, deg: number): [number, number] {
  const a = ((deg - 90) * Math.PI) / 180;
  return [CX + r * Math.cos(a), CY + r * Math.sin(a)];
}
function segPath(rIn: number, rOut: number, a0: number, a1: number): string {
  const [x0o, y0o] = polar(rOut, a0);
  const [x1o, y1o] = polar(rOut, a1);
  const [x0i, y0i] = polar(rIn, a0);
  const [x1i, y1i] = polar(rIn, a1);
  const large = a1 - a0 > 180 ? 1 : 0;
  return `M ${x0o} ${y0o} A ${rOut} ${rOut} 0 ${large} 1 ${x1o} ${y1o} `
    + `L ${x1i} ${y1i} A ${rIn} ${rIn} 0 ${large} 0 ${x0i} ${y0i} Z`;
}
function starPath(cx: number, cy: number, r: number): string {
  const p: string[] = [];
  for (let i = 0; i < 10; i += 1) {
    const rr = i % 2 === 0 ? r : r * 0.45;
    const a = ((i * 36 - 90) * Math.PI) / 180;
    p.push(`${cx + rr * Math.cos(a)} ${cy + rr * Math.sin(a)}`);
  }
  return `M${p.join("L")}Z`;
}
function hexPath(cx: number, cy: number, r: number): string {
  const p: string[] = [];
  for (let i = 0; i < 6; i += 1) {
    const a = ((i * 60) * Math.PI) / 180;
    p.push(`${cx + r * Math.cos(a)} ${cy + r * Math.sin(a)}`);
  }
  return `M${p.join("L")}Z`;
}

function OrbitLabel(props: { x: number; y: number; className: string; fill?: string; dy?: number; spinDelay?: string; children: React.ReactNode }) {
  return (
    <g transform={`translate(${props.x} ${props.y})`}>
      <g className="brain-counterspin" style={props.spinDelay ? { animationDelay: props.spinDelay } : undefined}>
        <text className={props.className} fill={props.fill} x={0} y={props.dy ?? 0}>{props.children}</text>
      </g>
    </g>
  );
}

type Placed = BrainRegionNode & { x: number; y: number; r: number; color: string; dly?: number };
type View = { zoom: number; x: number; y: number };
type Drag = { px: number; py: number; ox: number; oy: number; moved: boolean };
type Props = { domainName: string };

/** Renderuj telo atoma sa klikabilnim [[wikilinkovima]] (za navigaciju kroz veze). */
/** Otvori spoljni/aplikacioni link iz atoma: `…/#/filmium/...` navigira U APLIKACIJI
 *  (hash ruta, npr. stranica filma/glumca), ostalo u novom prozoru. */
function openAtomLink(url: string): void {
  const h = url.indexOf("/#/");
  if (h >= 0) { window.location.hash = url.slice(h + 1); return; }
  if (url.startsWith("#/")) { window.location.hash = url; return; }
  window.open(url, "_blank", "noopener");
}

function renderBody(text: string, onLink: (slug: string) => void): React.ReactNode[] {
  const out: React.ReactNode[] = [];
  // [[wikilink]] / [[slug|labela]]  ILI  markdown [tekst](url)
  const re = /\[\[([^\]|]+)(?:\|([^\]]+))?\]\]|\[([^\]]+)\]\(((?:https?:\/\/|#\/)[^\s)]+)\)/g;
  let last = 0;
  let m: RegExpExecArray | null;
  let i = 0;
  while ((m = re.exec(text)) !== null) {
    if (m.index > last) out.push(text.slice(last, m.index));
    if (m[1] !== undefined) {
      const slug = m[1].trim();
      const label = (m[2] ?? m[1]).trim();
      out.push(
        <button className="brain-wikilink" key={`wl-${i}`} onClick={() => onLink(slug)} type="button">
          {label}
        </button>,
      );
    } else {
      const label = m[3].trim();
      const url = m[4];
      out.push(
        <a className="brain-extlink" href={url} key={`el-${i}`}
          onClick={(e) => { e.preventDefault(); openAtomLink(url); }}>
          {label} ↗
        </a>,
      );
    }
    last = re.lastIndex;
    i += 1;
  }
  if (last < text.length) out.push(text.slice(last));
  return out;
}

/** Posvetli (amt>0) / potamni (amt<0) hex boju — za 3D gradijent balona. */
function shade(hex: string, amt: number): string {
  if (!hex.startsWith("#") || hex.length !== 7) return hex;
  const n = parseInt(hex.slice(1), 16);
  const f = (c: number) => Math.round(amt >= 0 ? c + (255 - c) * amt : c * (1 + amt));
  return `rgb(${f((n >> 16) & 255)},${f((n >> 8) & 255)},${f(n & 255)})`;
}

/** Sloj čvorova — memoizovan: hover NE re-renderuje 600 balona (samo sloj labela). */
const NodesLayer = memo(function NodesLayer(props: {
  placed: Placed[];
  selId: string | null;
  connSet: Set<string>;
  gradKeys: Set<string>;
  onSelect: (n: BrainRegionNode) => void;
  onHover: (n: BrainRegionNode | null) => void;
  moved: () => boolean;
}) {
  const hasSel = props.selId !== null;
  return (
    <g className={`brain-nodes${hasSel ? " has-sel" : ""}`}>
      {props.placed.map((node) => {
        const dim = hasSel && node.id !== props.selId && !props.connSet.has(node.slug);
        return (
          <g className={`brain-node-g${dim ? " is-dim" : ""}`} key={node.id} style={{ animationDelay: `${node.dly ?? 0}ms` }}>
            <circle
              className={`brain-region-node${props.selId === node.id ? " is-sel" : ""}`}
              cx={node.x} cy={node.y}
              fill={props.gradKeys.has(node.region) ? `url(#ng-${node.region})` : node.color}
              onClick={(e) => { e.stopPropagation(); if (!props.moved()) props.onSelect(node); }}
              onMouseEnter={() => props.onHover(node)} onMouseLeave={() => props.onHover(null)}
              r={node.r}
            />
          </g>
        );
      })}
    </g>
  );
});

function SpinningLabels(props: {
  items: Array<{ x: number; y: number; off: number; cls: string; text: string }>;
}) {
  // Uspravne labele (brojevi u balonima + ime pod mišem) — statične, uvek ravne.
  return (
    <g className="brain-spin-labels">
      {props.items.map((it, i) => (
        <text className={it.cls} key={i} x={it.x} y={it.y + it.off}>{it.text}</text>
      ))}
    </g>
  );
}

function BrainRegions({ domainName }: Props) {
  const [regions, setRegions] = useState<BrainRegion[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [tools, setTools] = useState<Array<{ name: string; slug: string }>>([]);
  const [skills, setSkills] = useState<Array<{ name: string; slug: string }>>([]);
  const [q, setQ] = useState("");
  const [hits, setHits] = useState<BrainSearchHit[]>([]);
  const [sizeMul, setSizeMul] = useState(1);
  const [layout, setLayout] = useState<"rings" | "circle" | "hex">("rings");
  const [drill, setDrill] = useState<{ key: string; label: string; nodes: BrainRegionNode[]; total?: number } | null>(null);
  const drillSeq = useRef(0); // prekida progresivno učitavanje kad se region promeni
  const [sel, setSel] = useState<BrainRegionNode | null>(null);
  const [content, setContent] = useState<string | null>(null);
  const [hover, setHover] = useState<BrainRegionNode | null>(null);
  const [hoverDot, setHoverDot] = useState<{ region: string; slug: string } | null>(null); // tačka veze pod mišem (fisheye)
  const dotLeaveTimer = useRef<number | null>(null); // efekat se zadrži ~0.7s posle napuštanja tačke
  const enterDot = useCallback((region: string, slug: string) => {
    if (dotLeaveTimer.current !== null) { window.clearTimeout(dotLeaveTimer.current); dotLeaveTimer.current = null; }
    setHoverDot({ region, slug });
  }, []);
  const leaveDot = useCallback(() => {
    if (dotLeaveTimer.current !== null) window.clearTimeout(dotLeaveTimer.current);
    dotLeaveTimer.current = window.setTimeout(() => { setHoverDot(null); dotLeaveTimer.current = null; }, 700);
  }, []);
  const [view, setView] = useState<View>({ zoom: 1, x: 0, y: 0 });
  const drag = useRef<Drag | null>(null);
  const svgRef = useRef<SVGSVGElement | null>(null);
  // Spoljni obruč je KRUŽAN i FIKSAN (ne prati oblik prozora); skalira se samo uniformno sa platnom.
  const ringRx = TOOL_R;
  const ringRy = TOOL_R;
  const movedFn = useCallback(() => Boolean(drag.current?.moved), []);
  const onHoverNode = useCallback((n: BrainRegionNode | null) => setHover(n), []);
  const spinGroupRef = useRef<SVGGElement | null>(null);

  useEffect(() => {
    let alive = true;
    getBrainRegions(16).then((d) => {
      if (!alive) return;
      setRegions(d.regions);
      setTotal(d.total);
      setTools((d.meta?.tools ?? []).map((t) => ({ name: t.name, slug: t.slug ?? "" })));
      setSkills((d.meta?.skills ?? []).map((sk) => ({ name: sk.name, slug: sk.slug ?? "" })));
    }).finally(() => alive && setLoading(false));
    return () => { alive = false; };
  }, []);

  // Napredni pretraživač (debounce)
  useEffect(() => {
    const needle = q.trim();
    if (needle.length < 2) { setHits([]); return; }
    let alive = true;
    const id = window.setTimeout(() => {
      getBrainSearch(needle, 24).then((r) => { if (alive) setHits(r.results); }).catch(() => { if (alive) setHits([]); });
    }, 180);
    return () => { alive = false; window.clearTimeout(id); };
  }, [q]);

  // ---- region sektori (uglovi) — statični, uvek prisutni ----
  const sectors = useMemo(() => {
    const GAP = 5;
    const n = regions.length;
    const span = n > 0 ? (360 - GAP * n) / n : 360;
    const m = new Map<string, { a0: number; a1: number; mid: number; color: string; i: number }>();
    regions.forEach((reg, i) => {
      const a0 = i * (span + GAP) + GAP / 2;
      const a1 = a0 + span;
      m.set(reg.key, { a0, a1, mid: (a0 + a1) / 2, color: colorFor(reg.key, i), i });
    });
    return { map: m, span, GAP };
  }, [regions]);

  /** Učitaj region PROGRESIVNO: prvih 120 odmah (prikaz), ostatak u pozadini u
   *  delovima; `lite` bez veza (veze se učitaju tek na klik). Pozicije su stabilne
   *  jer se layout računa po UKUPNOM broju, ne po učitanom. */
  async function loadRegion(key: string, label: string, inject?: BrainRegionNode): Promise<void> {
    const token = ++drillSeq.current;
    const total = Math.min(regions.find((r) => r.key === key)?.count ?? 0, 600);
    try {
      const first = await getBrainRegionNodes(key, 0, Math.min(120, Math.max(1, total)), true);
      if (drillSeq.current !== token) return;
      let nodes = first.nodes;
      if (inject && !nodes.some((x) => x.id === inject.id)) nodes = [inject, ...nodes];
      setDrill({ key, label, nodes, total: Math.max(total, nodes.length) });
      let off = first.nodes.length;
      while (off < total) {
        const chunk = await getBrainRegionNodes(key, off, Math.min(240, total - off), true);
        if (drillSeq.current !== token) return;
        if (!chunk.nodes.length) break;
        off += chunk.nodes.length;
        const add = chunk.nodes;
        setDrill((d) => (d && d.key === key
          ? { ...d, nodes: [...d.nodes, ...add.filter((x) => !d.nodes.some((y) => y.id === x.id))] }
          : d));
      }
    } catch { if (inject) setDrill({ key, label, nodes: [inject], total: 1 }); }
  }
  async function openRegion(key: string, label: string): Promise<void> {
    setSel(null); setContent(null);
    await loadRegion(key, label);
  }
  async function selectNode(node: BrainRegionNode): Promise<void> {
    setSel(node); setContent(null);
    try {
      const n = await getBrainResolve(node.slug);
      if (n.found) {
        setSel({ ...node, links: n.links ?? [], link_regions: n.link_regions ?? [] });
        setContent(n.content ?? "(prazan atom)");
      } else {
        const f = await getBrainRegionFile(node.region, node.rel);
        setContent(f.content || "(prazan atom)");
      }
    } catch { setContent("(ne mogu da učitam sadržaj)"); }
  }
  async function navigateToSlug(raw: string): Promise<void> {
    const slug = raw.trim().toLowerCase();
    if (!slug) return;
    if (slug.startsWith("region-")) {
      const key = slug.slice("region-".length);
      const reg = regions.find((r) => r.key === key);
      if (reg) { void openRegion(reg.key, reg.label); return; }
    }
    setContent(null);
    try {
      const n = await getBrainResolve(slug);
      if (!n.found || !n.region || !n.rel) { setContent("(veza ne postoji: " + slug + ")"); return; }
      const node: BrainRegionNode = {
        id: `${n.region}:${n.rel}`, label: n.label ?? slug, score: n.score ?? 0,
        rel: n.rel, region: n.region, slug: n.slug ?? slug,
        links: n.links ?? [], link_regions: n.link_regions ?? [],
        rating: n.rating ?? 0, conn: n.conn ?? 0,
      };
      if (regions.some((r) => r.key === n.region)) {
        void loadRegion(n.region, regions.find((r) => r.key === n.region)?.label ?? n.region, node);
      }
      setSel(node);
      setContent(n.content ?? "(prazan atom)");
    } catch { setContent("(ne mogu da učitam sadržaj)"); }
  }
  function back(): void { setDrill(null); setSel(null); setContent(null); }
  function deselect(): void { setSel(null); setContent(null); }

  // ---- pozicioniranje čvorova (raspored: prstenovi / krug / heks) ----
  const placed: Placed[] = useMemo(() => {
    const out: Placed[] = [];
    const rOf = (n: BrainRegionNode, base: number) => (base + Math.min(1, (n.conn || 0) / 22) * 9) * sizeMul;

    // PRSTENOVI — zadržan izvorni izgled (sektori u pregledu, obruči u drill-u)
    if (layout === "rings") {
      if (drill) {
        const col = sectors.map.get(drill.key)?.color ?? "#38bdf8";
        const sorted = [...drill.nodes].sort((a, b) => b.score - a.score);
        const per = 60;
        const rings = Math.max(1, Math.ceil((drill.total ?? sorted.length) / per));
        const sp = Math.min(24, (NODE_MAX_R - 196) / rings);
        sorted.forEach((n, j) => {
          const ringIdx = Math.floor(j / per);
          const inRing = j % per;
          const nr = 196 + ringIdx * sp + (1 - n.score) * 7;
          const a = (inRing / per) * 360 + ringIdx * 6;
          const [x, y] = polar(nr, a);
          out.push({ ...n, x, y, r: rOf(n, 3.4), color: col, dly: ringIdx * 45 + inRing * 2 });
        });
        return out;
      }
      regions.forEach((reg) => {
        const sec = sectors.map.get(reg.key);
        if (!sec) return;
        reg.nodes.forEach((node, j) => {
          const tt = reg.nodes.length > 1 ? j / (reg.nodes.length - 1) : 0.5;
          const na = sec.a0 + 10 + tt * (sec.a1 - sec.a0 - 20);
          const nr = 220 + (1 - node.score) * 168;
          const [x, y] = polar(nr, na);
          out.push({ ...node, x, y, r: rOf(node, 4.5), color: sec.color, dly: j * 7 });
        });
      });
      return out;
    }

    // KRUG / HEKS — jedinstven raspored svih čvorova, boja po regionu
    const items: Array<[BrainRegionNode, string]> = [];
    if (drill) {
      const col = sectors.map.get(drill.key)?.color ?? "#38bdf8";
      [...drill.nodes].sort((a, b) => b.score - a.score).forEach((n) => items.push([n, col]));
    } else {
      regions.forEach((reg) => {
        const col = sectors.map.get(reg.key)?.color ?? "#38bdf8";
        reg.nodes.forEach((n) => items.push([n, col]));
      });
    }
    const N = drill ? Math.max(drill.total ?? 0, items.length) : items.length;
    if (layout === "circle") {
      const GA = 2.399963229728653; // zlatni ugao (phyllotaxis)
      const k = (NODE_MAX_R - 70) / Math.sqrt(Math.max(1, N - 1));
      items.forEach(([n, col], j) => {
        const rad = 70 + k * Math.sqrt(j);
        const ang = j * GA;
        out.push({ ...n, x: CX + rad * Math.cos(ang), y: CY + rad * Math.sin(ang), r: rOf(n, 3.4), color: col, dly: j * 2.2 });
      });
    } else {
      const cols = Math.max(1, Math.ceil(Math.sqrt(N * 1.15)));
      const rows = Math.ceil(N / Math.max(1, cols));
      const cornerF = Math.hypot((cols - 1) / 2, ((rows - 1) * 0.9) / 2) || 1;
      const sp = Math.min(30, (NODE_MAX_R - 6) / cornerF);
      items.forEach(([n, col], j) => {
        const row = Math.floor(j / cols);
        const c = j % cols;
        const x = CX + (c - (cols - 1) / 2) * sp + (row % 2) * sp * 0.5;
        const y = CY + (row - (rows - 1) / 2) * sp * 0.9;
        out.push({ ...n, x, y, r: rOf(n, 3.4), color: col, dly: row * 22 });
      });
    }
    return out;
  }, [regions, drill, sectors, sizeMul, layout]);

  // Brojevi veza samo na NAJISTAKNUTIJIM čvorovima (da ne zatrpa) — top 15 po vezama.
  const numberedIds = useMemo(() => {
    const top = [...placed].filter((p) => (p.conn || 0) >= 8)
      .sort((a, b) => (b.conn || 0) - (a.conn || 0)).slice(0, 15);
    return new Set(top.map((p) => p.id));
  }, [placed]);

  // ---- veze: pozicioniraj povezane u SEKTORU NJIHOVOG regiona (u boji regiona) ----
  const conn = useMemo(() => {
    if (!sel) return { lines: [] as Array<{ x1: number; y1: number; x2: number; y2: number; c: string }>, dots: [] as Array<{ x: number; y: number; c: string; label: string }> };
    const a = placed.find((p) => p.id === sel.id);
    const ax = a?.x ?? CX;
    const ay = a?.y ?? CY;
    const lr = sel.link_regions ?? [];
    const byRegion = new Map<string, Array<{ slug: string; conn: number }>>();
    for (const { slug, region, conn } of lr) {
      if (!byRegion.has(region)) byRegion.set(region, []);
      byRegion.get(region)!.push({ slug, conn: conn ?? 0 });
    }
    const lines: Array<{ x1: number; y1: number; x2: number; y2: number; c: string }> = [];
    const dots: Array<{ x: number; y: number; c: string; label: string; region: string; near: number; isHover: boolean; conn: number }> = [];
    // Fisheye duž luka: susedi tačke pod mišem se ODBIJAJU (šire), daleki se blago
    // sabiju; transformacija je monotona pa nema preskakanja/preklapanja redosleda.
    const FISH_D = 0.3; // vrlo suptilno razmicanje (po zahtevu)
    const fish = (u: number) => Math.sign(u) * ((FISH_D + 1) * Math.abs(u)) / (FISH_D * Math.abs(u) + 1);
    byRegion.forEach((slugs, region) => {
      const sec = sectors.map.get(region);
      const col = sec?.color ?? "#94a3b8";
      const a0 = sec ? sec.a0 + 8 : 0;
      const a1 = sec ? sec.a1 - 8 : 360;
      const n = slugs.length;
      const hIdx = hoverDot && hoverDot.region === region ? slugs.findIndex((e) => e.slug === hoverDot.slug) : -1;
      const th = hIdx >= 0 && n > 1 ? hIdx / (n - 1) : -1;
      slugs.forEach(({ slug, conn: cc }, i) => {
        let tt = n > 1 ? i / (n - 1) : 0.5;
        let near = 1;
        if (th >= 0) {
          const side = tt >= th ? 1 - th : th;
          const u = side > 0 ? (tt - th) / side : 0;
          tt = th + fish(u) * side;
          near = 1 - Math.min(1, Math.abs(u) * 2.2);
        }
        const ang = a0 + tt * (a1 - a0);
        const [x, y] = polar(300, ang);
        dots.push({ x, y, c: col, label: slug, region, near, isHover: i === hIdx, conn: cc });
        lines.push({ x1: ax, y1: ay, x2: x, y2: y, c: col });
      });
    });
    // tačka pod mišem se crta POSLEDNJA (iznad ostalih)
    dots.sort((p, q) => Number(p.isHover) - Number(q.isHover));
    return { lines, dots };
  }, [sel, placed, sectors, hoverDot]);

  const connSet = useMemo(() => {
    const s = new Set<string>();
    if (sel) { s.add(sel.slug); for (const l of (sel.link_regions ?? [])) s.add(l.slug); }
    return s;
  }, [sel]);

  const gradKeys = useMemo(() => new Set(regions.map((r) => r.key)), [regions]);
  const onSelectNode = useCallback((n: BrainRegionNode) => { void selectNode(n); }, []);

  // „Svesnost" stranice: ako atom nosi `filmium_url`, sidebar nudi dugme koje
  // otvara tu stranicu LIVE u aplikaciji (film/glumac).
  const liveUrl = useMemo(() => {
    if (!content) return null;
    const m = content.match(/^filmium_url:\s*(\S+)/m);
    return m ? m[1] : null;
  }, [content]);

  // Stavke za uspravni sloj labela: brojevi veza (unutar balona) + ime pod mišem
  const labelItems = useMemo(() => {
    const items: Array<{ x: number; y: number; off: number; cls: string; text: string }> = [];
    for (const p of placed) {
      if (numberedIds.has(p.id)) items.push({ x: p.x, y: p.y, off: 0, cls: "brain-node-num", text: String(p.conn) });
    }
    if (hover && !sel) {
      const hp = placed.find((p) => p.id === hover.id);
      if (hp) items.push({ x: hp.x, y: hp.y, off: -(hp.r + 10), cls: "brain-node-hover-label", text: hover.label });
    }
    return items;
  }, [placed, numberedIds, hover, sel]);


  function onWheel(e: ReactWheelEvent<SVGSVGElement>): void {
    e.preventDefault();
    const factor = e.deltaY < 0 ? 1.12 : 1 / 1.12;
    setView((v) => {
      const zoom = Math.min(6, Math.max(0.4, v.zoom * factor));
      const rect = svgRef.current?.getBoundingClientRect();
      if (!rect) return { ...v, zoom };
      const mx = ((e.clientX - rect.left) / rect.width) * 1000;
      const my = ((e.clientY - rect.top) / rect.height) * 1000;
      const k = zoom / v.zoom;
      return { zoom, x: mx - (mx - v.x) * k, y: my - (my - v.y) * k };
    });
  }
  function onPointerDown(e: ReactPointerEvent<SVGSVGElement>): void {
    drag.current = { px: e.clientX, py: e.clientY, ox: view.x, oy: view.y, moved: false };
  }
  function onPointerMove(e: ReactPointerEvent<SVGSVGElement>): void {
    const g = drag.current;
    if (!g) return;
    const rect = svgRef.current?.getBoundingClientRect();
    if (!rect) return;
    const dx = ((e.clientX - g.px) / rect.width) * 1000;
    const dy = ((e.clientY - g.py) / rect.height) * 1000;
    if (Math.abs(dx) + Math.abs(dy) > 3) g.moved = true;
    setView((v) => ({ ...v, x: g.ox + dx, y: g.oy + dy }));
  }
  function onPointerUp(): void { drag.current = null; }
  const moved = (): boolean => Boolean(drag.current?.moved);

  const drillColor = drill ? (sectors.map.get(drill.key)?.color ?? "#38bdf8") : "#38bdf8";

  return (
    <div className="brain-regions">
      {loading && <p className="brain-message">Učitavam regione…</p>}
      <div className="brain-search-panel">
        <input
          aria-label="Pretraga atoma"
          className="brain-search-input"
          onChange={(e) => setQ(e.target.value)}
          placeholder="🔍 Pretraži atome (film, glumac, alat…)"
          value={q}
        />
        {hits.length > 0 && (
          <ul className="brain-search-results">
            {hits.map((h) => (
              <li key={`${h.region}:${h.slug}`}
                onClick={() => { setQ(""); setHits([]); void navigateToSlug(h.slug); }}>
                <span className="brain-search-dot" style={{ background: REGION_COLORS[h.region] ?? "#94a3b8" }} />
                <span className="brain-search-label">{h.label}</span>
                <span className="brain-search-meta">{h.region}{h.conn ? ` · ${h.conn} veza` : ""}</span>
              </li>
            ))}
          </ul>
        )}
      </div>
      <div className="brain-controls">
        <div className="brain-ctl-group">
          {(["rings", "circle", "hex"] as const).map((L) => (
            <button
              className={`brain-ctl-seg${layout === L ? " is-active" : ""}`}
              key={L}
              onClick={() => setLayout(L)}
              type="button"
            >
              {L === "rings" ? "Prstenovi" : L === "circle" ? "Krug" : "Heks"}
            </button>
          ))}
        </div>
        <label className="brain-ctl-size">
          Veličina
          <input max={1.8} min={0.6} onChange={(e) => setSizeMul(Number(e.target.value))} step={0.1} type="range" value={sizeMul} />
        </label>
        {drill && <button className="brain-ctl-btn" onClick={back} type="button">⤴ Skupi</button>}
      </div>
      <svg
        className="brain-regions-svg"
        onPointerDown={onPointerDown} onPointerLeave={onPointerUp}
        onPointerMove={onPointerMove} onPointerUp={onPointerUp}
        onWheel={onWheel} ref={svgRef} viewBox="0 0 1000 1000"
      >
        <rect className="brain-region-bg" height={2520} onClick={() => { if (!moved()) back(); }} width={2520} x={-760} y={-760} />
        <defs>
          <radialGradient cx="50%" cy="50%" id="brainCenterGlow" r="55%">
            <stop offset="0%" stopColor="rgba(104,128,238,0.40)" />
            <stop offset="22%" stopColor="rgba(74,120,220,0.18)" />
            <stop offset="52%" stopColor="rgba(40,80,150,0.06)" />
            <stop offset="100%" stopColor="rgba(0,0,0,0)" />
          </radialGradient>
          {/* Heksagonalna tekstura kao JEDAN pattern (umesto ~2000 putanja) */}
          <pattern height={58.89} id="hexTexPat" patternUnits="userSpaceOnUse" width={102}>
            {([[0, 0], [102, 0], [0, 58.89], [102, 58.89], [51, 29.445]] as Array<[number, number]>).map(([hx, hy], i) => (
              <path d={hexPath(hx, hy, 34)} fill="none" key={`hc-${i}`} stroke="rgba(132,152,214,0.07)" strokeWidth={1} />
            ))}
          </pattern>
          {/* 3D balon: radijalni gradijent po boji regiona (umesto 600 „sjaj" krugova) */}
          {regions.map((reg) => {
            const c = sectors.map.get(reg.key)?.color ?? "#38bdf8";
            return (
              <radialGradient cx="34%" cy="32%" id={`ng-${reg.key}`} key={`ng-${reg.key}`} r="72%">
                <stop offset="0%" stopColor={shade(c, 0.62)} />
                <stop offset="42%" stopColor={c} />
                <stop offset="100%" stopColor={shade(c, -0.32)} />
              </radialGradient>
            );
          })}
        </defs>
        <circle className="brain-center-glow" cx={CX} cy={CY} fill="url(#brainCenterGlow)" pointerEvents="none" r={900} />
        <rect className="brain-hex-tex" fill="url(#hexTexPat)" height={2520} pointerEvents="none" width={2520} x={-760} y={-760} />
        <g transform={`translate(${view.x} ${view.y}) scale(${view.zoom})`}>
          <ellipse className="brain-orbit-disc" cx={CX} cy={CY} onClick={(e) => { e.stopPropagation(); if (!moved()) deselect(); }} rx={ringRx + 40} ry={ringRy + 40} />

          <g className="brain-spin" ref={spinGroupRef}>
            {[300, 372].map((r) => <circle className="brain-orbit-guide" cx={CX} cy={CY} key={r} r={r} />)}
            <ellipse className="brain-orbit-edge" cx={CX} cy={CY} rx={ringRx} ry={ringRy} />

            {/* Skilovi — zvezdice između centra i regiona */}
            {skills.map((sk, i) => {
              const [sx, sy] = polar(SKILL_R, (i / Math.max(1, skills.length)) * 360);
              return (
                <g
                  className="brain-skill is-clickable"
                  key={`sk-${i}`}
                  onClick={(e) => { e.stopPropagation(); if (!moved()) void navigateToSlug(sk.slug); }}
                >
                  <path d={starPath(sx, sy, 6)} />
                  <title>{sk.name}</title>
                </g>
              );
            })}

            {/* Alati — heksagoni sa labelom na spoljnoj orbiti */}
            {tools.map((tool, i) => {
              const rad = (((i / Math.max(1, tools.length)) * 360 - 90) * Math.PI) / 180;
              const tx = CX + ringRx * Math.cos(rad);
              const ty = CY + ringRy * Math.sin(rad);
              const lx = CX + (ringRx + 30) * Math.cos(rad);
              const ly = CY + (ringRy + 30) * Math.sin(rad);
              return (
                <g
                  className="brain-tool is-clickable"
                  key={`tool-${i}`}
                  onClick={(e) => { e.stopPropagation(); if (!moved()) void navigateToSlug(tool.slug); }}
                >
                  <path d={hexPath(tx, ty, 16)} />
                  <text className="brain-tool-glyph" x={tx} y={ty + 4}>⚙</text>
                  <OrbitLabel className="brain-tool-label" dy={4} x={lx} y={ly}>{tool.name}</OrbitLabel>
                  <title>{tool.name}</title>
                </g>
              );
            })}

            {/* Regioni — STATIČNI, uvek prisutni */}
            {regions.map((reg) => {
              const sec = sectors.map.get(reg.key)!;
              const [lx, ly] = polar(148, sec.mid);
              const active = drill?.key === reg.key;
              return (
                <g
                  className={`brain-region-seg${active ? " is-active" : ""}`}
                  key={reg.key}
                  onClick={() => { if (!moved()) void openRegion(reg.key, reg.label); }}
                >
                  <path d={segPath(SEG_IN, SEG_OUT, sec.a0, sec.a1)} fill={sec.color} stroke={sec.color} />
                  <OrbitLabel className="brain-region-label" fill={sec.color} x={lx} y={ly}>{reg.label}</OrbitLabel>
                  <OrbitLabel className="brain-region-count" dy={18} x={lx} y={ly}>{reg.count}</OrbitLabel>
                </g>
              );
            })}

            {/* Linije veza + tačke povezanih (u boji svog regiona) */}
            {conn.lines.map((l, i) => (
              <line className="brain-region-link" key={`ln-${i}`} stroke={l.c} x1={l.x1} x2={l.x2} y1={l.y1} y2={l.y2} />
            ))}

            {/* Čvorovi — memoizovan sloj (hover ne re-renderuje balone) */}
            <NodesLayer
              connSet={connSet} gradKeys={gradKeys} moved={movedFn}
              onHover={onHoverNode} onSelect={onSelectNode}
              placed={placed} selId={sel?.id ?? null}
            />

            {/* Tačke veza IZNAD balončića (da hover pogađa njih, ne filmove ispod) */}
            {conn.dots.map((d) => (
              <g
                className={`brain-conn-dot is-clickable${d.isHover ? " is-hover" : ""}`}
                key={`cd-${d.region}-${d.label}`}
                onClick={(e) => { e.stopPropagation(); if (!moved()) void navigateToSlug(d.label); }}
                onMouseEnter={() => enterDot(d.region, d.label)}
                onMouseLeave={leaveDot}
                style={{ opacity: hoverDot && !d.isHover ? 0.35 + 0.65 * d.near : 1 }}
              >
                {d.conn > 0 && (
                  <text className="brain-conn-num" dominantBaseline="central" textAnchor={d.x >= CX ? "end" : "start"}
                    x={d.x >= CX ? d.x - 9 : d.x + 9} y={d.y}>{d.conn}</text>
                )}
                <circle cx={d.x} cy={d.y} fill={d.c} r={5} stroke="#fff" strokeWidth={1} />
                <text className="brain-conn-label" dominantBaseline="central" textAnchor={d.x >= CX ? "start" : "end"}
                  x={d.x >= CX ? d.x + 9 : d.x - 9} y={d.y}>{d.label}</text>
              </g>
            ))}
            {/* Labele (brojevi + ime pod mišem) su u SpinningLabels sloju (uspravne) */}
          </g>

          <SpinningLabels items={labelItems} />

          <circle className="brain-region-core" cx={CX} cy={CY} onClick={(e) => { e.stopPropagation(); if (!moved()) back(); }} r={CORE_R} />
          <text className="brain-region-core-label" x={CX} y={CY - 3}>{domainName}</text>
          <text className="brain-region-core-sub" x={CX} y={CY + 15}>{drill ? drill.label : `${total} atoma`}</text>
        </g>
      </svg>

      {drill && (
        <div className="brain-region-drillbar">
          <button className="brain-region-back" onClick={back} type="button">← Regioni</button>
          <span className="brain-region-drilltitle" style={{ color: drillColor }}>
            {drill.label} · {drill.nodes.length} od {regions.find((r) => r.key === drill.key)?.count ?? drill.nodes.length}
          </span>
        </div>
      )}
      {sel && (
        <aside className="brain-region-sidebar">
          <header>
            <strong>{sel.label}</strong>
            <button className="brain-sidebar-close" onClick={deselect} type="button">×</button>
            {liveUrl && (
              <button
                className="brain-live-btn"
                onClick={() => openAtomLink(liveUrl)}
                title="Otvori ovu stranicu LIVE u FILMIUM-u"
                type="button"
              >
                ▶ LIVE
              </button>
            )}
          </header>
          <div className="brain-region-sidebar-meta">
            {sel.region} · skor {sel.score}{sel.rating > 0 ? ` · ⭐ ${sel.rating}` : ""} · {sel.conn} veza
          </div>
          <div className="brain-region-sidebar-body">
            {content === null ? "Učitavam…" : renderBody(content, (slug) => void navigateToSlug(slug))}
          </div>
        </aside>
      )}
      {hover && !sel && (
        <div className="brain-region-tip">
          <strong>{hover.label}</strong>
          <span>skor {hover.score}{hover.rating > 0 ? ` · ⭐ ${hover.rating}` : ""} · {hover.conn} veza</span>
        </div>
      )}
    </div>
  );
}

export default BrainRegions;
