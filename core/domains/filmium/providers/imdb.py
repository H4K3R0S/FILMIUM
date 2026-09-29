#!/usr/bin/env python3
"""IMDb provider (KEYLESS, movies + series).

Primary path: the pip package ``cinemagoer`` (import ``imdb``,
``imdb.Cinemagoer()``). NOTE: cinemagoer 2026.8.20 on Python 3.14 ships ONLY the
``s3`` access system (the old ``http`` web-scraping backend was removed); ``s3``
needs a locally built SQLite dataset. If that dataset is absent, cinemagoer
raises and we fall back.

Fallback (minimal, keyless): given an ``imdb_id`` (``tt#######``) we read the
IMDb title page's ``application/ld+json`` block for rating / votes / genres /
plot. When no id is supplied we first resolve one via IMDb's public suggestion
endpoint (``sg.media-imdb.com``). Everything degrades to ``None`` gracefully.

Rate limit: 1s between calls.

Normalized keys: imdb_id, title, year, rating, votes, genres, plot.
"""

from __future__ import annotations

import json
import re
from urllib.parse import quote

import requests

from ._base import _save_raw, _slug, _strip_html, _throttle, _to_float, _to_int

_SOURCE = "imdb"
_THROTTLE_SECONDS = 1.0
_TIMEOUT = 20
_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}
_SUGGEST_HOST = "https://sg.media-imdb.com/suggestion/t"
_LDJSON_RE = re.compile(
    r'<script type="application/ld\+json">(.*?)</script>', re.DOTALL
)


def _normalize_id(imdb_id: str | None) -> str | None:
    if not imdb_id:
        return None
    imdb_id = imdb_id.strip()
    if re.fullmatch(r"tt\d{6,}", imdb_id):
        return imdb_id
    if re.fullmatch(r"\d{6,}", imdb_id):
        return "tt" + imdb_id
    return None


def _suggest(title: str) -> dict | None:
    """Resolve a title to {id, title, year} via IMDb's suggestion endpoint."""
    try:
        url = f"{_SUGGEST_HOST}/{quote(title.lower())}.json"
        resp = requests.get(url, headers={"User-Agent": _HEADERS["User-Agent"]}, timeout=_TIMEOUT)
        if resp.status_code != 200:
            return None
        entries = resp.json().get("d") or []
        for entry in entries:
            ent_id = entry.get("id", "")
            if isinstance(ent_id, str) and ent_id.startswith("tt"):
                return {
                    "id": ent_id,
                    "title": entry.get("l"),
                    "year": entry.get("y"),
                    "_raw": entry,
                }
    except Exception:  # noqa: BLE001
        return None
    return None


def _from_cinemagoer(imdb_id: str) -> dict | None:
    """Try the cinemagoer library. Returns normalized dict or None."""
    try:
        import logging

        import imdb as _imdblib

        logging.getLogger("imdbpy").disabled = True
        ia = _imdblib.Cinemagoer()  # defaults to whatever backend is available
        movie = ia.get_movie(imdb_id[2:])  # strip 'tt'
        if not movie:
            return None
        rating = _to_float(movie.get("rating"))
        if rating is None:
            return None  # no useful data -> let fallback try
        plot = movie.get("plot outline")
        if not plot and movie.get("plot"):
            plot = movie["plot"][0] if isinstance(movie["plot"], list) else movie["plot"]
        return {
            "imdb_id": imdb_id,
            "title": movie.get("title"),
            "year": movie.get("year"),
            "rating": rating,
            "votes": _to_int(movie.get("votes")),
            "genres": movie.get("genres") if isinstance(movie.get("genres"), list) else [],
            "plot": _strip_html(str(plot).split(". ")[0] + "." if plot else None),
            "_raw": {"source": "cinemagoer", "title": movie.get("title"), "rating": rating},
        }
    except Exception:  # noqa: BLE001
        return None


def _from_page(imdb_id: str) -> dict | None:
    """Scrape rating/votes/genres/plot from the IMDb title page ld+json."""
    try:
        url = f"https://www.imdb.com/title/{imdb_id}/"
        resp = requests.get(url, headers=_HEADERS, timeout=_TIMEOUT)
        if resp.status_code != 200:
            return None
        for match in _LDJSON_RE.finditer(resp.text):
            try:
                doc = json.loads(match.group(1))
            except Exception:  # noqa: BLE001, S112
                continue
            if not isinstance(doc, dict):
                continue
            agg = doc.get("aggregateRating") or {}
            genre = doc.get("genre")
            if isinstance(genre, str):
                genre = [genre]
            year = None
            date = doc.get("datePublished")
            if date:
                m = re.search(r"(\d{4})", str(date))
                if m:
                    year = int(m.group(1))
            return {
                "imdb_id": imdb_id,
                "title": doc.get("name"),
                "year": year,
                "rating": _to_float(agg.get("ratingValue")),
                "votes": _to_int(agg.get("ratingCount")),
                "genres": genre if isinstance(genre, list) else [],
                "plot": _strip_html(doc.get("description")),
                "_raw": doc,
            }
    except Exception:  # noqa: BLE001
        return None
    return None


def fetch(
    title: str,
    year: int | None = None,
    imdb_id: str | None = None,
    media_type: str | None = None,
) -> dict | None:
    """Fetch IMDb data. Returns normalized dict or None."""
    _throttle(_SOURCE, _THROTTLE_SECONDS)

    resolved_id = _normalize_id(imdb_id)
    suggestion = None

    if resolved_id is None and title:
        suggestion = _suggest(title)
        if suggestion:
            resolved_id = suggestion["id"]

    if resolved_id is None:
        return None

    # 1) library, 2) direct page scrape.
    result = _from_cinemagoer(resolved_id) or _from_page(resolved_id)

    # 3) if rating could not be fetched (e.g. IMDb blocked the request), still
    #    return the identity we resolved via the suggestion API, so downstream
    #    has the id/title/year even when the rating is unavailable.
    if result is None:
        if suggestion is None and title:
            suggestion = _suggest(title)
        if suggestion is None:
            return None
        result = {
            "imdb_id": resolved_id,
            "title": suggestion.get("title") or title,
            "year": suggestion.get("year") or year,
            "rating": None,
            "votes": None,
            "genres": [],
            "plot": None,
            "_raw": suggestion.get("_raw", {}),
        }

    if year is not None and not result.get("year"):
        result["year"] = year

    try:
        _save_raw(_SOURCE, _slug(title or resolved_id, result.get("year") or year), result["_raw"])
    except Exception:  # noqa: BLE001, S110
        pass

    result.pop("_raw", None)
    return result


if __name__ == "__main__":  # pragma: no cover - manual self-test
    print(fetch("Interstellar", 2014, imdb_id="tt0816692"))
