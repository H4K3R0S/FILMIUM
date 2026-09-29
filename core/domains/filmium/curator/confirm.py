# ========== POTVRDA UPISA (kratkoživući tokeni) ==========
# Upis (izmena/čuvanje) se ne izvršava iz `handle`; izda se token vezan za
# tačne parametre koje je korisnik video u pregledu. `take` je jednokratno i
# poštuje TTL — potvrda ne može izvršiti druge parametre niti se ponoviti.
from __future__ import annotations

import secrets
import time
from collections.abc import Callable
from dataclasses import dataclass


@dataclass
class _Entry:
    intent: str
    params: dict
    expires_at: float


class ConfirmStore:
    """Tokeni potvrde u procesu, sa istekom."""

    def __init__(
        self,
        ttl_seconds: float = 180.0,
        now: Callable[[], float] = time.monotonic,
    ) -> None:
        self._ttl = ttl_seconds
        self._now = now
        self._entries: dict[str, _Entry] = {}

    def issue(self, intent: str, params: dict) -> str:
        token = secrets.token_urlsafe(16)
        self._entries[token] = _Entry(
            intent=intent, params=dict(params), expires_at=self._now() + self._ttl
        )
        return token

    def take(self, token: str) -> tuple[str, dict]:
        entry = self._entries.pop(token, None)
        if entry is None:
            raise KeyError("Nepoznat ili već iskorišćen token.")
        if self._now() > entry.expires_at:
            raise KeyError("Token je istekao.")
        return entry.intent, entry.params
