# ========== CORE ROUTER (klasifikator namere) ==========
# Saobraćajac: tekst korisnika ili putanju fajla mapira na strukturiran JSON
# intent (intent/target_domain/action/parameters) preko lokalnog modela (Ollama).
# Ako model nije dostupan ili vrati neispravan JSON, vraća se siguran fallback.
from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass, field

from core.ai.model_registry import ModelRegistry
from core.ai.ollama_client import OllamaUnavailable

# generate(model, prompt, *, system=None, fmt=None) -> str
Generate = Callable[..., str]

SYSTEM_PROMPT = (
    "Ti si CORE ruter. Na osnovu korisnickog unosa i opcione putanje fajla, "
    "vrati ISKLJUCIVO validan JSON bez ikakvog dodatnog teksta, oblika: "
    '{"intent": "...", "target_domain": "...", "action": "...", '
    '"parameters": {}}. target_domain mora biti jedan od poznatih domena."'
)


# ========== NAMERA ==========
@dataclass
class RouteIntent:
    intent: str
    target_domain: str
    action: str
    parameters: dict = field(default_factory=dict)
    raw: str = ""

    @property
    def is_fallback(self) -> bool:
        return self.intent == "unknown"


def _fallback(raw: str = "") -> RouteIntent:
    return RouteIntent(intent="unknown", target_domain="CORE",
                       action="none", parameters={}, raw=raw)


# ========== RUTER ==========
class CoreRouter:
    """Klasifikuje nameru koristeći lokalni model iz registra (uloga 'model')."""

    def __init__(self, registry: ModelRegistry, generate: Generate,
                 *, domain: str = "CORE", role: str = "model") -> None:
        self._registry = registry
        self._generate = generate
        self._domain = domain
        self._role = role

    def route(self, user_input: str, *, path: str | None = None) -> RouteIntent:
        binding = self._registry.binding(self._domain, self._role)

        prompt = f"Unos korisnika: {user_input}"
        if path:
            prompt += f"\nPutanja fajla: {path}"
        prompt += (
            "\nPoznati domeni: "
            + ", ".join(self._registry.domains())
            + "\nVrati JSON intent."
        )

        try:
            raw = self._generate(binding.model, prompt,
                                 system=SYSTEM_PROMPT, fmt="json")
        except OllamaUnavailable:
            return _fallback()

        return self._parse(raw)

    def _parse(self, raw: str) -> RouteIntent:
        try:
            data = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return _fallback(raw)
        if not isinstance(data, dict):
            return _fallback(raw)

        target = str(data.get("target_domain", "CORE"))
        known = set(self._registry.domains()) | {"CORE"}
        if target not in known:
            target = "CORE"

        params = data.get("parameters", {})
        if not isinstance(params, dict):
            params = {}

        return RouteIntent(
            intent=str(data.get("intent", "unknown")),
            target_domain=target,
            action=str(data.get("action", "none")),
            parameters=params,
            raw=raw,
        )
