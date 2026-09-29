import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from "react";

import { renderMarkdown } from "./markdown";
import {
  RING_FRAC, RING_LABELS, TIMELINE_LEFT_FRAC, areaColor, layoutAreas, layoutCircle,
  layoutLinks, layoutOrbit, layoutRings, layoutTimeline, nodeColor, timelineRange, type Pt,
} from "./mapsLayout";
import {
  MAPS_KINDS, MAPS_VIEWS, type MapsGraph, type MapsKind, type MapsNode, type MapsView,
} from "./mapsTypes";
import "../../styles/maps.css";


// ==========          BRAIN MAPS — Canvas mapa Second Brain-a (MAPS stil)          ==========
// Šest pogleda (rings/circle/areas/links/timeline/orbit), čipovi po oblasti i vrsti,
// pan/zoom, hover/klik → sidebar sa sadržajem atoma. Crtanje je Canvas 2D; rAF petlja
// radi SAMO dok je `motion` uključen (inače se crta na promenu stanja).

type Props = {
  graph: MapsGraph;
  title: string;
  subtitle?: string;
  /** Čitanje sadržaja atoma (samo za lokalni sistem; sfere nemaju fajlove ovde). */
  fileFetcher?: (node: MapsNode) => Promise<string>;
  /** Link „↗ u ćeliji" (kad se gleda sfera drugog sistema). */
  externalUrl?: string;
  /** Obod (sfere drugih sistema) — renderuje se unutar mape da ostane i u „full" režimu. */
  children?: ReactNode;
};

type Xf = { k: number; tx: number; ty: number };
const IDENTITY: Xf = { k: 1, tx: 0, ty: 0 };
const KIND_GLYPH: Record<MapsKind, string> = {
  root: "⬡", area: "◉", skill: "◇", file: "○", routine: "◎", app: "⬡", run: "•",
};
const KIND_LABEL: Record<MapsKind, string> = {
  root: "root", area: "area", skill: "skill", file: "file", routine: "routine", app: "app", run: "run",
};

function fmtDate(ms: number): string {
  const d = new Date(ms);
  return `${String(d.getDate()).padStart(2, "0")}.${String(d.getMonth() + 1).padStart(2, "0")}`;
}

function hexPath(ctx: CanvasRenderingContext2D, x: number, y: number, r: number): void {
  ctx.beginPath();
  for (let i = 0; i < 6; i += 1) {
    const a = (i * Math.PI) / 3 + Math.PI / 6;
    const px = x + r * Math.cos(a);
    const py = y + r * Math.sin(a);
    if (i === 0) ctx.moveTo(px, py);
    else ctx.lineTo(px, py);
  }
  ctx.closePath();
}

function diamondPath(ctx: CanvasRenderingContext2D, x: number, y: number, r: number): void {
  ctx.beginPath();
  ctx.moveTo(x, y - r);
  ctx.lineTo(x + r, y);
  ctx.lineTo(x, y + r);
  ctx.lineTo(x - r, y);
  ctx.closePath();
}

