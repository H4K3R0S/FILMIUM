"""Second Brain jedne ćelije: graf SOPSTVENOG repoa (bez CORE-a).

Samostalno, bez ijednog uvoza ka CORE slojevima (registar domena, cells.json,
CORE-ov second_brain). Skenira samo svoj koren i grupiše čvorove po oblastima
repoa (backend/gui/atomi/domen/docs).
"""
from __future__ import annotations

import os
from dataclasses import asdict, dataclass, field
from pathlib import Path

# Raspored ĆELIJE (ne CORE): GUI je na `gui/src` (top-level), ne `apps/gui/src`;
# backend na `core` i `apps/api`. Nepostojeći koreni se preskaču.
_SCAN_ROOTS: tuple[str, ...] = (
    "core", "apps/api", "gui/src", "scripts", "tests", "docs", ".ai",
)
_EXCLUDE_DIRS: frozenset[str] = frozenset({
    "node_modules", ".venv", ".git", "dist", "build",
    "__pycache__", ".pytest_cache",
})
_EXCLUDE_SUFFIX: tuple[str, ...] = (".pyc",)
_SENSITIVE_NAMES: frozenset[str] = frozenset({".env"})
_ROUTINE_HINTS: tuple[str, ...] = ("automation", "cron", "scheduled", "auto_update")
MAX_BRAIN_READ_BYTES: int = 512_000

# Semantički obruči Second Brain-a oko domena (centar). Redosled = redosled
# hub-ova u grafu: Skills (kod/moći domena), Memory (znanje: `.ai/` + docs),
# Alati (alati koje domen koristi — deklarisani u `cell.json`). Fajlovi idu u
# Skills ili Memory; „Alati" nije iz fajlova nego iz manifesta.
_RINGS: tuple[tuple[str, str, str], ...] = (
    ("skills", "Skills", "sparkles"),
    ("memory", "Memory", "database"),
    ("alati", "Alati", "plug"),
)
_RING_LABEL: dict[str, str] = {r: label for r, label, _ in _RINGS}
_RING_ICON: dict[str, str] = {r: icon for r, _, icon in _RINGS}


class BrainGraphError(Exception):
    """Putanja je neispravna, van obima ili fajl nije čitljiv."""


@dataclass(frozen=True)
class BrainNode:
    id: str
    label: str
    kind: str
    group: str
    path: str | None
    route: str | None
    parent_id: str | None
    icon: str
    meta: dict = field(default_factory=dict)


@dataclass(frozen=True)
class BrainEdge:
    source: str
    target: str
    kind: str


@dataclass(frozen=True)
class BrainGraph:
    nodes: tuple[BrainNode, ...]
    edges: tuple[BrainEdge, ...]
    groups: tuple[str, ...]

    def to_dict(self) -> dict:
        return {
            "nodes": [asdict(n) for n in self.nodes],
            "edges": [asdict(e) for e in self.edges],
            "groups": [{"id": g, "label": _RING_LABEL.get(g, g)} for g in self.groups],
        }


def default_root() -> Path:
    # core/system/cell_brain.py -> koren ćelije je dva nivoa iznad `core`.
    return Path(__file__).resolve().parents[2]


def _ring_for(rel_posix: str) -> str:
    """Obruč jednog fajla: `.ai/` i `docs/` su Memory (znanje), ostalo su Skills
    (kod/moći domena). „Alati" ne dolaze iz fajlova (vidi `build_cell_brain`)."""
    if rel_posix.startswith((".ai/", "docs/")):
        return "memory"
    return "skills"


def _is_routine(rel_posix: str) -> bool:
    low = rel_posix.lower()
    if not low.endswith(".py"):
        return False
    name = low.rsplit("/", 1)[-1]
    if "/tests/" in low or name.startswith("test_") or ".test." in name:
        return False
    return any(h in low for h in _ROUTINE_HINTS)


def _scan_files(root: Path) -> list[str]:
    found: list[str] = []
    for base in _SCAN_ROOTS:
        start = root / base
        if not start.exists():
            continue
        for dirpath, dirnames, filenames in os.walk(start):
            dirnames[:] = sorted(d for d in dirnames if d not in _EXCLUDE_DIRS)
            for name in sorted(filenames):
                if name.endswith(_EXCLUDE_SUFFIX) or name in _SENSITIVE_NAMES:
                    continue
                found.append(Path(dirpath, name).relative_to(root).as_posix())
    return sorted(found)


