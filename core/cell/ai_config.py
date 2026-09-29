# ========== AI PODEŠAVANJA ĆELIJE (cell.json ai sekcija) ==========
# Ćelija radi nad lokalnom Ollamom; model i adresa žive u `cell.json` (ai.
# curator_model, ai.endpoint). Ovaj modul ih čita, upisuje i nabraja lokalno
# instalirane modele. Izmena se primenjuje po ponovnom pokretanju ćelije.
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from core.ai.ollama_client import OllamaClient
from core.cell.manifest import _DEFAULT_AI_ENDPOINT, CELL_MANIFEST_FILENAME


@dataclass(frozen=True)
class AiConfig:
    """AI podešavanja ćelije za ekran podešavanja."""

    curator_model: str | None
    endpoint: str
    default_endpoint: str
    available_models: list[str]


def _manifest_path(root: Path) -> Path:
    return root / CELL_MANIFEST_FILENAME


def list_local_models(endpoint: str) -> list[str]:
    """Imena lokalno instaliranih Ollama modela; prazna lista ako Ollama ćuti."""

    try:
        tags = OllamaClient(endpoint=endpoint, timeout=5.0).tags()
    except Exception:  # noqa: BLE001 — Ollama nedostupna ne sme da sruši ekran
        return []
    imena = [str(t.get("name")) for t in tags if t.get("name")]
    return sorted(set(imena))


def read_ai_config(root: Path) -> AiConfig:
    """Trenutna AI podešavanja + lista dostupnih modela."""

    data = json.loads(_manifest_path(root).read_text(encoding="utf-8"))
    ai = data.get("ai") or {}
    endpoint = str(ai.get("endpoint") or _DEFAULT_AI_ENDPOINT)
    model = ai.get("curator_model")
    return AiConfig(
        curator_model=model if model else None,
        endpoint=endpoint,
        default_endpoint=_DEFAULT_AI_ENDPOINT,
        available_models=list_local_models(endpoint),
    )


def write_ai_config(
    root: Path, *, curator_model: str | None, endpoint: str | None
) -> AiConfig:
    """Upisuje model i adresu u `cell.json` (ostatak manifesta netaknut).

    Prazan model -> `null` (Kurator nije podešen). Prazna adresa -> podrazumevana.
    Primenjuje se tek po ponovnom pokretanju ćelije.
    """

    path = _manifest_path(root)
    data = json.loads(path.read_text(encoding="utf-8"))
    ai = dict(data.get("ai") or {})

    model = (curator_model or "").strip()
    ai["curator_model"] = model or None
    adresa = (endpoint or "").strip()
    ai["endpoint"] = adresa or _DEFAULT_AI_ENDPOINT

    data["ai"] = ai
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return read_ai_config(root)
