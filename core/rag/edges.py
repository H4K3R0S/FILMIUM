# Strukturni edges izvedeni iz sadrzaja: python importi -> depends_on/tested_by,
# markdown linkovi -> references. Koristi ih ingest pipeline (po fajlu) i
# scripts/rag_edges.py (pun prolaz + dev-log lanac).
from __future__ import annotations

import ast
import os
import re
from pathlib import PurePosixPath

import psycopg

_LINK = re.compile(r"\[[^\]]+\]\(([^)]+)\)")
_INTERNI = ("core", "apps")


def extract_python_deps(text: str) -> list[str]:
    """Interni (core./apps.) dotted moduli koje fajl importuje."""
    try:
        stablo = ast.parse(text)
    except SyntaxError:
        return []
    mods: list[str] = []
    for n in ast.walk(stablo):
        if isinstance(n, ast.Import):
            mods += [a.name for a in n.names]
        elif isinstance(n, ast.ImportFrom):
            if n.level:  # relativni import — preskoci
                continue
            if n.module:
                mods.append(n.module)
                mods += [f"{n.module}.{a.name}" for a in n.names]
    return sorted({m for m in mods if m.split(".")[0] in _INTERNI})


def module_candidates(mod: str) -> list[str]:
    base = mod.replace(".", "/")
    return [base + ".py", base + "/__init__.py"]


def markdown_link_targets(text: str, *, base_dir: str) -> list[str]:
    """Repo-relativne putanje .md linkova u tekstu."""
    out: list[str] = []
    for m in _LINK.finditer(text):
        href = m.group(1).split("#")[0].strip()
        if not href.endswith(".md") or href.startswith("http"):
            continue
        spoj = str(PurePosixPath(base_dir) / href) if base_dir else href
        out.append(str(PurePosixPath(os.path.normpath(spoj).replace("\\", "/"))))
    return out


def _resolve_db(connection: psycopg.Connection, kandidati: list[str]) -> str | None:
    red = connection.execute(
        "SELECT id FROM nodes WHERE source_path = ANY(%s) LIMIT 1", (kandidati,)
    ).fetchone()
    return red["id"] if red else None


def _ins(connection, src, dst, tip, w, exempt) -> None:
    connection.execute(
        "INSERT INTO edges (src,dst,edge_type,weight,decay_exempt,last_used_at) "
        "VALUES (%s,%s,%s,%s,%s,now()) "
        "ON CONFLICT (src,dst,edge_type) DO UPDATE SET last_used_at=now()",
        (src, dst, tip, w, exempt),
    )


def sync_structural_edges(connection, node, *, resolve=None) -> int:
    """Dodaje import/link edges za jedan cvor; samo ako cilj-cvor postoji.

    resolve(kandidati)->id|None; podrazumevano DB pretraga po source_path.
    """
    if resolve is None:
        def resolve(k):
            return _resolve_db(connection, k)
    sp = node.source_path or ""
    telo = node.body or ""
    dodato = 0
    if sp.endswith(".py"):
        je_test = sp.startswith("tests/")
        for mod in extract_python_deps(telo):
            tid = resolve(module_candidates(mod))
            if not tid or tid == node.id:
                continue
            if je_test:
                _ins(connection, tid, node.id, "tested_by", 0.8, False)
            else:
                _ins(connection, node.id, tid, "depends_on", 0.9, True)
            dodato += 1
    elif sp.endswith(".md"):
        base = str(PurePosixPath(sp).parent) if "/" in sp else ""
        for tgt in markdown_link_targets(telo, base_dir=base):
            tid = resolve([tgt])
            if not tid or tid == node.id:
                continue
            _ins(connection, node.id, tid, "references", 0.3, False)
            dodato += 1
    return dodato
