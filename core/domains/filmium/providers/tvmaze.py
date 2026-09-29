#!/usr/bin/env python3
"""TVmaze provider (KEYLESS, series / TV).

Uses the public TVmaze REST API (no library required). The endpoint below fixes
the typo in the user's doc: the correct path is ``/singlesearch/shows`` with the
``embed=episodes`` query so we can count episodes in a single request.

Rate limit: 0.5s between calls (TVmaze allows ~20 requests / 10 seconds).

Normalized keys: tvmaze_id, name, rating, network, status, premiered, genres,
summary, episode_count.
"""

from __future__ import annotations

import requests

from ._base import _save_raw, _slug, _strip_html, _throttle, _to_float

_SOURCE = "tvmaze"
_THROTTLE_SECONDS = 0.5
_TIMEOUT = 20
_ENDPOINT = "https://api.tvmaze.com/singlesearch/shows"
_HEADERS = {"User-Agent": "filmium/1.0 (+keyless provider client)"}


def fetch(
    title: str,
    year: int | None = None,
    imdb_id: str | None = None,
    media_type: str | None = None,
) -> dict | None:
    """Fetch TVmaze show data. Returns normalized dict or None."""
    if not title:
        return None

    _throttle(_SOURCE, _THROTTLE_SECONDS)

    try:
        resp = requests.get(
            _ENDPOINT,
            params={"q": title, "embed": "episodes"},
            headers=_HEADERS,
            timeout=_TIMEOUT,
        )
    except Exception:  # noqa: BLE001
        return None

    if resp.status_code != 200:
        # 404 = no match; anything else = transient/network.
        return None

    try:
        data = resp.json()
    except Exception:  # noqa: BLE001
        return None

    if not isinstance(data, dict) or not data.get("id"):
        return None

    try:
        _save_raw(_SOURCE, _slug(title, year), data)
    except Exception:  # noqa: BLE001, S110
        pass

    rating = None
    if isinstance(data.get("rating"), dict):
        rating = _to_float(data["rating"].get("average"))

    network = None
    if isinstance(data.get("network"), dict) and data["network"].get("name"):
        network = data["network"]["name"]
    elif isinstance(data.get("webChannel"), dict) and data["webChannel"].get("name"):
        network = data["webChannel"]["name"]

    episodes = []
    embedded = data.get("_embedded")
    if isinstance(embedded, dict) and isinstance(embedded.get("episodes"), list):
        episodes = embedded["episodes"]

    genres = data.get("genres") if isinstance(data.get("genres"), list) else []

    return {
        "tvmaze_id": data.get("id"),
        "name": data.get("name"),
        "rating": rating,
        "network": network,
        "status": data.get("status"),
        "premiered": data.get("premiered"),
        "genres": genres,
        "summary": _strip_html(data.get("summary")),
        "episode_count": len(episodes) if episodes else None,
    }


if __name__ == "__main__":  # pragma: no cover - manual self-test
    print(fetch("Breaking Bad", media_type="series"))
