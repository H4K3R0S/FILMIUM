# ==========          RATE LIMITER          ==========
"""Zaštita od bloka (429) pri nezvaničnom Google Translate pozivu.

Dve odgovornosti:
  1. Razmak između zahteva — bar `min_interval` sekundi (throttle).
  2. Raspored ponovnih pokušaja — exponencijalni backoff na privremenu grešku.

Sat i `sleep` se ubrizgavaju radi determinističkih testova (bez čekanja).
"""

import time
from collections.abc import Callable


class RateLimiter:
    def __init__(
        self,
        min_interval: float = 1.0,
        max_retries: int = 3,
        backoff_base: float = 1.0,
        backoff_factor: float = 2.0,
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if min_interval < 0:
            raise ValueError("min_interval ne sme biti negativan")
        if max_retries < 0:
            raise ValueError("max_retries ne sme biti negativan")
        self.min_interval = min_interval
        self.max_retries = max_retries
        self.backoff_base = backoff_base
        self.backoff_factor = backoff_factor
        self._sleep = sleep
        self._clock = clock
        self._last: float | None = None

    # ==========          THROTTLE          ==========

    def acquire(self) -> None:
        """Blokira dok ne prođe `min_interval` od prethodnog poziva."""
        if self._last is not None:
            elapsed = self._clock() - self._last
            wait = self.min_interval - elapsed
            if wait > 0:
                self._sleep(wait)
        self._last = self._clock()

    # ==========          BACKOFF          ==========

    def backoff_delay(self, attempt: int) -> float:
        """Kašnjenje pre `attempt`-tog ponovnog pokušaja (attempt počinje od 1)."""
        return self.backoff_base * (self.backoff_factor ** (attempt - 1))

    def backoff_sleep(self, attempt: int) -> None:
        self._sleep(self.backoff_delay(attempt))
