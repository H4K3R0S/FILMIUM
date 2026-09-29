# ========== KONVERZIJA ZNANJA AGENTA U RAG NODOVE ==========
# Atomi (persona/tool/command) i settled-correct RAG-logovi -> ispravni RAG
# nodovi pod namespace-om cell:<domain>. Atom fajlovi se NE menjaju.
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import yaml

from core.rag.embedder import Embedder
from core.rag.ingest import ingest_text

# Ingestuje se SAMO settled-correct log. InteractionLog piše statuse
# "pending" (nedovršen), "correct" (ćutanje=tačno) i "wrong" (opovrgnut) —
# samo "correct" je pouzdano znanje; ostalo se preskače (bez ovoga bi
# opovrgnute/nedovršene interakcije zatrovale intent-prompt).
_CORRECT_STATUS = "correct"


def _frontmatter(meta: dict, body: str) -> str:
    yml = yaml.safe_dump(meta, allow_unicode=True, sort_keys=False).strip()
    return f"---\n{yml}\n---\n{body.strip()}\n"


def atom_to_node_text(domain: str, atom_id: str, atom_type: str,
                      title: str, body: str) -> str:
    meta = {
        "id": f"agent-{domain}-{atom_id}",
        "type": "reference",
        "subtype": atom_type,           # persona|tool|command (za filtriranje)
        "domain": domain,
        "namespace": f"cell:{domain}",
        "visibility": f"cell:{domain}",
        "tier": "domain",
        "title": title or atom_id,
    }
    return _frontmatter(meta, body)


def log_entry_to_node_text(domain: str, entry: dict) -> str | None:
    status = str(entry.get("status") or "")
    if status != _CORRECT_STATUS:
        return None
    understood = entry.get("understood") or {}
    intent = understood.get("intent", "")
    params = understood.get("params", {})
    telo = (
        f"Čuo: {entry.get('heard','')}\n"
        f"Razumeo: intent={intent} params={json.dumps(params, ensure_ascii=False)}\n"
        f"Alat: {entry.get('tool')}\n"
        f"Odgovor: {entry.get('reply','')}"
    )
    meta = {
        "id": f"agent-log-{domain}-{entry.get('log_id','')}",
        "type": "log",
        "subtype": "interaction",
        "domain": domain,
        "namespace": f"cell:{domain}",
        "visibility": f"cell:{domain}",
        "tier": "domain",
        "title": f"Interakcija {entry.get('log_id','')}: {intent}",
    }
    return _frontmatter(meta, telo)


def _parse_atom_meta(text: str) -> tuple[dict, str]:
    # Atom ima sopstveni frontmatter (id/type/title). Vrati (meta, telo).
    if not text.startswith("---"):
        return {}, text
    delovi = text.split("---", 2)
    if len(delovi) < 3:
        return {}, text
    front, telo = delovi[1], delovi[2].strip()
    try:
        meta = yaml.safe_load(front)
        if isinstance(meta, dict):
            return meta, telo
    except yaml.YAMLError:
        # Frontmatter nije čist YAML (npr. `related: [[wikilink]], [[..]]`) —
        # ne rušimo ingest; izvučemo samo osnovna polja linijskim skenom.
        pass
    meta = {}
    for line in front.splitlines():
        m = re.match(r"^(id|type|subtype|title)\s*:\s*(.+?)\s*$", line)
        if m:
            meta[m.group(1)] = m.group(2).strip().strip("\"'")
    return meta, telo


def ingest_cell(connection: Any, domain: str, root: str | Path, *,
                embedder: Embedder) -> dict:
    root = Path(root)
    personas = root / ".ai" / "atomi" / "personas"
    logs = root / ".ai" / "atomi" / "logs"
    n_atoma = n_logova = 0

    for md in sorted(personas.rglob("*.md")):
        meta, telo = _parse_atom_meta(md.read_text(encoding="utf-8"))
        aid = str(meta.get("id") or md.stem)
        atype = str(meta.get("type") or "reference")
        title = str(meta.get("title") or aid)
        txt = atom_to_node_text(domain, aid, atype, title, telo)
        ingest_text(connection, f"agent/{domain}/atom/{aid}", txt, embedder=embedder)
        n_atoma += 1

    for jsonl in sorted(logs.rglob("*.jsonl")):
        for line in jsonl.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            entry = json.loads(line)
            txt = log_entry_to_node_text(domain, entry)
            if txt is None:
                continue
            ingest_text(connection, f"agent/{domain}/log/{entry.get('log_id')}",
                        txt, embedder=embedder)
            n_logova += 1

    return {"domain": domain, "atoms": n_atoma, "logs": n_logova}


def ingest_all_cells(connection: Any, cells: dict, *, embedder: Embedder) -> dict:
    # `cells` = {domain: root}. IMPERIUM (bez Agenta) se ne prosleđuje.
    return {d: ingest_cell(connection, d, root, embedder=embedder)
            for d, root in cells.items()}
