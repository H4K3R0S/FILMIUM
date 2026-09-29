# F:\FILMIUM\tests\test_curator_api.py
from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from apps.api.routers import filmium_curator
from core.domains.filmium.curator.intent_router import AgentResult


class _FakeAgent:
    def handle(self, message):
        return AgentResult(kind="answer", intent="search", reply="Evo.", sources=["Matriks"])

    def confirm(self, token):
        return {"updated": True, "media_id": 5}

    def refute(self, log_id=None):
        return True


def _client() -> TestClient:
    app = FastAPI()
    app.include_router(filmium_curator.router)
    app.dependency_overrides[filmium_curator.get_agent] = lambda: _FakeAgent()
    return TestClient(app)


def test_command_endpoint():
    resp = _client().post("/api/v1/filmium/curator/command", json={"message": "nadji"})
    assert resp.status_code == 200
    assert resp.json()["sources"] == ["Matriks"]


def test_confirm_endpoint():
    resp = _client().post("/api/v1/filmium/curator/confirm", json={"token": "t"})
    assert resp.status_code == 200
    assert resp.json()["updated"] is True


def test_confirm_lose_token_je_400():
    class _BadAgent(_FakeAgent):
        def confirm(self, token):
            raise KeyError("nema")

    app = FastAPI()
    app.include_router(filmium_curator.router)
    app.dependency_overrides[filmium_curator.get_agent] = lambda: _BadAgent()
    resp = TestClient(app).post("/api/v1/filmium/curator/confirm", json={"token": "x"})
    assert resp.status_code == 400


def test_refute_endpoint():
    resp = _client().post("/api/v1/filmium/curator/refute", json={})
    assert resp.status_code == 200
    assert resp.json()["refuted"] is True
