# ==========          TRANSLATOR — INTERFEJS I IZUZECI          ==========
"""Ugovor za provajdere prevoda i zajednički izuzeci.

Svaki konkretan provajder (Google, kasnije lokalni Ollama...) implementira
`TranslatorProvider.translate`. Servis radi samo protiv ovog interfejsa,
pa se provajder menja bez diranja pozivaoca.
"""

from abc import ABC, abstractmethod

# ==========          IZUZECI          ==========

class TranslationError(Exception):
    """Prevod nije uspeo iz trajnog razloga (nevalidan ulaz, nepodržan jezik)."""


class RateLimitError(TranslationError):
    """Servis je privremeno odbio zahtev (npr. 429). Vredi pokušati kasnije."""


# ==========          INTERFEJS PROVAJDERA          ==========

class TranslatorProvider(ABC):
    """Apstraktni provajder prevoda: jedan tekst → prevedeni tekst."""

    @abstractmethod
    def translate(self, text: str, source: str, target: str) -> str:
        """Prevede `text` sa `source` na `target` jezik.

        Diže `RateLimitError` na privremeno odbijanje (429), a
        `TranslationError` na trajne greške (nevalidan ulaz/jezik).
        """
        raise NotImplementedError
