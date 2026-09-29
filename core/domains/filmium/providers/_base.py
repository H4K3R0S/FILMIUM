#!/usr/bin/env python3
"""Shared helpers for FILMIUM external provider clients.

These providers are KEYLESS. They must degrade gracefully: never raise from a
``fetch()`` call, return ``None`` on any failure (network, parse, missing lib),
and cache the RAW provider payload as JSON under
``<data>/filmium/external/<source>/<slug>.json`` so downstream code can diff it
the same way TMDB data is cached.
"""

from __future__ import annotations

import json
import re
import time
import unicodedata
from pathlib import Path
from typing import Any

# --- data dir resolution -------------------------------------------------
# Prefer the canonical CorePaths registry; fall back to the hardcoded FF path
# so the module still works if imported outside the app context.
try:  # pragma: no cover - depends on sys.path at runtime
    from core.foundation.paths import core_paths

    _DATA_DIR = Path(core_paths.data)
except Exception:  # pragma: no cover - fallback  # noqa: BLE001
    _DATA_DIR = Path("/run/media/kalima/FILMIUM/FILMIUM/data")

_EXTERNAL_DIR = _DATA_DIR / "filmium" / "external"

# --- module-level throttle store ----------------------------------------
_LAST_CALL: dict[str, float] = {}


def _throttle(source: str, seconds: float) -> None:
    """Sleep so successive calls to ``source`` are at least ``seconds`` apart.

    Uses a per-source last-call timestamp. Best-effort; never raises.
    """
    try:
        now = time.monotonic()
        last = _LAST_CALL.get(source)
        if last is not None:
            wait = seconds - (now - last)
            if wait > 0:
                time.sleep(wait)
        _LAST_CALL[source] = time.monotonic()
    except Exception:  # noqa: BLE001
        # Throttling must never break a fetch.
        _LAST_CALL[source] = time.monotonic()


def _slug(title: str, year: int | None = None) -> str:
    """Build an ascii, lowercase, filesystem-safe slug from title (+year)."""
    text = title or "unknown"
    # Strip accents -> ascii.
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    text = text.lower()
    text = re.sub(r"[^a-z0-9]+", "_", text).strip("_")
    if not text:
        text = "unknown"
    if year:
        text = f"{text}_{year}"
    return text


def _save_raw(source: str, slug: str, payload: Any) -> Path | None:
    """Persist the raw provider payload as JSON. Returns the path or None.

    Never raises: caching is best-effort and must not break a fetch.
    """
    try:
        target_dir = _EXTERNAL_DIR / source
        target_dir.mkdir(parents=True, exist_ok=True)
        path = target_dir / f"{slug}.json"
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, indent=2, ensure_ascii=False, default=str)
        return path
    except Exception:  # noqa: BLE001
        return None


_TAG_RE = re.compile(r"<[^>]+>")


def _strip_html(text: str | None) -> str | None:
    """Remove HTML tags and collapse whitespace. Returns None for falsy input."""
    if not text:
        return None
    try:
        cleaned = _TAG_RE.sub("", text)
        cleaned = re.sub(r"\s+", " ", cleaned).strip()
        return cleaned or None
    except Exception:  # noqa: BLE001
        return text


def _to_int(value: Any) -> int | None:
    """Best-effort int coercion (handles '73%', '1,234', None)."""
    if value is None:
        return None
    try:
        if isinstance(value, str):
            value = value.strip().rstrip("%").replace(",", "")
            if value == "":
                return None
        return int(float(value))
    except (TypeError, ValueError):
        return None


def _to_float(value: Any) -> float | None:
    """Best-effort float coercion."""
    if value is None:
        return None
    try:
        if isinstance(value, str):
            value = value.strip().rstrip("%").replace(",", "")
            if value == "":
                return None
        return float(value)
    except (TypeError, ValueError):
        return None
