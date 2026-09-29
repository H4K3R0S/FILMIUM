# ========== CORE AI SLOJ ==========
# ModelRegistry (mapiranje domen/uloga -> model/provajder), Ollama klijent i
# CoreRouter (klasifikacija namere). OpenRouter konektor dolazi uz CODIUM.
from core.ai.core_router import CoreRouter, RouteIntent
from core.ai.model_registry import (
    ModelBinding,
    ModelNotConfiguredError,
    ModelRegistry,
)
from core.ai.ollama_client import OllamaClient, OllamaUnavailable

__all__ = [
    "CoreRouter",
    "ModelBinding",
    "ModelNotConfiguredError",
    "ModelRegistry",
    "OllamaClient",
    "OllamaUnavailable",
    "RouteIntent",
]
