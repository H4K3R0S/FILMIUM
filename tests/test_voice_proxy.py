"""GLAS voice proxy (apps/api/routers/voice.py) — GLAS servis je monkeypatch-ovan."""
from __future__ import annotations

import httpx
from fastapi import FastAPI
from fastapi.testclient import TestClient

from apps.api.routers import voice


def _client() -> TestClient:
    app = FastAPI()
    app.include_router(voice.router)
    return TestClient(app)


class _Resp:
    def __init__(self, js=None, content=b"", status=200):
        self._js = js or {}
        self.content = content
        self.status_code = status

    def json(self):
        return self._js

    def raise_for_status(self):
        if self.status_code >= 400:
            raise httpx.HTTPStatusError("err", request=None, response=httpx.Response(self.status_code))


def test_transcribe_proxy(monkeypatch):
    monkeypatch.setattr(voice.httpx, "post", lambda *a, **k: _Resp(js={"text": "ćao", "lang": "sr"}))
    r = _client().post("/api/v1/voice/transcribe", files={"file": ("a.webm", b"x", "audio/webm")})
    assert r.status_code == 200
    assert r.json()["text"] == "ćao"


def test_speak_proxy_vraca_wav(monkeypatch):
    monkeypatch.setattr(voice.httpx, "post", lambda *a, **k: _Resp(content=b"RIFF...."))
    r = _client().post("/api/v1/voice/speak", json={"text": "zdravo", "lang": "sr"})
    assert r.status_code == 200
    assert r.content[:4] == b"RIFF"


def test_glas_nedostupan_503(monkeypatch):
    def boom(*a, **k):
        raise httpx.ConnectError("down")

    monkeypatch.setattr(voice.httpx, "post", boom)
    r = _client().post("/api/v1/voice/transcribe", files={"file": ("a.webm", b"x", "audio/webm")})
    assert r.status_code == 503


def test_voices_proxy(monkeypatch):
    monkeypatch.setattr(voice.httpx, "get", lambda *a, **k: _Resp(js={"voices": [{"id": "glas.onnx", "lang": "sr"}]}))
    r = _client().get("/api/v1/voice/voices")
    assert r.status_code == 200
    assert r.json()["voices"][0]["id"] == "glas.onnx"
