# ========== TESTOVI: cell API — ai-config i kurator atomi ==========
from __future__ import annotations

import json
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from apps.api.routers import cell
from core.cell.manifest import CellManifest


def _cell_root(tmp_path: Path) -> Path:
    (tmp_path / "cell.json").write_text(
        json.dumps({
            "domain_id": "filmium", "name": "FILMIUM", "domain_version": "0.1",
            "kernel_version": "0.1.0", "port": 8781, "created_at": "2026-01-01",
            "ai": {"curator_model": "qwen2.5", "endpoint": "http://localhost:11434"},
        }),
        encoding="utf-8",
    )
    atomi = tmp_path / ".ai" / "atomi" / "personas" / "kurator"
    (atomi / "tools").mkdir(parents=True)
    (atomi / "persona.md").write_text("Persona.\n", encoding="utf-8")
    (atomi / "tools" / "pretraga.md").write_text("Pretraga.\n", encoding="utf-8")
    return tmp_path


def _manifest(root: Path) -> CellManifest:
    return CellManifest(
        domain_id="filmium", name="FILMIUM", domain_version="0.1",
        kernel_version="0.1.0", port=8781, core_url=None, created_at="2026-01-01",
        detached_from=None, root=root, ai_endpoint="http://localhost:11434",
        ai_curator_model="qwen2.5", rag_enabled=False, rag_namespace="cell:filmium",
    )


def _client(tmp_path: Path, monkeypatch) -> TestClient:
    monkeypatch.setattr("core.cell.ai_config.list_local_models", lambda ep: ["qwen2.5", "llama3"])
    cell.bind_manifest(_manifest(_cell_root(tmp_path)))
    app = FastAPI()
    app.include_router(cell.router)
    return TestClient(app)


def test_get_ai_config(tmp_path, monkeypatch):
    resp = _client(tmp_path, monkeypatch).get("/cell/ai-config")
    assert resp.status_code == 200
    body = resp.json()
    assert body["curator_model"] == "qwen2.5"
    assert body["default_endpoint"] == "http://localhost:11434"
    assert body["available_models"] == ["qwen2.5", "llama3"]


def test_put_ai_config_upise_u_cell_json(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    resp = client.put("/cell/ai-config", json={"curator_model": "llama3", "endpoint": "http://y:11434"})
    assert resp.status_code == 200
    assert resp.json()["curator_model"] == "llama3"
    data = json.loads((tmp_path / "cell.json").read_text(encoding="utf-8"))
    assert data["ai"]["curator_model"] == "llama3"
    assert data["ai"]["endpoint"] == "http://y:11434"


def test_list_kurator_atoms(tmp_path, monkeypatch):
    resp = _client(tmp_path, monkeypatch).get("/cell/kurator/atoms")
    assert resp.status_code == 200
    putanje = {a["path"] for a in resp.json()}
    assert putanje == {"persona.md", "tools/pretraga.md"}


def test_put_kurator_atom(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    resp = client.put("/cell/kurator/atoms/tools/pretraga.md", json={"content": "Novo uputstvo.\n"})
    assert resp.status_code == 200
    assert "Novo uputstvo" in resp.json()["content"]
    saved = (tmp_path / ".ai/atomi/personas/kurator/tools/pretraga.md").read_text(encoding="utf-8")
    assert saved == "Novo uputstvo.\n"


def test_put_kurator_atom_prazan_odbijen(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    resp = client.put("/cell/kurator/atoms/persona.md", json={"content": "   "})
    assert resp.status_code == 422
