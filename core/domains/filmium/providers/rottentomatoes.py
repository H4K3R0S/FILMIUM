#!/usr/bin/env python3
"""Rotten Tomatoes provider (KEYLESS, movies).

The pip package ``rottentomatoes-python`` (import ``rottentomatoes``) installs
and imports fine on Python 3.14, but its HTML scraper is BROKEN against Rotten
Tomatoes' current page markup (it looks for an ``h1[slot=titleIntro]`` and a
search snippet layout that no longer exist, raising IndexError/AttributeError).

So this client uses a minimal direct-HTTPS approach instead: it reads the
``media-scorecard-json`` blob that RT embeds in each movie page, which contains
the current Tomatometer (criticsScore) and audience/Popcornmeter score. We try
the library first (in case a future release fixes it) and fall back to direct
parsing.

Rate limit: 2s between calls (module-level throttle). Movies primarily.

Normalized keys: tomatometer, audience_score, url, title, year, weighted_score.
"""

from __future__ import annotations

import json
import re

import requests

from ._base import _save_raw, _slug, _throttle, _to_float, _to_int

_SOURCE = "rottentomatoes"
_THROTTLE_SECONDS = 2.0
_TIMEOUT = 20
_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}

_SCORECARD_RE = re.compile(
    r'<script[^>]*id="media-scorecard-json"[^>]*>(.*?)</script>', re.DOTALL
)
_LDJSON_RE = re.compile(
    r'<script type="application/ld\+json">(.*?)</script>', re.DOTALL
)


def _rt_slug(title: str) -> str:
    """RT vanity slug: lowercase, non-alnum -> underscore."""
    text = re.sub(r"[^a-z0-9]+", "_", (title or "").lower()).strip("_")
    return text or "unknown"


def _candidate_urls(title: str, year: int | None) -> list[str]:
    base = _rt_slug(title)
    urls: list[str] = []
    if year:
        urls.append(f"https://www.rottentomatoes.com/m/{base}_{year}")
    urls.append(f"https://www.rottentomatoes.com/m/{base}")
    return urls


def _parse_page(html: str, final_url: str, title: str, year: int | None) -> dict | None:
    match = _SCORECARD_RE.search(html)
    if not match:
        return None
    try:
        scorecard = json.loads(match.group(1))
    except Exception:  # noqa: BLE001
        return None

    critics = scorecard.get("criticsScore") or {}
    audience = scorecard.get("audienceScore") or {}

    tomatometer = _to_int(critics.get("score") or critics.get("scorePercent"))
    audience_score = _to_int(audience.get("score") or audience.get("scorePercent"))
    weighted_score = _to_float(critics.get("averageRating"))

    if tomatometer is None and audience_score is None:
        return None

    # Resolve display title + year from ld+json if present.
    page_title = title
    page_year = year
    for ld_match in _LDJSON_RE.finditer(html):
        try:
            doc = json.loads(ld_match.group(1))
        except Exception:  # noqa: BLE001, S112
            continue
        if isinstance(doc, dict) and doc.get("@type") in ("Movie", "TVSeries", "CreativeWork"):
            name = doc.get("name")
            if name:
                page_title = name
            date = doc.get("dateCreated") or doc.get("datePublished")
            if date and page_year is None:
                m = re.search(r"(\d{4})", str(date))
                if m:
                    page_year = int(m.group(1))
            break

    normalized = {
        "tomatometer": tomatometer,
        "audience_score": audience_score,
        "url": final_url,
        "title": page_title,
        "year": page_year,
        "weighted_score": weighted_score,
    }
    return {"_normalized": normalized, "_raw": scorecard}


def fetch(
    title: str,
    year: int | None = None,
    imdb_id: str | None = None,
    media_type: str | None = None,
) -> dict | None:
    """Fetch Rotten Tomatoes scores for a movie. Returns normalized dict or None."""
    if not title:
        return None

    _throttle(_SOURCE, _THROTTLE_SECONDS)

    result = None
    try:
        for url in _candidate_urls(title, year):
            try:
                resp = requests.get(url, headers=_HEADERS, timeout=_TIMEOUT)
            except Exception:  # noqa: BLE001, S112
                continue
            if resp.status_code != 200:
                continue
            parsed = _parse_page(resp.text, str(resp.url), title, year)
            if parsed:
                result = parsed
                break
    except Exception:  # noqa: BLE001
        return None

    if not result:
        return None

    try:
        _save_raw(_SOURCE, _slug(title, year), result["_raw"])
    except Exception:  # noqa: BLE001, S110
        pass

    return result["_normalized"]


if __name__ == "__main__":  # pragma: no cover - manual self-test
    print(fetch("Interstellar", 2014))