def build_cell_brain(
    root: Path | None = None,
    name: str | None = None,
    tools: list[dict] | None = None,
) -> BrainGraph:
    """Graf ćelije: DOMEN u centru, pa obruči Skills / Memory / Alati.

    `name` je prikazno ime domena (iz `cell.json`); bez njega — ime foldera.
    `tools` je lista alata koje domen koristi (iz `cell.json`), svaki `{name,
    icon?, description?}`; prazna/None → nema „Alati" obruča (npr. KALIMA za sada).
    """
    root = (root or default_root())
    nodes: list[BrainNode] = []
    edges: list[BrainEdge] = []

    # Centar = domen.
    root_id = "cell:root"
    nodes.append(BrainNode(root_id, name or root.name, "cell", "skills",
                           None, "/dashboard", None, "brain", {}))

    files = _scan_files(root)
    file_rings = [r for r, _, _ in _RINGS if r != "alati"
                  and any(_ring_for(f) == r for f in files)]
    tools = tools or []
    used_rings = file_rings + (["alati"] if tools else [])

    # Hub-ovi obruča (root -> hub ivica; fajl -> hub se izvodi iz parent_id).
    for ring in used_rings:
        rid = f"area:{ring}"
        nodes.append(BrainNode(rid, _RING_LABEL[ring], "area", ring, None, None,
                               root_id, _RING_ICON[ring], {}))
        edges.append(BrainEdge(root_id, rid, "contains"))

    # Fajlovi u Skills/Memory.
    for rel in files:
        ring = _ring_for(rel)
        label = rel.rsplit("/", 1)[-1]
        kind = "routine" if _is_routine(rel) else "file"
        icon = "clock" if kind == "routine" else "file"
        nodes.append(BrainNode(f"{kind}:{rel}", label, kind, ring, rel, None,
                               f"area:{ring}", icon, {}))

    # Alati (iz manifesta) — čvorovi bez fajla, pod „Alati" hubom.
    for tool in tools:
        naziv = str(tool.get("name", "")).strip()
        if not naziv:
            continue
        opis = tool.get("description")
        meta = {"description": str(opis)} if opis else {}
        nodes.append(BrainNode(f"tool:{naziv}", naziv, "tool", "alati", None,
                               None, "area:alati", str(tool.get("icon", "plug")),
                               meta))
        edges.append(BrainEdge("area:alati", f"tool:{naziv}", "contains"))

    return BrainGraph(tuple(nodes), tuple(edges), tuple(used_rings))


def read_cell_brain_file(rel: str, root: Path | None = None) -> dict:
    """Bezbedno čita jedan tekstualni fajl iz obima ćelije (za pregled)."""
    base = (root or default_root()).resolve()
    cleaned = (rel or "").strip().lstrip("/").replace("\\", "/")
    if not cleaned or ".." in cleaned.split("/"):
        raise BrainGraphError(f"Neispravna putanja: {rel}")

    target = (base / cleaned).resolve()
    if target != base and base not in target.parents:
        raise BrainGraphError(f"Putanja izlazi iz korena: {rel}")

    parts = target.relative_to(base).parts
    if any(part in _EXCLUDE_DIRS for part in parts):
        raise BrainGraphError(f"Putanja je van obima: {rel}")
    if target.name in _SENSITIVE_NAMES or target.name.endswith(_EXCLUDE_SUFFIX):
        raise BrainGraphError(f"Fajl nije dostupan: {rel}")

    in_scope = any(
        parts[: len(Path(b).parts)] == Path(b).parts for b in _SCAN_ROOTS
    )
    if not in_scope:
        raise BrainGraphError(f"Putanja je van obima: {rel}")
    if not target.is_file():
        raise BrainGraphError(f"Fajl ne postoji: {rel}")

    rel_out = target.relative_to(base).as_posix()
    size = target.stat().st_size
    if size > MAX_BRAIN_READ_BYTES:
        return {"path": rel_out, "content": "", "truncated": True, "binary": False, "size": size}
    data = target.read_bytes()
    if b"\x00" in data:
        return {"path": rel_out, "content": "", "truncated": False, "binary": True, "size": size}
    return {
        "path": rel_out,
        "content": data.decode("utf-8", errors="replace"),
        "truncated": False, "binary": False, "size": size,
    }
