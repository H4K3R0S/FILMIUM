# ==========          TRANSLATOR — JAVNI API          ==========
"""CORE integracija za prevod (deep-translator, EN ↔ SR podrazumevano).

Poziv iz bilo kog dela CORE-a:

    from integrations.translator import translate, translate_batch, TranslatorService

    sr = translate("A gripping thriller.")          # brzo, deljeni servis
    svc = TranslatorService(min_interval=2.0)        # sopstveno podešavanje
    opisi_sr = svc.translate_batch(engleski_opisi)   # gomila (FILMIUM, cron)
"""

from integrations.translator.base import (
    RateLimitError,
    TranslationError,
    TranslatorProvider,
)
from integrations.translator.google_provider import GoogleDeepProvider
from integrations.translator.rate_limiter import RateLimiter
from integrations.translator.service import (
    TranslatorService,
    get_service,
    translate,
    translate_batch,
)

__all__ = [
    "GoogleDeepProvider",
    "RateLimitError",
    "RateLimiter",
    "TranslationError",
    "TranslatorProvider",
    "TranslatorService",
    "get_service",
    "translate",
    "translate_batch",
]
