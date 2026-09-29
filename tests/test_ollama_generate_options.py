# tests/test_ollama_generate_options.py
# ========== TEST: generate šalje keep_alive (model ostaje topao) ==========
import json

from core.ai.ollama_client import OllamaClient


def _capture_client(captured: dict) -> OllamaClient:
    def transport(url, body, timeout):
        captured["payload"] = json.loads(body)
        return json.dumps({"response": "ok"})

    return OllamaClient(transport=transport)


def test_generate_ukljucuje_keep_alive_kad_je_zadat():
    captured: dict = {}
    _capture_client(captured).generate("qwen2.5:7b", "hi", keep_alive="10m")
    assert captured["payload"]["keep_alive"] == "10m"


def test_generate_bez_keep_alive_ne_salje_polje():
    captured: dict = {}
    _capture_client(captured).generate("qwen2.5:7b", "hi")
    assert "keep_alive" not in captured["payload"]
