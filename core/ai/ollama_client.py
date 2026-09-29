# ========== OLLAMA KLIJENT ==========
# Tanak klijent za lokalni Ollama API (localhost:11434). Bez novih zavisnosti
# (urllib iz standardne biblioteke). Transport je injektabilan radi testiranja
# bez pokrenutog Ollama servera. Degradira uredno: ako server nije dostupan,
# baca OllamaUnavailable (pozivalac odlučuje o fallback-u).
from __future__ import annotations

import json
from collections.abc import Callable
from urllib.error import URLError
from urllib.request import Request, urlopen

# Transport: (url, payload_bytes, timeout) -> odgovor kao tekst.
Transport = Callable[[str, bytes, float], str]

# GET transport: (url, timeout) -> odgovor kao tekst.
GetTransport = Callable[[str, float], str]


class OllamaUnavailable(RuntimeError):
    """Ollama server nije dostupan ili je vratio grešku."""


def _default_transport(url: str, body: bytes, timeout: float) -> str:
    request = Request(url, data=body, headers={"Content-Type": "application/json"})
    try:
        with urlopen(request, timeout=timeout) as response:
            return response.read().decode("utf-8")
    except (URLError, OSError) as error:
        raise OllamaUnavailable(str(error)) from error


def _default_get_transport(url: str, timeout: float) -> str:
    try:
        with urlopen(url, timeout=timeout) as response:
            return response.read().decode("utf-8")
    except (URLError, OSError) as error:
        raise OllamaUnavailable(str(error)) from error


# ========== KLIJENT ==========
class OllamaClient:
    """Poziva Ollama `/api/generate` (ne-stream) i vraća tekst modela."""

    def __init__(self, endpoint: str = "http://localhost:11434",
                 transport: Transport | None = None,
                 timeout: float = 60.0,
                 get_transport: GetTransport | None = None) -> None:
        self._endpoint = endpoint.rstrip("/")
        self._transport = transport or _default_transport
        self._get_transport = get_transport or _default_get_transport
        self._timeout = timeout

    def generate(self, model: str, prompt: str, *,
                 system: str | None = None,
                 fmt: str | None = None,
                 keep_alive: str | None = None) -> str:
        """Vrati generisani tekst. `fmt="json"` traži strukturiran JSON izlaz.

        `keep_alive` (npr. "10m", "-1") drži model rezidentnim u (V)RAM-u posle
        poziva, da sledeći upit ne plati hladno učitavanje. None → ne šalje se
        (Ollama podrazumevano 5min).
        """
        payload: dict = {"model": model, "prompt": prompt, "stream": False}
        if system is not None:
            payload["system"] = system
        if fmt is not None:
            payload["format"] = fmt
        if keep_alive is not None:
            payload["keep_alive"] = keep_alive

        raw = self._transport(
            f"{self._endpoint}/api/generate",
            json.dumps(payload).encode("utf-8"),
            self._timeout,
        )
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as error:
            raise OllamaUnavailable(f"Neispravan odgovor Ollama: {error}") from error
        return data.get("response", "")

    def tags(self) -> list[dict]:
        """Lokalno instalirani modeli (`GET /api/tags`)."""

        raw = self._get_transport(f"{self._endpoint}/api/tags", self._timeout)
        data = self._decode(raw)
        models = data.get("models", [])
        return models if isinstance(models, list) else []

    def chat(self, model: str, messages: list[dict], *,
             system: str | None = None) -> dict:
        """Ne-stream poziv `/api/chat`. Vraća ceo dekodiran odgovor.

        Za razliku od `generate`, ovaj put nosi listu poruka i u odgovoru
        `prompt_eval_count` / `eval_count` — brojanje tokena bez dodatnog posla.
        """

        payload_messages = list(messages)
        if system is not None:
            payload_messages.insert(0, {"role": "system", "content": system})

        raw = self._transport(
            f"{self._endpoint}/api/chat",
            json.dumps({
                "model": model,
                "messages": payload_messages,
                "stream": False,
            }).encode("utf-8"),
            self._timeout,
        )
        return self._decode(raw)

    @staticmethod
    def _decode(raw: str) -> dict:
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as error:
            raise OllamaUnavailable(f"Neispravan odgovor Ollama: {error}") from error
        if not isinstance(data, dict):
            raise OllamaUnavailable("Ollama nije vratio JSON objekat.")
        return data
