from __future__ import annotations

import hashlib
from dataclasses import dataclass, field

import yaml

from core.rag.schema_sql import EDGE_TYPES, NODE_TYPES

_VALIDNI_TIPOVI = frozenset(n for n, _t, _o in NODE_TYPES)
_VALIDNE_VEZE = frozenset(n for n, _w, _e in EDGE_TYPES)
_OBAVEZNA = ("id", "type", "domain", "namespace", "tier", "title")


class NodeValidationError(ValueError):
    """Frontmatter cvora je neispravan ili nekompletan."""


@dataclass(frozen=True)
class EdgeSpec:
    edge_type: str
    target: str
    weight: float


@dataclass(frozen=True)
class Node:
    id: str
    domain: str
    node_type: str
    namespace: str
    visibility: str
    tier: str
    title: str
    subtype: str | None = None
    owner_agent: str | None = None
    summary: str | None = None
    keywords: tuple[str, ...] = ()
    tags: tuple[str, ...] = ()
    symbols: tuple[str, ...] = ()
    source_path: str | None = None
    span_start: int | None = None
    span_end: int | None = None
    content_hash: str = ""
    attributes: dict = field(default_factory=dict)
    edges: tuple[EdgeSpec, ...] = ()
    body: str = ""


def _split_frontmatter(text: str) -> tuple[dict, str]:
    if not text.startswith("---"):
        raise NodeValidationError("Nedostaje YAML frontmatter (---)")
    delovi = text.split("---", 2)
    if len(delovi) < 3:
        raise NodeValidationError("Frontmatter nije zatvoren sa ---")
    meta = yaml.safe_load(delovi[1]) or {}
    if not isinstance(meta, dict):
        raise NodeValidationError("Frontmatter nije mapa kljuc-vrednost")
    return meta, delovi[2].strip()


def parse_node(text: str, *, source_path: str | None = None) -> Node:
    meta, body = _split_frontmatter(text)

    for kljuc in _OBAVEZNA:
        if not meta.get(kljuc):
            raise NodeValidationError(f"Nedostaje obavezno polje: {kljuc}")

    tip = meta["type"]
    if tip not in _VALIDNI_TIPOVI:
        raise NodeValidationError(f"Nepoznat node_type: {tip}")

    veze: list[EdgeSpec] = []
    for e in meta.get("edges", []) or []:
        et = e.get("type")
        if et not in _VALIDNE_VEZE:
            raise NodeValidationError(f"Nepoznat edge_type: {et}")
        veze.append(EdgeSpec(et, e["target"], float(e.get("weight", 0.5))))

    span = meta.get("span") or [None, None]
    return Node(
        id=meta["id"],
        domain=meta["domain"],
        node_type=tip,
        namespace=meta["namespace"],
        visibility=meta.get("visibility", meta["namespace"]),
        tier=meta["tier"],
        title=meta["title"],
        subtype=meta.get("subtype"),
        owner_agent=meta.get("owner_agent"),
        summary=meta.get("summary"),
        keywords=tuple(meta.get("keywords", []) or []),
        tags=tuple(meta.get("tags", []) or []),
        symbols=tuple(meta.get("symbols", []) or []),
        source_path=meta.get("source_path") or source_path,
        span_start=span[0],
        span_end=span[1],
        content_hash=hashlib.sha256(text.encode("utf-8")).hexdigest(),
        attributes=meta.get("attributes", {}) or {},
        edges=tuple(veze),
        body=body,
    )
