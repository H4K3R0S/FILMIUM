import { createElement, useEffect, useMemo, useRef, useState } from "react";

import type { BrainIndex } from "./graph";
import { neighborIds } from "./graph";
import type { PositionedNode } from "./layout";
import { RING_RADIUS } from "./layout";
import { hexPoints, iconFor, nodeColor, starPoints } from "./brainColors";
import type { BrainNodeKind } from "../../types/secondBrain";

type BrainCanvasProps = {
  positioned: PositionedNode[];
  index: BrainIndex;
  visibleIds: Set<string>;
  focusId: string | null;
  onSelect: (id: string | null) => void;
  /** Prstenovi-vodiči (radijusi); default CORE. Ćelija prosleđuje svoje. */
  ringGuides?: number[];
  /** Labele obruča; default CORE. Ćelija prosleđuje Skills/Memory/Alati. */
  ringLabels?: Array<{ label: string; r: number }>;
};

const VIEW = 1500; // logicki kvadrat: bazni scale mapira ga na manju dimenziju
const MIN_ZOOM = 0.4;
const MAX_ZOOM = 3.2;
const DRAG_THRESHOLD = 3; // px pre nego sto pokret postane pan (a ne klik)
const TWO_PI = Math.PI * 2;

// Radijalni opseg "spacer" linija koje razdvajaju sektore memorije po domenu.
const MEM_DIV_INNER = RING_RADIUS.file_min - 24;
const MEM_DIV_OUTER = RING_RADIUS.file_max + 16;

// Hex-grid pozadina: pravilan šestougaoni mozaik (pointy-top), tri kopije po
// pattern-tile-u da bi se sastavljao bez preklapanja/rupa.
const HEX_R = 22;
const HEX_W = Math.sqrt(3) * HEX_R;
const HEX_H = HEX_R * 2;
const HEX_TILE_H = HEX_H * 0.75;

// Obruci-vodici (slabi krugovi) + labele na svojim radijusima.
const RING_GUIDES = [
  RING_RADIUS.skill,
  RING_RADIUS.domain,
  RING_RADIUS.file_max,
  RING_RADIUS.routine,
  RING_RADIUS.app,
];
const RING_LABELS: Array<{ label: string; r: number }> = [
  { label: "SKILLS", r: RING_RADIUS.skill },
  { label: "MEMORY", r: (RING_RADIUS.file_min + RING_RADIUS.file_max) / 2 },
  { label: "ROUTINES", r: RING_RADIUS.routine },
  { label: "APPLICATIONS", r: RING_RADIUS.app },
];

function sizeFor(kind: BrainNodeKind): number {
  switch (kind) {
    case "core":
    case "cell": // ćelija: domen u centru
      return 48;
    case "domain":
      return 30;
    case "area": // ćelija: hub obruča (Skills/Memory/Alati)
      return 26;
    case "app":
      return 22;
    case "skill":
    case "page":
    case "tool": // ćelija: alat domena
      return 20;
    case "routine":
      return 10;
    default:
      return 5; // file
  }
}

// Deterministicki fazni pomak (0..1) za "treperenje" memorijskih tacaka — da
// polje bude živo bez pomeranja centara cvorova (linije ostaju prikacene).
function twinkleDelay(node: PositionedNode): string {
  const h = Math.abs(Math.round(node.x * 13.1 + node.y * 7.7));
  return `-${(h % 500) / 100}s`;
}

type View = { zoom: number; x: number; y: number };
type Gesture = { startX: number; startY: number; lastX: number; lastY: number; moved: boolean };

