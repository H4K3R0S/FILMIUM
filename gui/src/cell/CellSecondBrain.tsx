import { useCallback, useEffect, useMemo, useState } from "react";
import { Search } from "lucide-react";
import { useNavigate, useSearchParams } from "react-router";

import BrainCanvas from "../features/secondbrain/BrainCanvas";
import BrainMaps from "../features/secondbrain/BrainMaps";
import BrainRegions from "../features/secondbrain/BrainRegions";
import BrainSpheres, { type SphereItem } from "../features/secondbrain/BrainSpheres";
import BrainContentPanel from "./CellBrainContentPanel";
import BrainInfoPanel from "../features/secondbrain/BrainInfoPanel";
import { buildIndex, neighborIds } from "../features/secondbrain/graph";
import { sampleVisible } from "../features/secondbrain/layout";
import {
  CELL_RING_GUIDES,
  CELL_RING_LABELS,
  layoutCellBrain,
} from "../features/secondbrain/cellBrainLayout";
import type { MapsGraph, MapsNode, Sphere } from "../features/secondbrain/mapsTypes";
import {
  getBrainGraph, getBrainMaps, getBrainRegionFile, getSphereMaps, getSpheres,
} from "../services/secondBrainApi";
import type { BrainGraph, BrainNode } from "../types/secondBrain";
import "../styles/second-brain.css";

const EMPTY_GRAPH: BrainGraph = { nodes: [], edges: [], groups: [] };
const LOD_CAP = 200;
// Sopstveni sistem (centar). Backend `/spheres` vraća SAMO druge sisteme, pa je ovaj id
// samo lokalni ključ (isti fajl radi u svakoj app-i i u svakom domenu).
const HOME = "self";
type ViewMode = "mapa" | "graf" | "regioni";
const VIEW_MODES: ViewMode[] = ["mapa", "regioni", "graf"];

