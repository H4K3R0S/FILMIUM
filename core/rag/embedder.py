from __future__ import annotations

import json
from collections.abc import Callable
from urllib.error import URLError
from urllib.request import Request, urlopen

EmbedTransport = Callable[[str, bytes, float], str]


def _default_transport(url: str, body: bytes, timeout: float) -> str:
    request = Request(url, data=body, headers={"Content-Type": "application/json"})
    with urlopen(request, timeout=timeout) as response:
        return response.read().decode("utf-8")


class Embedder:
    """Zove Ollama /api/embed u batch-evima. Degradira na None po batch-u.

    Veliki fajlovi (stotine chunkova) se cepaju na batch_size grupa da jedan
    ogroman zahtev ne obori ceo fajl.
    """

    def __init__(self, model: str, *, endpoint: str = "http://localhost:11434",
                 transport: EmbedTransport | None = None,
                 timeout: float = 30.0, batch_size: int = 96) -> None:
        self._model = model
        self._endpoint = endpoint.rstrip("/")
        self._transport = transport or _default_transport
        self._timeout = timeout
        self._batch_size = max(1, batch_size)

    def _embed_batch(self, texts: list[str]) -> list[list[float] | None]:
        payload = json.dumps({"model": self._model, "input": texts}).encode("utf-8")
        try:
            raw = self._transport(f"{self._endpoint}/api/embed", payload, self._timeout)
            data = json.loads(raw)
            vektori = data.get("embeddings")
            if not isinstance(vektori, list) or len(vektori) != len(texts):
                return [None] * len(texts)
            return [list(v) for v in vektori]
        except (URLError, OSError, json.JSONDecodeError):
            return [None] * len(texts)

    def embed(self, texts: list[str]) -> list[list[float] | None]:
        if not texts:
            return []
        rezultat: list[list[float] | None] = []
        for i in range(0, len(texts), self._batch_size):
            rezultat.extend(self._embed_batch(texts[i:i + self._batch_size]))
        return rezultat

    def embed_one(self, text: str) -> list[float] | None:
        return self.embed([text])[0]