/** SVG render koncentricnih obruca + cvorova + konekcionih linija. */
function BrainCanvas({
  positioned,
  index,
  visibleIds,
  focusId,
  onSelect,
  ringGuides = RING_GUIDES,
  ringLabels = RING_LABELS,
}: BrainCanvasProps) {
  const svgRef = useRef<SVGSVGElement | null>(null);
  const [size, setSize] = useState({ w: 1200, h: 800 });
  const [view, setView] = useState<View>({ zoom: 1, x: 0, y: 0 });
  const gesture = useRef<Gesture | null>(null);
  // Da klik posle prevlacenja ne deselektuje.
  const draggedRef = useRef(false);

  const byId = useMemo(() => new Map(positioned.map((n) => [n.id, n])), [positioned]);
  const visibleNodes = useMemo(
    () => positioned.filter((n) => visibleIds.has(n.id)),
    [positioned, visibleIds],
  );
  const structuralLines = useMemo(
    () =>
      index.edges.filter(
        (e) => e.kind === "contains" && visibleIds.has(e.source) && visibleIds.has(e.target),
      ),
    [index, visibleIds],
  );
  const focusNode = focusId ? byId.get(focusId) ?? null : null;
  const focusNeighborIds = useMemo(
    () => (focusId ? neighborIds(index, focusId) : new Set<string>()),
    [index, focusId],
  );
  const focusNeighborsVisible = useMemo(
    () => [...focusNeighborIds].filter((id) => visibleIds.has(id)),
    [focusNeighborIds, visibleIds],
  );

  // "Spacer" linije izmedju sektora memorije: na sredini izmedju uglova
  // susednih vidljivih domena (radi za bilo koji broj domena, sa wrap-om).
  const memoryDividers = useMemo(() => {
    const angles = visibleNodes
      .filter((n) => n.kind === "domain")
      .map((n) => n.angle)
      .sort((a, b) => a - b);
    if (angles.length < 2) {
      return [];
    }
    const mids: number[] = [];
    for (let i = 0; i < angles.length; i += 1) {
      const a = angles[i];
      const b = i + 1 < angles.length ? angles[i + 1] : angles[0] + TWO_PI;
      mids.push((a + b) / 2);
    }
    return mids;
  }, [visibleNodes]);

  // ---- Enter animacija: cvor koji se tek montira nosi "brain-node-enter"
  // (opacity 0, scale manji); posle burst-a se ta klasa skida (cvor je u
  // `enteredIds`), sto pokrece CSS tranziciju (second-brain.css) ka punom
  // stanju.
  //
  // StrictMode-bezbedno: NE oslanjamo se na perzistentni "vec zakazano" ref
  // koji simulirani StrictMode cleanup moze da ostavi siroceta (setup ->
  // cleanup -> setup: cleanup otkaze tajmer, a drugi setup vidi da su svi
  // id-jevi "vec zakazani" pa ne zakazuje zamenu — cvorovi ostaju zauvek u
  // "enter" stanju). Umesto toga: na svaku promenu `visibleNodes` zakazujemo
  // (dupli rAF — jedan frame da se enter-klasa zaista upise u DOM, drugi da
  // browser ima priliku da je "vidi" pre skidanja, inace CSS tranzicija ne
  // bi okinula) MERGE trenutno vidljivih id-jeva u `enteredIds` (Set). Merge
  // je idempotentan — dodavanje id-ja koji je vec unutra je no-op — pa dvo-
  // struko pokretanje efekta (StrictMode) ili otkazan pa ponovo zakazan rAF
  // ne moze da ostavi cvor trajno skriven. Cleanup samo otkazuje pending rAF
  // handle; nema "fresh.length === 0 -> return" granu koja bi presekla
  // ponovni pokusaj.
  const [enteredIds, setEnteredIds] = useState<Set<string>>(new Set());
  useEffect(() => {
    const ids = visibleNodes.map((n) => n.id);
    let raf2 = 0;
    const raf1 = window.requestAnimationFrame(() => {
      raf2 = window.requestAnimationFrame(() => {
        setEnteredIds((prev) => {
          const next = new Set(prev);
          for (const id of ids) {
            next.add(id);
          }
          return next;
        });
      });
    });
    return () => {
      window.cancelAnimationFrame(raf1);
      if (raf2) {
        window.cancelAnimationFrame(raf2);
      }
    };
  }, [visibleNodes]);

  // Bazni scale: 1500 logickih jedinica na manju dimenziju vidljivog polja.
  const baseScale = Math.min(size.w, size.h) / VIEW || 1;
  const cx = size.w / 2;
  const cy = size.h / 2;
  const scale = baseScale * view.zoom;

  // Prati velicinu elementa (mapa puni ceo prostor).
  useEffect(() => {
    const el = svgRef.current;
    if (!el) {
      return;
    }
    const measure = () => {
      const rect = el.getBoundingClientRect();
      if (rect.width && rect.height) {
        setSize({ w: rect.width, h: rect.height });
      }
    };
    measure();
    if (typeof ResizeObserver !== "undefined") {
      const ro = new ResizeObserver(measure);
      ro.observe(el);
      return () => ro.disconnect();
    }
    window.addEventListener("resize", measure);
    return () => window.removeEventListener("resize", measure);
  }, []);

  // Zoom ka kursoru. React `onWheel` je passive (preventDefault ne radi i
  // stranica bi skrolovala uporedo), pa vezujemo native non-passive listener.
  useEffect(() => {
    const el = svgRef.current;
    if (!el) {
      return;
    }
    const onWheel = (event: WheelEvent) => {
      event.preventDefault();
      const rect = el.getBoundingClientRect();
      const lx = event.clientX - rect.left;
      const ly = event.clientY - rect.top;
      setView((v) => {
        const factor = event.deltaY > 0 ? 0.9 : 1.1;
        const nextZoom = Math.min(MAX_ZOOM, Math.max(MIN_ZOOM, v.zoom * factor));
        if (nextZoom === v.zoom) {
          return v;
        }
        const cxNow = rect.width / 2;
        const cyNow = rect.height / 2;
        const sNow = (Math.min(rect.width, rect.height) / VIEW || 1) * v.zoom;
        const sNext = (Math.min(rect.width, rect.height) / VIEW || 1) * nextZoom;
        // Svetska tacka pod kursorom ostaje pod kursorom posle zooma.
        const wx = (lx - cxNow - v.x) / sNow;
        const wy = (ly - cyNow - v.y) / sNow;
        return { zoom: nextZoom, x: lx - cxNow - wx * sNext, y: ly - cyNow - wy * sNext };
      });
    };
    el.addEventListener("wheel", onWheel, { passive: false });
    return () => el.removeEventListener("wheel", onWheel);
  }, []);

  function onPointerDown(event: React.PointerEvent): void {
    if (event.button !== 0) {
      return;
    }
    draggedRef.current = false;
    gesture.current = {
      startX: event.clientX,
      startY: event.clientY,
      lastX: event.clientX,
      lastY: event.clientY,
      moved: false,
    };
  }

  function onPointerMove(event: React.PointerEvent): void {
    const g = gesture.current;
    if (!g) {
      return;
    }
    const dx = event.clientX - g.lastX;
    const dy = event.clientY - g.lastY;
    g.lastX = event.clientX;
    g.lastY = event.clientY;
    if (
      !g.moved &&
      (Math.abs(event.clientX - g.startX) > DRAG_THRESHOLD ||
        Math.abs(event.clientY - g.startY) > DRAG_THRESHOLD)
    ) {
      g.moved = true;
      draggedRef.current = true;
    }
    if (g.moved) {
      // Pan je u px ekrana (transform vec skalira sadrzaj).
      setView((v) => ({ ...v, x: v.x + dx, y: v.y + dy }));
    }
  }

  function endDrag(): void {
    gesture.current = null;
  }

  // Klik u prazno deselektuje — osim ako je gest zapravo bio prevlacenje.
  function onBackgroundClick(): void {
    if (draggedRef.current) {
      draggedRef.current = false;
      return;
    }
    onSelect(null);
  }

  function renderShape(node: PositionedNode, sizePx: number, color: string) {
    switch (node.kind) {
      case "cell":
        // Ćelija: domen u centru — kao CORE jezgro (kutija + ime).
        return (
          <>
            <circle className="brain-core-glow" r={sizePx + 40} fill="url(#brain-core-glow)" />
            <rect
              x={-sizePx}
              y={-sizePx}
              width={sizePx * 2}
              height={sizePx * 2}
              rx={16}
              fill="#1b1622"
              stroke={color}
            />
            <g transform={`translate(${-sizePx * 0.5} ${-sizePx * 0.5})`}>
              {createElement(iconFor(node.icon), { size: sizePx })}
            </g>
            <text className="brain-node-label" y={sizePx + 20} textAnchor="middle">
              {node.label}
            </text>
          </>
        );
      case "area":
        // Ćelija: hub obruča (Skills/Memory/Alati) — krug sa labelom.
        return (
          <>
            <circle className="brain-domain-halo" r={sizePx} fill="none" stroke={color} />
            <circle r={sizePx} fill="#181622" stroke={color} />
            <g transform={`translate(${-sizePx / 2} ${-sizePx / 2})`}>
              {createElement(iconFor(node.icon), { size: sizePx })}
            </g>
            <text className="brain-node-label" y={sizePx + 16} textAnchor="middle">
              {node.label}
            </text>
          </>
        );
      case "tool":
        // Ćelija: alat domena — šestougao sa vidljivom labelom.
        return (
          <>
            <polygon points={hexPoints(sizePx)} fill="#181622" stroke={color} />
            <g transform={`translate(${-sizePx * 0.45} ${-sizePx * 0.45})`}>
              {createElement(iconFor(node.icon), { size: sizePx * 0.9 })}
            </g>
            <text className="brain-node-label" y={sizePx + 14} textAnchor="middle">
              {node.label}
            </text>
          </>
        );
      case "core":
        return (
          <>
            <circle className="brain-core-glow" r={sizePx + 40} fill="url(#brain-core-glow)" />
            <rect
              x={-sizePx}
              y={-sizePx}
              width={sizePx * 2}
              height={sizePx * 2}
              rx={16}
              fill="#1b1622"
              stroke={color}
            />
            <g transform={`translate(${-sizePx * 0.5} ${-sizePx * 0.5})`}>
              {createElement(iconFor(node.icon), { size: sizePx })}
            </g>
            <text className="brain-node-label" y={sizePx + 20} textAnchor="middle">
              {node.label}
            </text>
          </>
        );
      case "domain":
        return (
          <>
            <circle className="brain-domain-halo" r={sizePx} fill="none" stroke={color} />
            <circle r={sizePx} fill="#181622" stroke={color} />
            <g transform={`translate(${-sizePx / 2} ${-sizePx / 2})`}>
              {createElement(iconFor(node.icon), { size: sizePx })}
            </g>
            <text className="brain-node-label" y={sizePx + 16} textAnchor="middle">
              {node.label}
            </text>
          </>
        );
      case "app":
        return (
          <>
            <polygon points={hexPoints(sizePx)} fill="#181622" stroke={color} />
            <g transform={`translate(${-sizePx * 0.45} ${-sizePx * 0.45})`}>
              {createElement(iconFor(node.icon), { size: sizePx * 0.9 })}
            </g>
            <title>{node.label}</title>
          </>
        );
      case "skill":
      case "page":
        return (
          <>
            <polygon points={starPoints(sizePx)} fill={color} fillOpacity={0.85} stroke={color} />
            <title>{node.label}</title>
          </>
        );
      case "routine":
        return (
          <>
            <circle r={sizePx} fill={color} fillOpacity={0.85} />
            <title>{node.label}</title>
          </>
        );
      default:
        // file: tacka bez stalne labele, sire nevidljivo hit-polje za klik.
        return (
          <>
            <circle r={sizePx + 6} fill="transparent" />
            <circle
              className="brain-file-dot"
              r={sizePx}
              fill={color}
              style={{ animationDelay: twinkleDelay(node) }}
            />
            <title>{node.label}</title>
          </>
        );
    }
  }

  return (
    <svg
      ref={svgRef}
      className="brain-canvas"
      role="img"
      aria-label="Second Brain graf"
      onPointerDown={onPointerDown}
      onPointerMove={onPointerMove}
      onPointerUp={endDrag}
      onPointerLeave={endDrag}
      onClick={onBackgroundClick}
    >
      <defs>
        <radialGradient id="brain-core-glow" cx="50%" cy="50%" r="50%">
          <stop offset="0%" stopColor="#ff8a3d" stopOpacity="0.55" />
          <stop offset="100%" stopColor="#ff8a3d" stopOpacity="0" />
        </radialGradient>
        <pattern
          id="brain-hex-grid"
          width={HEX_W}
          height={HEX_TILE_H}
          patternUnits="userSpaceOnUse"
        >
          <polygon
            className="brain-hex-cell"
            points={hexPoints(HEX_R)}
            transform={`translate(${HEX_W / 2} ${HEX_H / 2})`}
          />
          <polygon
            className="brain-hex-cell"
            points={hexPoints(HEX_R)}
            transform={`translate(0 ${HEX_H})`}
          />
          <polygon
            className="brain-hex-cell"
            points={hexPoints(HEX_R)}
            transform={`translate(${HEX_W} ${HEX_H})`}
          />
        </pattern>
      </defs>

      <g transform={`translate(${cx + view.x} ${cy + view.y}) scale(${scale})`}>
        {/* Hex-grid pozadina — ispod svega. */}
        <rect x={-4000} y={-4000} width={8000} height={8000} fill="url(#brain-hex-grid)" />

        {/* Obruci-vodici + labele (uspravne, van rotirajucih grupa). */}
        <g className="brain-rings">
          {ringGuides.map((r) => (
            <circle key={r} className="brain-ring" cx={0} cy={0} r={r} />
          ))}
          {ringLabels.map(({ label, r }) => (
            <text key={label} className="brain-ring-label" x={0} y={-r} textAnchor="middle">
              {label}
            </text>
          ))}
        </g>

        {/* Orbita: dividers + linije + cvorovi rotiraju KAO JEDNA GRUPA, pa
            linije uvek ostaju prikacene na tacke/ikone. Labele i ikone se
            kontra-rotiraju (brain-upright) da ostanu uspravne. Na fokus se
            orbita pauzira (lakši klik na susede). */}
        <g className={focusId !== null ? "brain-orbit paused" : "brain-orbit"}>
        {/* "Spacer" linije koje razdvajaju sektore memorije po domenu. */}
        <g className="brain-mem-dividers">
          {memoryDividers.map((angle) => (
            <line
              key={`div-${angle.toFixed(4)}`}
              x1={MEM_DIV_INNER * Math.cos(angle)}
              y1={MEM_DIV_INNER * Math.sin(angle)}
              x2={MEM_DIV_OUTER * Math.cos(angle)}
              y2={MEM_DIV_OUTER * Math.sin(angle)}
              className="brain-mem-divider"
            />
          ))}
        </g>

        {/* Ivice sadrzanja (strukturne) + konekcione linije ka fokusu — u istoj
            orbiti kao cvorovi, pa padaju tacno na tacke; highlight se
            "iscrtava" animacijom. */}
        <g className="brain-edges">
          {structuralLines.map((edge) => {
            const a = byId.get(edge.source);
            const b = byId.get(edge.target);
            if (!a || !b) {
              return null;
            }
            return (
              <line
                key={`${edge.source}->${edge.target}`}
                x1={a.x}
                y1={a.y}
                x2={b.x}
                y2={b.y}
                className="brain-edge"
                opacity={focusId !== null ? 0.08 : 0.22}
              />
            );
          })}

          {focusNode &&
            focusNeighborsVisible.map((id) => {
              const b = byId.get(id);
              if (!b) {
                return null;
              }
              return (
                <line
                  // Kljuc nosi focusId da se draw-animacija ponovo okine na svaki
                  // novi fokus.
                  key={`hl-${focusId}-${id}`}
                  x1={focusNode.x}
                  y1={focusNode.y}
                  x2={b.x}
                  y2={b.y}
                  className="brain-edge highlight"
                  stroke={nodeColor(focusNode)}
                  pathLength={1}
                />
              );
            })}
        </g>

        {/* Cvorovi. Centri orbitiraju; kod cvorova sa labelom/ikonom sadržaj se
            kontra-rotira (brain-upright) pa ostaje uspravan i citljiv. */}
        <g className="brain-nodes">
          {visibleNodes.map((node) => {
            const color = nodeColor(node);
            const nodeSize = sizeFor(node.kind);
            const isFocus = node.id === focusId;
            const dimmed = focusId !== null && !isFocus && !focusNeighborIds.has(node.id);
            const entered = enteredIds.has(node.id);
            // Cvorovi sa citljivim sadržajem ostaju uspravni; simetricni glyph-ovi
            // (skill/routine/file) mogu da rotiraju sa orbitom.
            const upright =
              node.kind === "core" || node.kind === "domain" || node.kind === "app" ||
              node.kind === "cell" || node.kind === "area" || node.kind === "tool";
            const shape = renderShape(node, nodeSize, color);
            return (
              <g
                key={node.id}
                data-testid={`brain-node-${node.id}`}
                className={[
                  "brain-node",
                  `kind-${node.kind}`,
                  isFocus ? "selected" : "",
                  dimmed ? "dimmed" : "",
                  entered ? "" : "brain-node-enter",
                ]
                  .filter(Boolean)
                  .join(" ")}
                transform={`translate(${node.x} ${node.y})`}
                style={{ color }}
                onClick={(event) => {
                  event.stopPropagation();
                  onSelect(node.id);
                }}
              >
                {upright ? <g className="brain-upright">{shape}</g> : shape}
              </g>
            );
          })}
        </g>
        </g>
      </g>
    </svg>
  );
}

export default BrainCanvas;
