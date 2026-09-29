# ========== FILMIUM KURATOR (RAG servis) ==========
# Kognitivni sloj nad FILMIUM bazom: uzme top-N relevantnih naslova (retriever),
# spakuje ih kao kontekst i traži od lokalnog modela (qwen2.5) ekspertsku
# preporuku na srpskom. Ako model nije dostupan, vraća uredan spisak naslova.
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

from core.ai.model_registry import ModelRegistry
from core.ai.ollama_client import OllamaUnavailable
from core.domains.filmium.curator.retriever import MediaRetriever

# generate(model, prompt, *, system=None, fmt=None) -> str
Generate = Callable[..., str]

SYSTEM_PROMPT = (
    "Ti si FILMIUM Kurator, ekspert za film. Odgovaraj isključivo na srpskom "
    "jeziku, prirodno i sažeto. Preporuke daj SAMO iz ponuđenog konteksta "
    "(korisnikova biblioteka); ne izmišljaj naslove kojih nema."
)


@dataclass
class CuratorAnswer:
    answer: str
    sources: list[str] = field(default_factory=list)
    is_fallback: bool = False


def _format_context(items: list[dict]) -> str:
    lines = []
    for i, meta in enumerate(items, start=1):
        genres = ", ".join(meta.get("genres", [])) or "—"
        year = meta.get("release_year") or "—"
        director = meta.get("director") or "—"
        overview = (meta.get("overview") or "").strip()
        if len(overview) > 240:
            overview = overview[:240] + "…"
        lines.append(
            f"{i}. {meta.get('title', '?')} ({year}) · žanr: {genres} · "
            f"režija: {director}\n   {overview}"
        )
    return "\n".join(lines)


# ========== KURATOR ==========
class CuratorService:
    """RAG preporuka nad korisnikovom FILMIUM bibliotekom."""

    def __init__(self, registry: ModelRegistry, generate: Generate,
                 retriever: MediaRetriever, *, role: str = "curator_model") -> None:
        self._registry = registry
        self._generate = generate
        self._retriever = retriever
        self._role = role

    def ask(self, question: str, *, top_n: int = 10) -> CuratorAnswer:
        items = self._retriever.retrieve(question, top_n=top_n)
        sources = [m.get("title", "") for m in items]

        if not items:
            return CuratorAnswer(
                answer="U biblioteci nema naslova za ovu pretragu.",
                sources=[], is_fallback=True,
            )

        binding = self._registry.binding("Filmium", self._role)
        context = _format_context(items)
        prompt = (
            f"Pitanje korisnika: {question}\n\n"
            f"Dostupni naslovi iz biblioteke:\n{context}\n\n"
            "Daj preporuku i kratko obrazloženje na srpskom."
        )

        try:
            answer = self._generate(binding.model, prompt,
                                    system=SYSTEM_PROMPT, fmt=None)
        except OllamaUnavailable:
            # Uredan fallback: pobroj najrelevantnije naslove bez LLM-a.
            listed = "; ".join(s for s in sources if s)
            return CuratorAnswer(
                answer=f"Model trenutno nije dostupan. Najbliži naslovi: {listed}.",
                sources=sources, is_fallback=True,
            )

        return CuratorAnswer(answer=answer.strip(), sources=sources)
