import { getJson } from "./httpClient";
import type { BrainFile, BrainGraph } from "../types/secondBrain";

/** Ucitava ceo Second Brain graf sa CORE API-ja. */
export function getBrainGraph(): Promise<BrainGraph> {
  return getJson<BrainGraph>("/api/v1/second-brain/graph");
}

/** Ucitava tekstualni sadrzaj jednog fajla iz obima (za pregled). */
export function getBrainFile(path: string): Promise<BrainFile> {
  return getJson<BrainFile>(`/api/v1/second-brain/file?path=${encodeURIComponent(path)}`);
}

/** Regioni znanja (glumci/filmovi/serije/anime/kolekcije) — top-N po skoru. */
export function getBrainRegions(topN = 16): Promise<import("../types/secondBrain").BrainRegionsResponse> {
  return getJson(`/api/v1/second-brain/regions?top_n=${topN}`);
}

/** Drill-down: svi čvorovi jednog regiona (paginirano). */
export function getBrainRegionNodes(
  key: string,
  offset = 0,
  limit = 400,
  lite = false,
): Promise<import("../types/secondBrain").BrainRegionNodesResponse> {
  return getJson(
    `/api/v1/second-brain/region/${encodeURIComponent(key)}?offset=${offset}&limit=${limit}${lite ? "&lite=1" : ""}`,
  );
}

/** Sadržaj jednog atom fajla regiona (za sidebar). */
export function getBrainRegionFile(
  region: string,
  rel: string,
): Promise<{ region: string; rel: string; content: string; error?: string }> {
  return getJson(
    `/api/v1/second-brain/region-file?region=${encodeURIComponent(region)}&rel=${encodeURIComponent(rel)}`,
  );
}

/** Nadji atom po slugu (za navigaciju kroz [[linkove]] i klik na skill/alat). */
export function getBrainResolve(
  slug: string,
): Promise<import("../types/secondBrain").BrainResolveResponse> {
  return getJson(`/api/v1/second-brain/resolve?slug=${encodeURIComponent(slug)}`);
}

/** MAPS graf ovog sistema (root/oblasti/atomi/rutine/run-ovi/app-ovi). */
export function getBrainMaps(): Promise<import("../features/secondbrain/mapsTypes").MapsGraph> {
  return getJson(`/api/v1/second-brain/maps`);
}

/** Sfere drugih sistema (domeni) — sažetak, fail-soft (offline = online:false). */
export function getSpheres(): Promise<{ spheres: import("../features/secondbrain/mapsTypes").Sphere[] }> {
  return getJson(`/api/v1/second-brain/spheres`);
}

/** MAPS graf jedne sfere (backend proksira i adaptira domenov /regions). */
export function getSphereMaps(id: string): Promise<import("../features/secondbrain/mapsTypes").MapsGraph> {
  return getJson(`/api/v1/second-brain/spheres/${encodeURIComponent(id)}/maps`);
}

/** Napredni pretraživač atoma (naziv/slug kroz sve regione + skills/alati/problemi). */
export function getBrainSearch(
  q: string,
  limit = 30,
): Promise<import("../types/secondBrain").BrainSearchResponse> {
  return getJson(`/api/v1/second-brain/search?q=${encodeURIComponent(q)}&limit=${limit}`);
}
