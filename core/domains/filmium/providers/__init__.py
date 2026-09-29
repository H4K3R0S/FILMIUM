"""FILMIUM external, KEYLESS provider clients.

Each provider module exposes a stable::

    fetch(title: str, year: int | None = None, imdb_id: str | None = None,
          media_type: str | None = None) -> dict | None

Returns a normalized dict of fields, or ``None`` if not found / library
missing / network error (never raises). The raw provider response is cached to
``<data>/filmium/external/<source>/<slug>.json``.

Providers:
    rottentomatoes  - movies (Tomatometer / audience score)
    tvmaze          - series / TV
    jikan           - anime (MyAnimeList via Jikan v4)
    imdb            - movies + series (rating / votes)
"""

from . import imdb, jikan, rottentomatoes, tvmaze

__all__ = ["imdb", "jikan", "rottentomatoes", "tvmaze"]
