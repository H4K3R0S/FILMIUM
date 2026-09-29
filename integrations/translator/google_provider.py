# ==========          GOOGLE (deep-translator) PROVAJDER          ==========
"""Provajder prevoda preko biblioteke `deep-translator` (bez API ključa).

Mapira izuzetke biblioteke na CORE izuzetke:
  - privremeno (429/mreža/server) → RateLimitError
  - trajno (nevalidan ulaz/jezik)  → TranslationError
"""

import logging

from deep_translator import GoogleTranslator
from deep_translator import exceptions as dt_exc

from integrations.translator.base import (
    RateLimitError,
    TranslationError,
    TranslatorProvider,
)

logger = logging.getLogger("core")

# Izuzeci biblioteke koji znače "pokušaj kasnije".
_TRANSIENT = (
    dt_exc.TooManyRequests,
    dt_exc.RequestError,
    dt_exc.ServerException,
)


class GoogleDeepProvider(TranslatorProvider):
    """GoogleTranslator omotač. Instanca se pravi po pozivu jer par
    (source, target) određuje prevod, a jeftina je za kreiranje."""

    def translate(self, text: str, source: str, target: str) -> str:
        try:
            return GoogleTranslator(source=source, target=target).translate(text)
        except _TRANSIENT as exc:
            logger.warning("Prevod privremeno odbijen (%s): %s", source, target)
            raise RateLimitError(str(exc)) from exc
        except dt_exc.BaseError as exc:
            raise TranslationError(str(exc)) from exc
