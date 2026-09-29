export type BrainNodeKind =
  | "core" | "skill" | "page" | "domain" | "file" | "routine" | "app"
  // Ćelijski Second Brain: domen (centar), obruč-hub, alat.
  | "cell" | "area" | "tool";
export type BrainEdgeKind = "contains";
export type BrainGroup = "codium" | "filmium" | "imperium" | "kalima" | "core";

export interface BrainNode {
  id: string;
  label: string;
  kind: BrainNodeKind;
  group: string;
  path: string | null;
  route: string | null;
  parent_id: string | null;
  icon: string;
  meta: Record<string, unknown>;
}

export interface BrainEdge {
  source: string;
  target: string;
  kind: BrainEdgeKind;
}

export interface BrainGroupInfo {
  id: string;
  label: string;
}

export interface BrainGraph {
  nodes: BrainNode[];
  edges: BrainEdge[];
  groups: BrainGroupInfo[];
}

export interface BrainFile {
  path: string;
  content: string;
  truncated: boolean;
  binary: boolean;
  size: number;
}

export type BrainRegionNode = {
  id: string;
  label: string;
  score: number;
  rel: string;
  region: string;
  slug: string;
  links: string[];
  link_regions?: Array<{ slug: string; region: string; conn?: number }>;
  rating: number;
  conn: number;
};

export type BrainRegion = {
  key: string;
  label: string;
  icon: string;
  count: number;
  nodes: BrainRegionNode[];
};

export type BrainMetaItem = { name: string; icon?: string; description?: string; slug?: string };
export type BrainRegionsResponse = {
  regions: BrainRegion[];
  total: number;
  meta?: { tools: BrainMetaItem[]; skills: BrainMetaItem[] };
};

export type BrainRegionNodesResponse = {
  key: string;
  label: string;
  count: number;
  nodes: BrainRegionNode[];
};

export type BrainResolveResponse = {
  found: boolean;
  slug: string;
  region?: string;
  rel?: string;
  label?: string;
  score?: number;
  rating?: number;
  conn?: number;
  links?: string[];
  link_regions?: Array<{ slug: string; region: string; conn?: number }>;
  content?: string;
};

export type BrainSearchHit = {
  label: string;
  slug: string;
  region: string;
  rel: string;
  conn: number;
  score: number;
};
export type BrainSearchResponse = { query: string; results: BrainSearchHit[] };
