# ========== KURATOR RETRIEVER (lokalni RAG bez ChromaDB) ==========
# Rangira postojeće FILMIUM naslove po preklapanju ključnih reči sa upitom i
# vraća top-N kao kompaktne metapodatke (kontekst za LLM). Ne učitava celu bazu
# u model — samo najrelevantnije. ChromaDB nije u 0.1, pa se koristi lokalni
# tekstualni skor nad postojećim podacima.
from __future__ import annotations

import re
from collections.abc import Callable, Sequence
from typing import Any

# list_provider() -> sekvenca MediaItem-a (npr. MediaRepository.list_all)
ListProvider = Callable[[], Sequence[Any]]

_STOPWORDS = frozenset({
    "i", "a", "u", "o", "za", "se", "je", "na", "sa", "od", "do", "the", "of",
    "mi", "me", "neki", "nešto", "film", "filmovi", "serija", "serije", "hoću",
    "preporuci", "preporuka", "gledati",
})

# Polje -> težina u skoru.
_WEIGHTS: dict[str, float] = {
    "title": 3.0, "english_title": 2.0, "genres": 2.0, "keywords": 2.0,
    "cast_names": 1.0, "director": 1.0, "studio": 1.0, "collection": 1.0,
    "notes": 1.0, "english_description": 1.0,
}


def _tokens(text: str) -> set[str]:
    return {
        t for t in re.split(r"[^0-9a-zA-ZčćžšđčČĆŽŠĐ]+", text.lower())
        if len(t) > 2 and t not in _STOPWORDS
    }


def _field_text(item: Any, field: str) -> str:
    value = getattr(item, field, None)
    if value is None:
        return ""
    if isinstance(value, (tuple, list)):
        return " ".join(str(v) for v in value)
    return str(value)


def _score(item: Any, query_tokens: set[str]) -> float:
    total = 0.0
    for field, weight in _WEIGHTS.items():
        field_tokens = _tokens(_field_text(item, field))
        total += weight * len(query_tokens & field_tokens)
    return total


def _to_metadata(item: Any) -> dict:
    return {
        "media_id": getattr(item, "id", None),
        "title": getattr(item, "title", ""),
        "release_year": getattr(item, "release_year", None),
        "genres": list(getattr(item, "genres", ()) or ()),
        "director": getattr(item, "director", None),
        "cast": list(getattr(item, "cast_names", ()) or ())[:5],
        "rating": getattr(item, "rating", None),
        "overview": getattr(item, "english_description", None)
        or getattr(item, "notes", None) or "",
    }


# ========== RETRIEVER ==========
class MediaRetriever:
    """Vraća top-N relevantnih naslova za tekstualni upit."""

    def __init__(self, list_provider: ListProvider) -> None:
        self._list_provider = list_provider

    def retrieve(self, query: str, top_n: int = 10) -> list[dict]:
        items = list(self._list_provider())
        query_tokens = _tokens(query)

        scored = [(item, _score(item, query_tokens)) for item in items]
        relevant = [pair for pair in scored if pair[1] > 0]
        relevant.sort(key=lambda pair: pair[1], reverse=True)

        # Ako ništa ne pogađa upit, uzmi najbolje ocenjene kao zdrav fallback.
        if not relevant:
            by_rating = sorted(
                items, key=lambda i: (getattr(i, "rating", None) or 0), reverse=True,
            )
            return [_to_metadata(i) for i in by_rating[:top_n]]

        return [_to_metadata(item) for item, _ in relevant[:top_n]]
