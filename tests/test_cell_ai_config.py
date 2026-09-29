# ========== TESTOVI: AI podešavanja ćelije ==========
from __future__ import annotations

import json
from pathlib import Path

from core.cell import ai_config


def _cell(tmp_path: Path, ai: dict | None = None) -> Path:
    data = {"domain_id": "filmium", "port": 8781}
    if ai is not None:
        data["ai"] = ai
    (tmp_path / "cell.json").write_text(json.dumps(data), encoding="utf-8")
    return tmp_path


def test_read_vraca_model_i_adresu(tmp_path, monkeypatch):
    monkeypatch.setattr(ai_config, "list_local_models", lambda ep: ["qwen2.5", "llama3"])
    root = _cell(tmp_path, {"curator_model": "qwen2.5", "endpoint": "http://x:11434"})
    cfg = ai_config.read_ai_config(root)
    assert cfg.curator_model == "qwen2.5"
    assert cfg.endpoint == "http://x:11434"
    assert cfg.default_endpoint == "http://localhost:11434"
    assert cfg.available_models == ["qwen2.5", "llama3"]


def test_read_bez_ai_daje_podrazumevano(tmp_path, monkeypatch):
    monkeypatch.setattr(ai_config, "list_local_models", lambda ep: [])
    cfg = ai_config.read_ai_config(_cell(tmp_path))
    assert cfg.curator_model is None
    assert cfg.endpoint == "http://localhost:11434"


def test_write_upise_model_i_adresu_i_sacuva_ostalo(tmp_path, monkeypatch):
    monkeypatch.setattr(ai_config, "list_local_models", lambda ep: [])
    root = _cell(tmp_path, {"curator_model": None})
    ai_config.write_ai_config(root, curator_model="llama3", endpoint="http://y:11434")

    data = json.loads((root / "cell.json").read_text(encoding="utf-8"))
    assert data["ai"]["curator_model"] == "llama3"
    assert data["ai"]["endpoint"] == "http://y:11434"
    assert data["domain_id"] == "filmium"  # ostatak netaknut


def test_write_prazan_model_je_null_prazna_adresa_podrazumevana(tmp_path, monkeypatch):
    monkeypatch.setattr(ai_config, "list_local_models", lambda ep: [])
    root = _cell(tmp_path, {"curator_model": "staro"})
    cfg = ai_config.write_ai_config(root, curator_model="  ", endpoint="")
    assert cfg.curator_model is None
    assert cfg.endpoint == "http://localhost:11434"


def test_list_local_models_prazno_kad_ollama_cuti(monkeypatch):
    def _puca(self):
        raise RuntimeError("nedostupno")

    monkeypatch.setattr("core.ai.ollama_client.OllamaClient.tags", _puca)
    assert ai_config.list_local_models("http://localhost:11434") == []