function BrainMaps({ graph, title, subtitle, fileFetcher, externalUrl, children }: Props) {
  const [view, setView] = useState<MapsView>("rings");
  const [motion, setMotion] = useState(true);
  const [names, setNames] = useState(false);
  const [full, setFull] = useState(false);
  const [query, setQuery] = useState("");
  const [areaSel, setAreaSel] = useState<string | null>(null);
  const [kinds, setKinds] = useState<Set<MapsKind>>(() => new Set(MAPS_KINDS));
  const [selId, setSelId] = useState<string | null>(null);
  const [hoverId, setHoverId] = useState<string | null>(null);
  const [content, setContent] = useState<string | null>(null);
  const [size, setSize] = useState({ w: 800, h: 600 });
  const [xf, setXf] = useState<Xf>(IDENTITY);

  const wrapRef = useRef<HTMLDivElement | null>(null);
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const ptsRef = useRef<Pt[]>([]);
  const tRef = useRef(0);
  const dragRef = useRef<{ sx: number; sy: number; tx: number; ty: number; moved: boolean } | null>(null);

  // ----------          izvedeni podaci          ----------
  const areaIndex = useMemo(() => new Map(graph.areas.map((a, i) => [a.key, i])), [graph.areas]);
  const areaLabel = useMemo(() => new Map(graph.areas.map((a) => [a.key, a.label])), [graph.areas]);
  const byId = useMemo(() => new Map(graph.nodes.map((n) => [n.id, n])), [graph.nodes]);

  const visible = useMemo(() => graph.nodes.filter((n) => {
    if (n.kind === "root") return true;
    if (areaSel !== null && n.area !== areaSel) return false;
    if (n.kind === "area") return true;
    return kinds.has(n.kind);
  }), [graph.nodes, areaSel, kinds]);

  const visibleLinks = useMemo(() => {
    const ids = new Set(visible.map((n) => n.id));
    return graph.links.filter((l) => ids.has(l.source) && ids.has(l.target));
  }, [graph.links, visible]);

  const adjacency = useMemo(() => {
    const m = new Map<string, Set<string>>();
    for (const l of graph.links) {
      if (!m.has(l.source)) m.set(l.source, new Set());
      if (!m.has(l.target)) m.set(l.target, new Set());
      m.get(l.source)!.add(l.target);
      m.get(l.target)!.add(l.source);
    }
    return m;
  }, [graph.links]);

  // Force-raspored je skup → jednom po (vidljivi čvorovi, veličina), ne po frejmu.
  const forcePts = useMemo(
    () => (view === "links" ? layoutLinks(visible, visibleLinks, size.w, size.h) : []),
    [view, visible, visibleLinks, size.w, size.h],
  );
  const timelinePts = useMemo(
    () => (view === "timeline" ? layoutTimeline(visible, size.w, size.h) : []),
    [view, visible, size.w, size.h],
  );
  const tRange = useMemo(() => (view === "timeline" ? timelineRange(visible) : null), [view, visible]);

  const computePts = useCallback((t: number): Pt[] => {
    switch (view) {
      case "rings": return layoutRings(visible, size.w, size.h, t);
      case "circle": return layoutCircle(visible, size.w, size.h, t);
      case "areas": return layoutAreas(visible, size.w, size.h, t);
      case "links": return forcePts;
      case "timeline": return timelinePts;
      case "orbit": return layoutOrbit(visible, size.w, size.h, t);
      default: return [];
    }
  }, [view, visible, size.w, size.h, forcePts, timelinePts]);

  // ----------          veličina platna          ----------
  useEffect(() => {
    const el = wrapRef.current;
    if (!el) return;
    const ro = new ResizeObserver((entries) => {
      const r = entries[0]?.contentRect;
      if (r && r.width > 0 && r.height > 0) setSize({ w: Math.round(r.width), h: Math.round(r.height) });
    });
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  useEffect(() => { setXf(IDENTITY); }, [view, size.w, size.h, full]);

  // ----------          crtanje          ----------
  const stateRef = useRef({ xf, selId, hoverId, names, view, tRange, areaIndex, byId, adjacency, visibleLinks, size, title });
  stateRef.current = { xf, selId, hoverId, names, view, tRange, areaIndex, byId, adjacency, visibleLinks, size, title };

  const draw = useCallback(() => {
    const canvas = canvasRef.current;
    const ctx = canvas?.getContext("2d");
    if (!canvas || !ctx) return;
    const s = stateRef.current;
    const dpr = window.devicePixelRatio || 1;
    const W = s.size.w;
    const H = s.size.h;
    if (canvas.width !== W * dpr || canvas.height !== H * dpr) {
      canvas.width = W * dpr;
      canvas.height = H * dpr;
    }
    const pts = computePts(tRef.current);
    ptsRef.current = pts;
    const pById = new Map(pts.map((p) => [p.id, p]));
    const k = s.xf.k;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, W, H);
    ctx.setTransform(dpr * k, 0, 0, dpr * k, dpr * s.xf.tx, dpr * s.xf.ty);
    const cx = W / 2;
    const cy = H / 2;
    const R = Math.max(60, Math.min(W, H) / 2 - 44);
    ctx.font = "10px ui-monospace, SFMono-Regular, Menlo, monospace";

    // vodilje prstenova / vremenska osa
    ctx.lineWidth = 1 / k;
    if (s.view === "rings" || s.view === "orbit") {
      for (let L = 1; L <= 4; L += 1) {
        const r = R * RING_FRAC[L];
        ctx.beginPath();
        if (s.view === "orbit") ctx.ellipse(cx, cy, r, r * 0.5, 0, 0, Math.PI * 2);
        else ctx.arc(cx, cy, r, 0, Math.PI * 2);
        ctx.strokeStyle = "rgba(148,163,184,0.16)";
        ctx.stroke();
        ctx.fillStyle = L === 1 ? "#ff9d57" : L === 2 ? "#b57be0" : L === 3 ? "#e3b341" : "#4f9df0";
        ctx.textAlign = "center";
        ctx.fillText(RING_LABELS[L - 1], cx, cy - (s.view === "orbit" ? r * 0.5 : r) - 5);
      }
    } else if (s.view === "timeline") {
      const left = W * TIMELINE_LEFT_FRAC;
      ctx.strokeStyle = "rgba(148,163,184,0.25)";
      ctx.beginPath(); ctx.moveTo(left, 78); ctx.lineTo(W - 32, 78); ctx.stroke();
      ctx.beginPath(); ctx.moveTo(W * (TIMELINE_LEFT_FRAC - 0.04), 60); ctx.lineTo(W * (TIMELINE_LEFT_FRAC - 0.04), H - 20); ctx.stroke();
      ctx.fillStyle = "rgba(148,163,184,0.6)";
      ctx.textAlign = "center";
      ctx.fillText("?", W * (TIMELINE_LEFT_FRAC - 0.04) / 2, 74);
      if (s.tRange) {
        const n = 6;
        for (let i = 0; i <= n; i += 1) {
          const x = left + ((W - 32 - left) * i) / n;
          const ms = s.tRange.min + ((s.tRange.max - s.tRange.min) * i) / n;
          ctx.fillText(fmtDate(ms), x, 70);
          ctx.beginPath(); ctx.moveTo(x, 74); ctx.lineTo(x, 82); ctx.stroke();
        }
      }
      ctx.textAlign = "left";
      ctx.fillStyle = "rgba(148,163,184,0.45)";
      ["RUNS", "ROUTINES", "APPS", "SKILLS"].forEach((lbl, i) => {
        const rows = 4 + s.areaIndex.size;
        const rowH = Math.max(18, (H - 96 - 40) / rows);
        ctx.fillText(lbl, 6, 96 + rowH * (i + 0.5) + 3);
      });
    }

    // veze
    const sel = s.selId;
    const adj = sel ? s.adjacency.get(sel) ?? new Set<string>() : null;
    for (const l of s.visibleLinks) {
      const a = pById.get(l.source);
      const b = pById.get(l.target);
      if (!a || !b) continue;
      const touches = sel !== null && (l.source === sel || l.target === sel);
      const na = s.byId.get(l.source);
      const color = na ? nodeColor(na, s.areaIndex) : "#94a3b8";
      ctx.strokeStyle = touches ? color : "rgba(148,163,184,1)";
      ctx.globalAlpha = touches ? 0.9 : sel ? 0.035 : (na?.kind === "run" || s.byId.get(l.target)?.kind === "run" ? 0.05 : 0.11);
      ctx.lineWidth = (touches ? 1.4 : 0.7) / k;
      ctx.beginPath();
      ctx.moveTo(a.x, a.y);
      if (s.view === "circle" && na?.kind !== "root") ctx.quadraticCurveTo(cx, cy, b.x, b.y);
      else ctx.lineTo(b.x, b.y);
      ctx.stroke();
    }
    ctx.globalAlpha = 1;

    // čvorovi (orbit: po dubini)
    const ordered = s.view === "orbit" ? [...pts].sort((p, q) => p.z - q.z) : pts;
    for (const p of ordered) {
      const n = s.byId.get(p.id);
      if (!n) continue;
      const color = nodeColor(n, s.areaIndex);
      const isSel = p.id === sel;
      const isHover = p.id === s.hoverId;
      const dim = sel !== null && !isSel && !(adj?.has(p.id));
      const smallArea = n.kind === "area" && (graph.areas[s.areaIndex.get(n.area ?? "") ?? -1]?.count ?? 0) < 3;
      ctx.globalAlpha = p.alpha * (dim ? 0.14 : 1);
      if (isSel || isHover) {
        ctx.beginPath(); ctx.arc(p.x, p.y, p.r + 6, 0, Math.PI * 2);
        ctx.fillStyle = color; ctx.globalAlpha *= 0.25; ctx.fill();
        ctx.globalAlpha = p.alpha * (dim ? 0.14 : 1);
      }
      ctx.fillStyle = color;
      ctx.strokeStyle = color;
      ctx.lineWidth = 1.2 / Math.sqrt(k);
      switch (n.kind) {
        case "root":
          hexPath(ctx, p.x, p.y, p.r); ctx.fillStyle = "rgba(255,157,87,0.12)"; ctx.fill();
          ctx.lineWidth = 2; ctx.stroke();
          hexPath(ctx, p.x, p.y, p.r * 0.45); ctx.fillStyle = color; ctx.fill();
          break;
        case "area":
          if (smallArea) { ctx.beginPath(); ctx.arc(p.x, p.y, 3.5, 0, Math.PI * 2); ctx.fill(); break; }
          ctx.beginPath(); ctx.arc(p.x, p.y, p.r, 0, Math.PI * 2);
          ctx.fillStyle = "rgba(8,14,26,0.9)"; ctx.fill(); ctx.lineWidth = 2; ctx.stroke();
          ctx.beginPath(); ctx.arc(p.x, p.y, p.r * 0.45, 0, Math.PI * 2); ctx.fillStyle = color; ctx.fill();
          break;
        case "skill":
          diamondPath(ctx, p.x, p.y, p.r); ctx.fill();
          break;
        case "routine":
          ctx.beginPath(); ctx.arc(p.x, p.y, p.r, 0, Math.PI * 2); ctx.stroke();
          ctx.beginPath(); ctx.arc(p.x, p.y, p.r * 0.35, 0, Math.PI * 2); ctx.fill();
          break;
        case "app":
          hexPath(ctx, p.x, p.y, p.r); ctx.fillStyle = "rgba(79,157,240,0.15)"; ctx.fill(); ctx.stroke();
          break;
        default:
          ctx.beginPath(); ctx.arc(p.x, p.y, p.r, 0, Math.PI * 2); ctx.fill();
          if (n.status === "fail") { ctx.strokeStyle = "#f87171"; ctx.stroke(); }
      }
      // oznake
      const showLabel = n.kind === "root" || (n.kind === "area" && !smallArea) || isSel || isHover
        || (s.names && k >= 0.7 && n.kind !== "run");
      if (showLabel) {
        ctx.fillStyle = isSel || isHover ? "#f8fafc" : n.kind === "root" ? "#ffd7b8" : n.kind === "area" ? color : "rgba(226,232,240,0.78)";
        ctx.font = n.kind === "root" ? "bold 11px ui-monospace, monospace" : n.kind === "area" ? "bold 9.5px ui-monospace, monospace" : `${isSel || isHover ? 10.5 : 8.5}px ui-monospace, monospace`;
        ctx.textAlign = n.kind === "root" ? "center" : "left";
        const text = n.kind === "area" ? n.label.toUpperCase() : n.label;
        const lx = n.kind === "root" ? p.x : p.x + p.r + 4;
        const ly = n.kind === "root" ? p.y + p.r + 14 : p.y + 3.5;
        ctx.fillText(text.length > 42 ? `${text.slice(0, 40)}…` : text, lx, ly);
        if (n.kind === "area") {
          ctx.fillStyle = "rgba(226,232,240,0.5)";
          ctx.font = "8.5px ui-monospace, monospace";
          ctx.fillText(String(graph.areas[s.areaIndex.get(n.area ?? "") ?? 0]?.count ?? ""), lx, ly + 11);
        }
      }
    }
    ctx.globalAlpha = 1;
  }, [computePts, graph.areas]);

  // rAF samo dok je motion; inače crtanje na promenu stanja.
  useEffect(() => {
    if (!motion || view === "links" || view === "timeline") { draw(); return; }
    let raf = 0;
    let last = performance.now();
    const loop = (now: number) => {
      tRef.current += (now - last) / 1000;
      last = now;
      draw();
      raf = requestAnimationFrame(loop);
    };
    raf = requestAnimationFrame(loop);
    return () => cancelAnimationFrame(raf);
  }, [motion, view, draw]);

  useEffect(() => { draw(); }, [draw, xf, selId, hoverId, names, size, full]);

  // ----------          interakcija          ----------
  const hit = useCallback((sx: number, sy: number): Pt | null => {
    const { k, tx, ty } = stateRef.current.xf;
    const wx = (sx - tx) / k;
    const wy = (sy - ty) / k;
    let best: Pt | null = null;
    let bd = Infinity;
    for (const p of ptsRef.current) {
      const d = Math.hypot(p.x - wx, p.y - wy);
      const thr = p.r + 5 / k;
      if (d < thr && d < bd) { bd = d; best = p; }
    }
    return best;
  }, []);

  const local = (e: React.PointerEvent | React.WheelEvent): [number, number] => {
    const r = (e.currentTarget as HTMLElement).getBoundingClientRect();
    return [e.clientX - r.left, e.clientY - r.top];
  };

  function onPointerDown(e: React.PointerEvent<HTMLCanvasElement>): void {
    const [x, y] = local(e);
    dragRef.current = { sx: x, sy: y, tx: xf.tx, ty: xf.ty, moved: false };
    (e.currentTarget as HTMLElement).setPointerCapture(e.pointerId);
  }
  function onPointerMove(e: React.PointerEvent<HTMLCanvasElement>): void {
    const [x, y] = local(e);
    const d = dragRef.current;
    if (d) {
      if (!d.moved && Math.hypot(x - d.sx, y - d.sy) < 4) return;
      d.moved = true;
      setXf({ k: xf.k, tx: d.tx + (x - d.sx), ty: d.ty + (y - d.sy) });
      return;
    }
    const p = hit(x, y);
    setHoverId(p ? p.id : null);
  }
  function onPointerUp(e: React.PointerEvent<HTMLCanvasElement>): void {
    const d = dragRef.current;
    dragRef.current = null;
    if (d?.moved) return;
    const [x, y] = local(e);
    const p = hit(x, y);
    setSelId(p ? (p.id === selId ? null : p.id) : null);
  }
  function onWheel(e: React.WheelEvent<HTMLCanvasElement>): void {
    const [x, y] = local(e);
    const nk = Math.min(6, Math.max(0.3, xf.k * Math.exp(-e.deltaY * 0.0012)));
    const wx = (x - xf.tx) / xf.k;
    const wy = (y - xf.ty) / xf.k;
    setXf({ k: nk, tx: x - wx * nk, ty: y - wy * nk });
  }

  function runSearch(e: React.FormEvent): void {
    e.preventDefault();
    const needle = query.trim().toLowerCase();
    if (!needle) return;
    const m = visible.find((n) => n.label.toLowerCase().includes(needle) || (n.path ?? "").toLowerCase().includes(needle))
      ?? graph.nodes.find((n) => n.label.toLowerCase().includes(needle));
    if (m) setSelId(m.id);
  }

  function toggleKind(kd: MapsKind): void {
    setKinds((prev) => {
      const next = new Set(prev);
      if (next.has(kd)) next.delete(kd); else next.add(kd);
      return next;
    });
  }

  // ----------          sidebar (sadržaj atoma)          ----------
  const selNode = selId ? byId.get(selId) ?? null : null;
  useEffect(() => {
    setContent(null);
    if (!selNode || !fileFetcher || !selNode.path || (selNode.kind !== "file" && selNode.kind !== "skill")) return;
    let alive = true;
    fileFetcher(selNode).then((txt) => { if (alive) setContent(txt); }).catch(() => { if (alive) setContent("(sadržaj nije dostupan)"); });
    return () => { alive = false; };
  }, [selNode, fileFetcher]);

  const hoverNode = hoverId ? byId.get(hoverId) ?? null : null;
  const canFetch = Boolean(fileFetcher && selNode?.path && (selNode.kind === "file" || selNode.kind === "skill"));

  return (
    <div className={`maps-root${full ? " is-full" : ""}${selNode ? " has-sidebar" : ""}`}>
      <div className="maps-toolbar">
        <div className="maps-title">
          <span className="maps-title-hex">⬡</span>
          <strong>{title}</strong>
          <span className="maps-title-sub">{subtitle ?? "Second Brain"}</span>
        </div>
        <div className="maps-views" role="tablist">
          <span className="maps-views-label">VIEW</span>
          {MAPS_VIEWS.map((v) => (
            <button className={view === v.id ? "is-active" : ""} key={v.id} onClick={() => setView(v.id)} type="button">{v.label}</button>
          ))}
        </div>
        <div className="maps-stats">
          {graph.stats.files} files · {graph.stats.links} links · {graph.stats.runs} runs
          {externalUrl && <a className="maps-ext" href={externalUrl} rel="noopener" target="_blank" title="Otvori Second Brain u ćeliji">↗ u ćeliji</a>}
        </div>
      </div>
      <div className="maps-tools">
        <button className={`maps-btn${motion ? " is-on" : ""}`} onClick={() => setMotion((v) => !v)} type="button">motion</button>
        <form className="maps-search" onSubmit={runSearch}>
          <span>⌕</span>
          <input aria-label="Pretraga mape" onChange={(e) => setQuery(e.target.value)} placeholder="search" value={query} />
        </form>
        <button className="maps-btn" onClick={() => setXf(IDENTITY)} type="button">⛶ fit</button>
        <button className={`maps-btn${full ? " is-on" : ""}`} onClick={() => setFull((v) => !v)} type="button">⤢ full</button>
        <button className={`maps-btn${names ? " is-on" : ""}`} onClick={() => setNames((v) => !v)} type="button">names</button>
        <div className="maps-chips maps-chips--kinds">
          {MAPS_KINDS.map((kd) => (
            <button className={`maps-chip maps-chip--kind${kinds.has(kd) ? " is-active" : ""}`} key={kd} onClick={() => toggleKind(kd)} type="button">
              <span>{KIND_GLYPH[kd]}</span> {KIND_LABEL[kd]}
            </button>
          ))}
        </div>
      </div>
      <div className="maps-chips">
        <button className={`maps-chip${areaSel === null ? " is-active" : ""}`} onClick={() => setAreaSel(null)} type="button">
          <i style={{ background: "#e2e8f0" }} /> all areas
        </button>
        {graph.areas.map((a, i) => (
          <button className={`maps-chip${areaSel === a.key ? " is-active" : ""}`} key={a.key}
            onClick={() => setAreaSel(areaSel === a.key ? null : a.key)} style={{ borderColor: areaColor(i) }} type="button">
            <i style={{ background: areaColor(i) }} /> {a.label.toLowerCase()} <b>{a.count}</b>
          </button>
        ))}
      </div>
      <div className="maps-stage" ref={wrapRef}>
        <canvas
          className="maps-canvas"
          onPointerDown={onPointerDown}
          onPointerLeave={() => { setHoverId(null); dragRef.current = null; }}
          onPointerMove={onPointerMove}
          onPointerUp={onPointerUp}
          onWheel={onWheel}
          ref={canvasRef}
          style={{ width: size.w, height: size.h }}
        />
      </div>

      {hoverNode && !selNode && (
        <div className="maps-tip">
          <strong>{hoverNode.label}</strong>
          <span>{KIND_LABEL[hoverNode.kind]}{hoverNode.area ? ` · ${areaLabel.get(hoverNode.area) ?? hoverNode.area}` : ""} · {hoverNode.links} veza{hoverNode.changed ? ` · ${hoverNode.changed.slice(0, 10)}` : ""}</span>
        </div>
      )}

      {selNode && (
        <aside className="brain-region-sidebar maps-sidebar">
          <header>
            <strong>{selNode.label}</strong>
            <button className="brain-sidebar-close" onClick={() => setSelId(null)} type="button">×</button>
          </header>
          <div className="brain-region-sidebar-meta">
            {KIND_GLYPH[selNode.kind]} {KIND_LABEL[selNode.kind]}
            {selNode.area ? ` · ${areaLabel.get(selNode.area) ?? selNode.area}` : ""}
            {` · ${selNode.links} veza`}
            {selNode.changed ? ` · ${selNode.changed.slice(0, 16).replace("T", " ")}` : ""}
            {selNode.path ? <div className="maps-path">{selNode.path}</div> : null}
          </div>
          <div className="brain-region-sidebar-body">
            {canFetch
              ? (content === null ? "Učitavam…" : renderMarkdown(content))
              : (selNode.note || (adjacency.get(selNode.id)?.size
                ? `Veze: ${[...adjacency.get(selNode.id)!].slice(0, 40).map((id) => byId.get(id)?.label ?? id).join(" · ")}`
                : "(bez dodatnih podataka)"))}
          </div>
        </aside>
      )}

      {children}
    </div>
  );
}

export default BrainMaps;
