from __future__ import annotations

import hashlib
import re
from pathlib import PurePosixPath

from core.rag.node import Node

_DOMENI = ("codium", "filmium", "imperium", "kalima")
_KOD_EKST = (".py", ".ts", ".tsx", ".js", ".mjs", ".rs", ".go")


def has_frontmatter(text: str) -> bool:
    if not text.startswith("---"):
        return False
    return len(text.split("---", 2)) >= 3


def _norm(relpath: str) -> str:
    return str(PurePosixPath(relpath.replace("\\", "/")))


def infer_domain(relpath: str) -> tuple[str, str]:
    delovi = _norm(relpath).split("/")
    if len(delovi) >= 3 and delovi[0] == "core" and delovi[1] == "domains" and delovi[2] in _DOMENI:
        return delovi[2], "domain"
    return "core", "core"


def infer_type(relpath: str) -> str:
    p = _norm(relpath)
    ime = p.rsplit("/", 1)[-1]
    if p.startswith("tests/") and ime.endswith(".py"):
        return "test"
    if ime.endswith(_KOD_EKST):
        return "code_unit"
    if ime.endswith(".md"):
        if p.startswith(".ai/dev-log") or "/.ai/dev-log" in ("/" + p):
            return "log"
        if "docs/superpowers/specs" in p:
            return "spec"
        if "docs/superpowers/plans" in p:
            return "plan"
        return "reference"
    return "reference"


def infer_namespace(node_type: str) -> str:
    return "protected" if node_type in ("code_unit", "test") else "global"


def _slug(ime: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", ime.lower()).strip("-") or "cvor"


def derive_node_from_file(relpath: str, text: str) -> Node:
    rel = _norm(relpath)
    domain, tier = infer_domain(rel)
    tip = infer_type(rel)
    ns = infer_namespace(tip)
    ime = rel.rsplit("/", 1)[-1]
    kratki = hashlib.sha1(rel.encode("utf-8"), usedforsecurity=False).hexdigest()[:8]
    prva = next((l.strip() for l in text.splitlines() if l.strip()), "")
    return Node(
        id=f"{domain}-{kratki}-{_slug(ime)}",
        domain=domain,
        node_type=tip,
        namespace=ns,
        visibility=ns,
        tier=tier,
        title=ime,
        summary=prva[:120] or None,
        source_path=rel,
        content_hash=hashlib.sha256(text.encode("utf-8")).hexdigest(),
        body=text,
    )