/** Second Brain ćelije: MAPS mapa (default) · regioni znanja · graf repoa; sfere drugih sistema. */
function CellSecondBrain() {
  const navigate = useNavigate();
  const [params, setParams] = useSearchParams();
  const [graph, setGraph] = useState<BrainGraph>(EMPTY_GRAPH);
  const [focusId, setFocusId] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const rawView = params.get("view");
  const viewMode: ViewMode = VIEW_MODES.includes(rawView as ViewMode) ? (rawView as ViewMode) : "mapa";
  const setViewMode = (m: ViewMode) => setParams((p) => { p.set("view", m); return p; }, { replace: true });

  // ----------          MAPS: lokalni graf + sfere drugih sistema          ----------
  const [system, setSystem] = useState<string>(HOME);
  const [homeMaps, setHomeMaps] = useState<MapsGraph | null>(null);
  const [sphereMaps, setSphereMaps] = useState<MapsGraph | null>(null);
  const [spheres, setSpheres] = useState<Sphere[]>([]);
  const [mapsError, setMapsError] = useState<string | null>(null);
  const [mapsLoading, setMapsLoading] = useState(false);

  // Puna visina stranice: ćelijski `.workspace` se ne rasteže sam (CORE to
  // radi preko `second-brain-shell`, ćelija nema taj omotač). Klasa na <html>
  // dok je stranica montirana razvuče workspace/sadržaj (CSS u second-brain.css)
  // — radi i samostalno i chromeless (embed u CORE).
  useEffect(() => {
    const root = document.documentElement;
    root.classList.add("cell-brain-active");
    return () => root.classList.remove("cell-brain-active");
  }, []);

  useEffect(() => {
    let alive = true;
    void (async () => {
      try {
        const data = await getBrainGraph();
        if (!alive) {
          return;
        }
        setGraph(data);
        setErrorMessage(null);
      } catch (error) {
        if (!alive) {
          return;
        }
        setErrorMessage(
          error instanceof Error ? error.message : "Ucitavanje grafa nije uspelo.",
        );
      } finally {
        if (alive) {
          setIsLoading(false);
        }
      }
    })();
    return () => {
      alive = false;
    };
  }, []);

  // MAPS graf lokalnog sistema + sažetak sfera (fail-soft: greška samo u poruci).
  useEffect(() => {
    let alive = true;
    void (async () => {
      try {
        const data = await getBrainMaps();
        if (alive) { setHomeMaps(data); setMapsError(null); }
      } catch (error) {
        if (alive) setMapsError(error instanceof Error ? error.message : "Učitavanje mape nije uspelo.");
      }
      try {
        const s = await getSpheres();
        if (alive) setSpheres(s.spheres);
      } catch {
        /* sfere su opcione */
      }
    })();
    return () => { alive = false; };
  }, []);

  const pickSystem = useCallback((id: string) => {
    setSystem(id);
    setSphereMaps(null);
    setMapsError(null);
    if (id === HOME) return;
    setMapsLoading(true);
    getSphereMaps(id)
      .then((g) => { setSphereMaps(g); setMapsLoading(false); })
      .catch((error) => {
        setMapsError(error instanceof Error ? error.message : `${id} ne odgovara.`);
        setMapsLoading(false);
      });
  }, []);

  const fetchAtom = useCallback(async (node: MapsNode): Promise<string> => {
    const res = await getBrainRegionFile(node.area ?? "", node.path ?? "");
    if (res.error) throw new Error(res.error);
    return res.content;
  }, []);

  const sphereItems: SphereItem[] = useMemo(() => [
    {
      id: HOME, label: homeMaps?.center.label ?? "…", online: homeMaps !== null,
      total: homeMaps?.stats.files ?? 0, areas: homeMaps?.areas ?? [],
    },
    ...spheres,
  ], [homeMaps, spheres]);
  const activeSphere = spheres.find((s) => s.id === system) ?? null;
  const mapsGraph = system === HOME ? homeMaps : sphereMaps;

  const index = useMemo(() => buildIndex(graph), [graph]);
  const positioned = useMemo(() => layoutCellBrain(graph.nodes), [graph]);

  // LOD kad nema fokusa (uzorak do LOD_CAP); kad je fokus postavljen, drzimo
  // svu strukturu (ne-file cvorove) vidljivu + fokus + sve njegove susede
  // (uklj. fajlove van LOD-a).
  const visibleIds = useMemo(() => {
    if (focusId === null) {
      return sampleVisible(graph.nodes, LOD_CAP);
    }
    const ids = new Set<string>([focusId]);
    for (const id of neighborIds(index, focusId)) {
      ids.add(id);
    }
    for (const node of graph.nodes) {
      if (node.kind !== "file") {
        ids.add(node.id);
      }
    }
    return ids;
  }, [focusId, graph.nodes, index]);

  const focusNode = focusId ? index.byId.get(focusId) ?? null : null;
  const focusNeighborIds = useMemo(
    () => (focusId ? neighborIds(index, focusId) : new Set<string>()),
    [index, focusId],
  );
  const neighborNodes = focusNode
    ? [...focusNeighborIds].map((id) => index.byId.get(id)).filter((n): n is BrainNode => Boolean(n))
    : [];

  // Cvor koji pokazuje na stvaran fajl → levi panel sa sadrzajem; ostalo
  // (domeni/skilovi/stranice = folderi) → desni info-panel.
  const FILE_KINDS = new Set(["file", "routine", "app", "core"]);
  const showsContent = Boolean(focusNode && focusNode.path && FILE_KINDS.has(focusNode.kind));

  function runSearch(event: React.FormEvent): void {
    event.preventDefault();
    const needle = query.trim().toLowerCase();
    if (needle === "") {
      return;
    }
    const match = graph.nodes.find(
      (node) =>
        node.label.toLowerCase().includes(needle) ||
        (node.path ?? "").toLowerCase().includes(needle),
    );
    if (match) {
      setFocusId(match.id);
    }
  }

  function openNode(node: BrainNode): void {
    if (node.route) {
      navigate(node.route);
    }
  }

  return (
    <div className="brain-page">
      <header className="brain-topbar">
        <h1 className="brain-heading">Second Brain</h1>
        {viewMode === "graf" && (
          <form className="brain-search" onSubmit={runSearch}>
            <Search size={16} />
            <input
              aria-label="Pretraga cvorova"
              placeholder="Pretrazi cvorove…"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
            />
          </form>
        )}
        <div className="brain-viewtoggle" role="tablist">
          <button
            className={viewMode === "mapa" ? "is-active" : ""}
            onClick={() => setViewMode("mapa")}
            type="button"
          >
            Mapa
          </button>
          <button
            className={viewMode === "regioni" ? "is-active" : ""}
            onClick={() => setViewMode("regioni")}
            type="button"
          >
            Regioni znanja
          </button>
          <button
            className={viewMode === "graf" ? "is-active" : ""}
            onClick={() => setViewMode("graf")}
            type="button"
          >
            Graf repoa
          </button>
        </div>
      </header>

      {errorMessage && viewMode !== "mapa" && <p className="brain-message error">{errorMessage}</p>}
      {isLoading && viewMode !== "mapa" && <p className="brain-message">Ucitavam graf…</p>}

      <div className="brain-stage">
        {viewMode === "mapa" ? (
          mapsGraph ? (
            <BrainMaps
              externalUrl={activeSphere ? `${activeSphere.url}/#/second-brain` : undefined}
              fileFetcher={system === HOME ? fetchAtom : undefined}
              graph={mapsGraph}
              key={system}
              subtitle={system === HOME ? "Second Brain · MAPS" : `Second Brain · sfera ${activeSphere?.label ?? system}`}
              title={mapsGraph.center.label}
            >
              <BrainSpheres active={system} items={sphereItems} onPick={pickSystem} />
              {mapsLoading && <div className="maps-notice">Učitavam sferu…</div>}
            </BrainMaps>
          ) : (
            <div className="maps-root">
              <BrainSpheres active={system} items={sphereItems} onPick={pickSystem} />
              <div className="maps-notice">
                {mapsLoading ? "Učitavam sferu…" : mapsError ?? "Učitavam mapu…"}
                {system !== HOME && !mapsLoading && (
                  <button onClick={() => pickSystem(HOME)} type="button">← {homeMaps?.center.label ?? "nazad"}</button>
                )}
              </div>
            </div>
          )
        ) : viewMode === "regioni" ? (
          <BrainRegions
            domainName={graph.nodes[0]?.label ?? "FILMIUM"}
          />
        ) : (
          <>
        <BrainCanvas
          positioned={positioned}
          index={index}
          visibleIds={visibleIds}
          focusId={focusId}
          onSelect={setFocusId}
          ringGuides={CELL_RING_GUIDES}
          ringLabels={CELL_RING_LABELS}
        />
        {showsContent ? (
          <BrainContentPanel
            node={focusNode}
            onOpen={openNode}
            onClose={() => setFocusId(null)}
          />
        ) : (
          <BrainInfoPanel
            node={focusNode}
            neighbors={neighborNodes}
            onOpen={openNode}
            onClose={() => setFocusId(null)}
          />
        )}
          </>
        )}
      </div>

      {focusNode && viewMode === "graf" && (
        <p className="brain-caption">
          Prošireno: {focusNode.label} — {focusNeighborIds.size} stavki
        </p>
      )}
    </div>
  );
}

export default CellSecondBrain;
