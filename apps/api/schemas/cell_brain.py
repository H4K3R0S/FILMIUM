"""Izlazne šeme za ćelijski Second Brain graf."""
from __future__ import annotations

from pydantic import BaseModel


class BrainNodeOut(BaseModel):
    id: str
    label: str
    kind: str
    group: str
    path: str | None
    route: str | None
    parent_id: str | None
    icon: str
    meta: dict[str, object] = {}


class BrainEdgeOut(BaseModel):
    source: str
    target: str
    kind: str


class GroupOut(BaseModel):
    id: str
    label: str


class BrainGraphOut(BaseModel):
    nodes: list[BrainNodeOut]
    edges: list[BrainEdgeOut]
    groups: list[GroupOut]


class BrainFileOut(BaseModel):
    path: str
    content: str
    truncated: bool
    binary: bool
    size: int
