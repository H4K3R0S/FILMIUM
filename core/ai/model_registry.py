# ========== MODEL REGISTRY ==========
# Centralni registar: mapira domen + ulogu na model, provajdera i endpoint.
# Cilj: promena provajdera (ollama <-> openrouter) u konfiguraciji preusmerava
# saobraćaj bez menjanja domenske logike. Konektor za openrouter dolazi kasnije
# (uz CODIUM); registar ga samo deklariše.
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from core.foundation.paths import core_paths

# Ključevi koji NISU uloga modela u konfiguraciji domena.
_META_KEYS = frozenset({"provider", "endpoint", "local_endpoint"})

# Uloge koje ostaju lokalne i kad je domen prebačen na udaljenog provajdera —
# ali samo ako domen izričito objavi `local_endpoint`. Bez tog pravila bi
# `light_model` nasledio `provider: anthropic` i lokalni model bi se slao na
# Anthropic API, gde ga nema.
_LOCAL_ROLES = frozenset({"light_model"})
_LOCAL_PROVIDER = "ollama"

# Ugrađeni podrazumevani registar (fallback ako fajl ne postoji).
_DEFAULTS: dict = {
    "domains": {
        "CORE": {
            "model": "llama3.2:latest",
            "provider": "ollama",
            "endpoint": "http://localhost:11434",
        },
        "Filmium": {
            "curator_model": "qwen2.5:7b",
            "embedding_model": "nomic-embed-text:latest",
            "provider": "ollama",
            "endpoint": "http://localhost:11434",
        },
    }
}


class ModelNotConfiguredError(KeyError):
    """Tražena kombinacija domen/uloga ne postoji u registru."""


# ========== VEZA MODELA ==========
@dataclass(frozen=True)
class ModelBinding:
    domain: str
    role: str
    model: str
    provider: str
    endpoint: str

    @property
    def is_local(self) -> bool:
        return self.provider == "ollama"


# ========== REGISTAR ==========
class ModelRegistry:
    """Čita mapiranje domen->uloga->model iz `models_config.json`."""

    def __init__(self, config: dict | None = None,
                 config_path: Path | None = None) -> None:
        self._data = config if config is not None else self._load(config_path)

    @staticmethod
    def _load(config_path: Path | None) -> dict:
        path = config_path or (core_paths.config / "models_config.json")
        try:
            return json.loads(Path(path).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return _DEFAULTS

    # ---------- upit ----------
    def domains(self) -> list[str]:
        return list(self._data.get("domains", {}).keys())

    def _domain_config(self, domain: str) -> dict:
        try:
            return self._data["domains"][domain]
        except KeyError as error:
            raise ModelNotConfiguredError(f"Nepoznat domen: {domain}") from error

    def roles(self, domain: str) -> list[str]:
        return [k for k in self._domain_config(domain) if k not in _META_KEYS]

    def binding(self, domain: str, role: str = "model") -> ModelBinding:
        cfg = self._domain_config(domain)
        if role not in cfg:
            raise ModelNotConfiguredError(
                f"Domen {domain} nema ulogu '{role}'."
            )
        local_endpoint = cfg.get("local_endpoint")
        lokalna = role in _LOCAL_ROLES and bool(local_endpoint)
        return ModelBinding(
            domain=domain,
            role=role,
            model=cfg[role],
            provider=_LOCAL_PROVIDER if lokalna else cfg.get("provider", "ollama"),
            endpoint=(
                local_endpoint if lokalna
                else cfg.get("endpoint", "http://localhost:11434")
            ),
        )

    def all_bindings(self) -> list[ModelBinding]:
        result: list[ModelBinding] = []
        for domain in self.domains():
            for role in self.roles(domain):
                result.append(self.binding(domain, role))
        return result
