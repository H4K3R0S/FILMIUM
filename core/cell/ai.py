"""AI sloj ćelije: lokalna Ollama i jedno vezivanje modela iz `cell.json`.

CORE ima pun registar modela sa provajderima, ključevima i vidljivošću. Ćelija
ne nosi ništa od toga — nosi samo adresu lokalne Ollame i ime modela.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from core.ai.ollama_client import OllamaClient
from core.cell.manifest import CellManifest
from core.domains.filmium.curator import CuratorAnswer, CuratorService, MediaRetriever

_CURATOR_TIMEOUT_SECONDS = 60.0


@dataclass(frozen=True)
class CellModelBinding:
    """Model i adresa servisa za jednu ulogu."""

    model: str
    endpoint: str


class CellModelRegistry:
    """Najmanji registar modela: sve uloge vode na isti lokalni model."""

    def __init__(self, manifest: CellManifest) -> None:
        self._manifest = manifest

    def binding(self, domain: str, role: str) -> CellModelBinding:
        """
        Vraća vezivanje modela za traženu ulogu.

        Args:
            domain: Ime domena; u ćeliji postoji samo jedan, pa se ne koristi.
            role: Ime uloge, npr. `curator_model`.

        Returns:
            Model i adresa.

        Raises:
            LookupError: Ako model nije upisan u `cell.json`.
        """
        model = self._manifest.ai_curator_model

        if not model:
            raise LookupError(
                f"cell.json nema ai.curator_model za ulogu {role} ({domain})"
            )

        return CellModelBinding(model=model, endpoint=self._manifest.ai_endpoint)


# Isti tekst koji roditeljski `CuratorService.ask` vraća za praznu pretragu;
# ponovljen ovde jer se pri nepodešenom modelu roditelj ne poziva.
_EMPTY_LIBRARY_ANSWER = "U biblioteci nema naslova za ovu pretragu."


class CellCuratorService(CuratorService):
    """
    Kurator ćelije koji preživi nepodešen model.

    Svaka svežesklopljena ćelija ima `cell.json` sa `ai.curator_model = null`
    (nema ključeva, nema provajdera — samo prazno mesto za lokalnu Ollamu).
    Roditeljski `CuratorService.ask` bi tada pukao na `CellModelRegistry.binding`
    i probio API ćelije kao 500 — korisnik treba uputstvo kako da podesi model,
    a ne pad. Zato se manifest proverava PRE poziva roditelja: bez modela se
    biblioteka pretraži jednom i vraća uputstvo; sa modelom ide pravo na
    roditelja, BEZ hvatanja ijedne greške (ni `LookupError` iz drugog izvora
    ne sme da se maskira kao "nije podešeno").
    """

    def __init__(
        self,
        manifest: CellManifest,
        registry: CellModelRegistry,
        generate: Callable[..., str],
        retriever: MediaRetriever,
        *,
        role: str = "curator_model",
    ) -> None:
        # `CellModelRegistry` je duck-typed zamena za CORE `ModelRegistry` (ima `binding`).
        super().__init__(registry, generate, retriever, role=role)  # type: ignore[arg-type]
        self._manifest = manifest

    def ask(self, question: str, *, top_n: int = 10) -> CuratorAnswer:
        if self._manifest.ai_curator_model:
            return super().ask(question, top_n=top_n)

        items = self._retriever.retrieve(question, top_n=top_n)
        sources = [m.get("title", "") for m in items]
        if not items:
            return CuratorAnswer(answer=_EMPTY_LIBRARY_ANSWER, sources=[], is_fallback=True)

        listed = "; ".join(s for s in sources if s)
        answer = (
            "Kurator nije podešen za ovu ćeliju: u cell.json nedostaje "
            "ai.curator_model. Upišite ime lokalnog modela (i po potrebi "
            "ai.endpoint) u cell.json i ponovo pokrenite ćeliju."
        )
        if listed:
            answer += f" Najbliži naslovi: {listed}."

        return CuratorAnswer(answer=answer, sources=sources, is_fallback=True)


def build_cell_curator(
    manifest: CellManifest,
    retriever: MediaRetriever,
) -> CuratorService:
    """
    Sklapa Kuratora za ćeliju.

    Args:
        manifest: Manifest ćelije.
        retriever: Pretraživač biblioteke; `CuratorService` ga zove kao
            `retrieve(question, top_n=...)`.

    Returns:
        Kurator vezan za lokalnu Ollamu, otporan na nepodešen model
        (`CellCuratorService`).
    """
    registry = CellModelRegistry(manifest)
    client = OllamaClient(
        endpoint=manifest.ai_endpoint,
        timeout=_CURATOR_TIMEOUT_SECONDS,
    )

    def generate(
        model: str,
        prompt: str,
        *,
        system: str | None = None,
        fmt: str | None = None,
    ) -> str:
        return client.generate(model, prompt, system=system, fmt=fmt)

    return CellCuratorService(manifest, registry, generate, retriever)
