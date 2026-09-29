from __future__ import annotations


def rrf_fuse(rankings: list[list[str]], *, k: int = 60) -> list[tuple[str, float]]:
    """Reciprocal Rank Fusion vise rangiranih lista id-eva."""
    skor: dict[str, float] = {}
    for lista in rankings:
        for rank, ident in enumerate(lista, start=1):
            skor[ident] = skor.get(ident, 0.0) + 1.0 / (k + rank)
    return sorted(skor.items(), key=lambda par: par[1], reverse=True)
