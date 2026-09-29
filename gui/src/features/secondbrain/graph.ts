import type { BrainEdge, BrainGraph, BrainNode } from "../../types/secondBrain";

export interface BrainIndex {
  nodes: BrainNode[];
  byId: Map<string, BrainNode>;
  edges: BrainEdge[];
  adjacency: Map<string, Set<string>>;
  childrenByParent: Map<string, BrainNode[]>;
}

export function buildIndex(graph: BrainGraph): BrainIndex {
  const byId = new Map<string, BrainNode>();
  const childrenByParent = new Map<string, BrainNode[]>();
  for (const node of graph.nodes) {
    byId.set(node.id, node);
    if (node.parent_id) {
      const list = childrenByParent.get(node.parent_id) ?? [];
      list.push(node);
      childrenByParent.set(node.parent_id, list);
    }
  }
  const adjacency = new Map<string, Set<string>>();
  const link = (a: string, b: string) => {
    if (!adjacency.has(a)) adjacency.set(a, new Set());
    adjacency.get(a)!.add(b);
  };
  for (const edge of graph.edges) {
    if (byId.has(edge.source) && byId.has(edge.target)) {
      link(edge.source, edge.target);
      link(edge.target, edge.source);
    }
  }
  return { nodes: graph.nodes, byId, edges: graph.edges, adjacency, childrenByParent };
}

/** Susedstvo za fokus: edge-susedi + roditelj + deca (iz parent_id). */
export function neighborIds(index: BrainIndex, nodeId: string): Set<string> {
  const result = new Set<string>(index.adjacency.get(nodeId) ?? []);
  const self = index.byId.get(nodeId);
  if (self?.parent_id) result.add(self.parent_id);
  for (const child of index.childrenByParent.get(nodeId) ?? []) result.add(child.id);
  result.delete(nodeId);
  return result;
}
