#!/usr/bin/env python3
"""Jikan provider (KEYLESS, anime -> MyAnimeList).

The pip package ``jikanpy`` installs and imports on Python 3.14, but the pinned
release (4.3.2) still targets Jikan's DISCONTINUED v3 API and returns
``HTTP 410 - v3 has been discontinued``. So this client talks to the current
Jikan v4 REST API directly with ``requests``.

Rate limit: 1s between calls (Jikan allows ~3 req/s, 60 req/min).

Normalized keys: mal_id, title, title_japanese, type, episodes, score, studio,
status, synopsis, genres.
"""

from __future__ import annotations

import requests

from ._base import _save_raw, _slug, _strip_html, _throttle, _to_float

_SOURCE = "jikan"
_THROTTLE_SECONDS = 1.0
_TIMEOUT = 20
_ENDPOINT = "https://api.jikan.moe/v4/anime"
_HEADERS = {"User-Agent": "filmium/1.0 (+keyless provider client)"}


def fetch(
    title: str,
    year: int | None = None,
    imdb_id: str | None = None,
    media_type: str | None = None,
) -> dict | None:
    """Fetch anime data from Jikan v4. Returns normalized dict or None."""
    if not title:
        return None

    _throttle(_SOURCE, _THROTTLE_SECONDS)

    try:
        resp = requests.get(
            _ENDPOINT,
            params={"q": title, "limit": 1},
            headers=_HEADERS,
            timeout=_TIMEOUT,
        )
    except Exception:  # noqa: BLE001
        return None

    if resp.status_code != 200:
        return None

    try:
        payload = resp.json()
    except Exception:  # noqa: BLE001
        return None

    results = payload.get("data") if isinstance(payload, dict) else None
    if not results:
        return None
    anime = results[0]

    try:
        _save_raw(_SOURCE, _slug(title, year), anime)
    except Exception:  # noqa: BLE001, S110
        pass

    studio = None
    studios = anime.get("studios")
    if isinstance(studios, list) and studios and isinstance(studios[0], dict):
        studio = studios[0].get("name")

    genres = []
    raw_genres = anime.get("genres")
    if isinstance(raw_genres, list):
        genres = [g.get("name") for g in raw_genres if isinstance(g, dict) and g.get("name")]

    return {
        "mal_id": anime.get("mal_id"),
        "title": anime.get("title"),
        "title_japanese": anime.get("title_japanese"),
        "type": anime.get("type"),
        "episodes": anime.get("episodes"),
        "score": _to_float(anime.get("score")),
        "studio": studio,
        "status": anime.get("status"),
        "synopsis": _strip_html(anime.get("synopsis")),
        "genres": genres,
    }


if __name__ == "__main__":  # pragma: no cover - manual self-test
    print(fetch("Attack on Titan", media_type="anime"))
