# ========== PREPORUKA (taste → kandidati → AI curira) ==========
# Kombinuje dva sloja:
#   (2) UKUS: iz favorita (težina 2) + odgledanih (težina 1) izvuče omiljene
#       žanrove/režisere; kandidate boduje po preklapanju s tim ukusom.
#   (3) AI CURIRA: model iz bodovanog poola izabere konačnih ~N (opciono; ako
#       nema modela ili on zataji, fallback = top po skoru).
# Iz preporuke se ISKLJUČUJU već gledani/favoriti (predlažemo NOVO).
from __future__ import annotations

from collections import Counter
from collections.abc import Callable, Sequence
from typing import Any

ListProvider = Callable[[], Sequence[Any]]
# curate(pool, req) -> lista media_id-jeva koje AI preporučuje (podskup poola).
Curate = Callable[[Sequence[Any], dict], Sequence[int]]

_POOL_MULTIPLIER = 3
_POOL_MIN = 40


def _val(x: Any) -> Any:
    """Vrednost enum-a ili sam objekat (media_type/watch_status mogu biti enum ili str)."""
    return getattr(x, "value", x)


def _is_completed(item: Any) -> bool:
    return str(_val(getattr(item, "watch_status", ""))) == "completed"


class Recommender:
    """Preporuka naslova iz biblioteke po ukusu + (opciono) AI kuriranje."""

    def __init__(self, list_provider: ListProvider, curate: Curate | None = None) -> None:
        self._list_provider = list_provider
        self._curate = curate

    def recommend(
        self,
        *,
        genre: str | None = None,
        media_type: str | None = None,
        mood: str | None = None,
        limit: int = 20,
    ) -> list[int]:
        items = list(self._list_provider())
        if not items:
            return []

        # (2) UKUS: omiljeni žanrovi/režiseri iz favorita (×2) + odgledanih (×1).
        genre_score: Counter[str] = Counter()
        director_score: Counter[str] = Counter()
        seen: set[int] = set()  # već gledani/favoriti → isključi iz preporuke
        for m in items:
            fav = bool(getattr(m, "is_favorite", False))
            done = _is_completed(m)
            if not (fav or done):
                continue
            seen.add(getattr(m, "id", None))
            weight = 2 if fav else 1
            for g in getattr(m, "genres", ()) or ():
                genre_score[g] += weight
            director = getattr(m, "director", None)
            if director:
                director_score[director] += weight

        # Kandidati: NOVI naslovi (ne gledani), uz opcioni žanr/tip filter.
        scored: list[tuple[int, int, Any]] = []
        for m in items:
            mid = getattr(m, "id", None)
            if mid in seen:
                continue
            if media_type and str(_val(getattr(m, "media_type", None))) != media_type:
                continue
            genres = tuple(getattr(m, "genres", ()) or ())
            if genre and genre not in genres:
                continue
            score = sum(genre_score[g] for g in genres)
            score += director_score.get(getattr(m, "director", None), 0)
            scored.append((score, int(getattr(m, "release_year", 0) or 0), m))

        # Najbolji ukus gore; noviji kao tie-break.
        scored.sort(key=lambda t: (t[0], t[1]), reverse=True)
        pool = [m for _, _, m in scored[: max(limit * _POOL_MULTIPLIER, _POOL_MIN)]]
        if not pool:
            return []

        # (3) AI CURIRA konačnih ~limit iz poola (ako je model dostupan).
        if self._curate is not None:
            req = {"genre": genre, "media_type": media_type, "mood": mood, "limit": limit}
            try:
                picks = list(self._curate(pool, req))
            except Exception:  # noqa: BLE001 — AI zataji → fallback na skor
                picks = []
            pool_ids = {getattr(m, "id", None) for m in pool}
            ids = [i for i in picks if i in pool_ids]
            if ids:
                return ids[:limit]

        # Fallback: top po skoru ukusa.
        return [getattr(m, "id", None) for m in pool[:limit]]
