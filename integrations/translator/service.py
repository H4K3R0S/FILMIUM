# ==========          TRANSLATOR SERVIS          ==========
"""Spaja provajder + rate limiter u jedan, lako pozivljiv servis.

Podrazumevan smer je EN → SR. Na privremeno odbijanje (RateLimitError)
ponavlja uz exponencijalni backoff do `max_retries`, pa propušta grešku.
"""

import logging

from integrations.translator.base import (
    RateLimitError,
    TranslationError,
    TranslatorProvider,
)
from integrations.translator.google_provider import GoogleDeepProvider
from integrations.translator.rate_limiter import RateLimiter

logger = logging.getLogger("core")


class TranslatorService:
    def __init__(
        self,
        provider: TranslatorProvider | None = None,
        rate_limiter: RateLimiter | None = None,
        default_source: str = "en",
        default_target: str = "sr",
        *,
        min_interval: float = 1.0,
        max_retries: int = 3,
    ) -> None:
        self.provider = provider or GoogleDeepProvider()
        self.limiter = rate_limiter or RateLimiter(
            min_interval=min_interval, max_retries=max_retries
        )
        self.default_source = default_source
        self.default_target = default_target

    # ==========          JEDAN TEKST          ==========

    def translate(
        self,
        text: str,
        source: str | None = None,
        target: str | None = None,
    ) -> str:
        """Prevede jedan tekst. Prazan/whitespace ulaz vraća se netaknut."""
        if text is None:
            raise TranslationError("text ne sme biti None")
        if not text.strip():
            return text

        source = source or self.default_source
        target = target or self.default_target

        attempt = 0
        while True:
            self.limiter.acquire()
            try:
                result = self.provider.translate(text, source, target)
                return result if result is not None else ""
            except RateLimitError:
                if attempt >= self.limiter.max_retries:
                    logger.error("Prevod odustao posle %d pokušaja", attempt)
                    raise
                attempt += 1
                logger.warning("Rate limit — backoff pokušaj %d", attempt)
                self.limiter.backoff_sleep(attempt)

    # ==========          VIŠE TEKSTOVA          ==========

    def translate_batch(
        self,
        texts: list[str],
        source: str | None = None,
        target: str | None = None,
    ) -> list[str]:
        """Prevede listu tekstova, razmaknuto kroz rate limiter.

        Koristi FILMIUM (gomila filmskih opisa) i budući cron.
        """
        return [self.translate(t, source, target) for t in texts]

    # ==========          NASLOV + OPIS (JEDAN POZIV)          ==========

    _PAIR_DELIM = "\n⟐⟐⟐\n"

    def translate_pair(
        self,
        title: str,
        overview: str,
        *,
        target: str | None = None,
    ) -> tuple[str, str]:
        """Prevede naslov i opis jednim pozivom. Prazni delovi ostaju prazni.

        Naslov i opis se spoje jedinstvenim delimiterom, pošalje se jedan
        prevod, pa se rezultat rasparča. Ako split ne uspe (prevodilac je
        pojeo delimiter), pada na dva odvojena poziva.
        """
        title = title or ""
        overview = overview or ""
        if not title.strip() and not overview.strip():
            return title, overview

        joined = f"{title}{self._PAIR_DELIM}{overview}"
        translated = self.translate(joined, target=target)
        parts = translated.split(self._PAIR_DELIM.strip())
        if len(parts) == 2:
            return parts[0].strip(), parts[1].strip()

        new_title = (
            self.translate(title, target=target) if title.strip() else title
        )
        new_overview = (
            self.translate(overview, target=target)
            if overview.strip()
            else overview
        )
        return new_title, new_overview


# ==========          SINGLETON I PREČICA          ==========

_default_service: TranslatorService | None = None


def get_service() -> TranslatorService:
    """Vrati deljeni servis sa podrazumevanim podešavanjima (EN → SR)."""
    global _default_service
    if _default_service is None:
        _default_service = TranslatorService()
    return _default_service


def translate(
    text: str,
    source: str | None = None,
    target: str | None = None,
) -> str:
    """Brza prečica: prevede jedan tekst deljenim servisom (EN → SR)."""
    return get_service().translate(text, source, target)


def translate_batch(
    texts: list[str],
    source: str | None = None,
    target: str | None = None,
) -> list[str]:
    """Brza prečica za listu tekstova deljenim servisom."""
    return get_service().translate_batch(texts, source, target)
