from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import psycopg

from core.rag.retrieve import search_domain


@dataclass(frozen=True)
class GoldItem:
    query: str
    expect_substr: str


def load_goldset(path: Path) -> list[GoldItem]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return [GoldItem(d["query"], d["expect_substr"]) for d in data]


def _pogodak(cvorovi, substr: str) -> bool:
    for n in cvorovi:
        haystack = f"{n.node_id} {n.source_path or ''}"
        if substr in haystack:
            return True
    return False


def recall_at_k(connection: psycopg.Connection, gold: list[GoldItem], *,
                embedder, k: int = 10) -> float:
    if not gold:
        return 0.0
    pogodaka = 0
    for stavka in gold:
        cvorovi = search_domain(connection, stavka.query, None,
                                embedder=embedder, k=k)
        if _pogodak(cvorovi, stavka.expect_substr):
            pogodaka += 1
    return pogodaka / len(gold)
