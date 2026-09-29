"""FALLTHROUGH protokol — most između ćelijskog RAG-a i centralnog rutera.

Kada interni RAG ćelije NE nađe odgovor u svojoj lokalnoj bazi, umesto praznog
rezultata ćelija pošalje FALLTHROUGH zahtev centralnom ruteru (Global Atom OS,
`router-api` na 127.0.0.1:4800). Ako ruter vrati podatak (iz globalnog grafa ili
od drugog domena preko `/solve`), ćelija ga upiše kao NOVI ATOMSKI FAJL u svoju
lokalnu bazu (`.ai/atomi/nauceno/`) i — best-effort — u globalni graf (`ggraph`),
da bi ga sledeći put znala odmah, bez rutera.

Sve je TOLERANTNO (isti duh kao LocalRetriever): ruter dole, mreža, `ggraph`
nedostupan → prazan rezultat / no-op; Agent nikad ne pada zbog fallthrough-a.
Samo Python stdlib — bez novih zavisnosti.
"""
from __future__ import annotations

import json
import logging
import re
import subprocess
import unicodedata
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

_logger = logging.getLogger(__name__)

# Maks. dužina jednog snippet-a (kao u LocalRetriever/CORE `_search`).
_SNIPPET_MAX = 400
_ROUTER_DEFAULT = "http://127.0.0.1:4800/route"
_ASK_TIMEOUT = 3.0  # kratko: fallthrough NE sme da zaglavi Agentov odgovor

# capability -> ključne reči (srpski + engleski). Prvi pogodak (redom) bira
# capability koju šaljemo ruteru. Deterministički, bez AI-ja.
_CAPABILITY_KEYWORDS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("code", ("kod", "kôd", "skript", "script", "program", "exploit", "payload",
              "ctf", "build", "kompajl", "compile", "debug", "funkcij", "class",
              "python", "bash", "reverse", "shell", "razvoj")),
    ("recon", ("pentest", "recon", "izviđ", "izvid", "target", " ip", "adres",
               "scan", "skenir", "nmap", "port ", "ranjiv", "vuln", "cve",
               "hash", "malver", "malware", "forenz", "osint")),
    ("orchestration", ("plan", "strateg", "orkestr", "workflow", "zadatak",
                       "koordin", "raspored", "arhitekt")),
    ("film", ("film", "movie", "video", "serij", "epizod", "subtitle", "titl",
              "youtube", "plejer", "poster", "tmdb", "medij", "media")),
)


def slugify(text: str) -> str:
    """Isto kao `GlobalGraphManager.slugify` (id se poklopi sa ruter graf-kešom)."""
    norm = unicodedata.normalize("NFKD", text)
    norm = "".join(c for c in norm if not unicodedata.combining(c))
    norm = re.sub(r"[^a-z0-9]+", "-", norm.lower()).strip("-")[:80]
    return norm or "atom"


def infer_capability(query: str) -> str | None:
    """Odredi traženu capability iz upita (ključne reči) ili None."""
    q = f" {query.lower()} "
    for cap, kws in _CAPABILITY_KEYWORDS:
        if any(kw in q for kw in kws):
            return cap
    return None


def _tokens(text: str) -> list[str]:
    return [t for t in re.split(r"[^a-z0-9]+", text.lower()) if len(t) >= 3]


def _strip_frontmatter(text: str) -> str:
    if text.startswith("---"):
        end = text.find("\n---", 3)
        if end != -1:
            nl = text.find("\n", end + 1)
            return text[nl + 1:] if nl != -1 else ""
    return text


def _ggraph_get_body(atom_id: str) -> str:
    """Dovuci telo atoma iz globalnog grafa (`ggraph get`). Prazno ako ne uspe."""
    try:
        out = subprocess.run(["ggraph", "get", atom_id], capture_output=True,
                             text=True, timeout=4, check=False)
        if out.returncode != 0 or not out.stdout.strip():
            return ""
        return str(json.loads(out.stdout).get("body") or "").strip()
    except Exception:  # noqa: BLE001 — ggraph opcion
        return ""


def _ggraph_add(query: str, snippets: list[str], capability: str | None) -> None:
    """Upiši naučeni atom i u globalni graf (deljeno, za ruter graf-keš)."""
    body = "\n\n".join(s for s in snippets if s and s.strip())
    if not body.strip():
        return
    try:
        subprocess.run(
            ["ggraph", "add", capability or "note", query[:120],
             "-i", slugify(query), "-b", body,
             "-t", f"fallthrough,{capability or 'note'}"],
            capture_output=True, text=True, timeout=6, check=False,
        )
    except Exception as error:  # noqa: BLE001 — graf je opcion
        _logger.debug("ggraph add nije uspeo (%s)", error)


def _extract_snippets(data: object) -> list[str]:
    """Normalizuj `RouteResponse.data` u listu tekstualnih snippeta."""
    if data is None:
        return []
    if isinstance(data, dict):
        snips = data.get("snippets")
        if isinstance(snips, list) and snips:
            return [str(s)[:_SNIPPET_MAX] for s in snips if str(s).strip()]
        atom_id = data.get("cachedAtom")
        if isinstance(atom_id, str) and atom_id:
            body = _ggraph_get_body(atom_id)
            if body:
                return [body[:_SNIPPET_MAX]]
            return [f"[graf] atom '{atom_id}' (tip {data.get('type', '?')})"]
        cands = data.get("candidatesByType")
        if isinstance(cands, list) and cands:
            return [f"[graf] srodni atomi: {', '.join(str(c) for c in cands[:5])}"]
        try:
            return [json.dumps(data, ensure_ascii=False)[:_SNIPPET_MAX]]
        except Exception:  # noqa: BLE001
            return []
    if isinstance(data, str):
        return [data[:_SNIPPET_MAX]] if data.strip() else []
    if isinstance(data, list):
        return [str(x)[:_SNIPPET_MAX] for x in data if str(x).strip()]
    return [str(data)[:_SNIPPET_MAX]]


class FallthroughClient:
    """Klijent ka centralnom ruteru (POST /route). Sve greške -> []."""

    def __init__(self, origin: str, router_url: str = _ROUTER_DEFAULT,
                 timeout: float = _ASK_TIMEOUT) -> None:
        self._origin = origin
        self._router_url = router_url
        self._timeout = timeout

    def ask(self, query: str, capability: str | None = None) -> list[str]:
        cap = capability or infer_capability(query) or ""
        payload = {
            "capability": cap,
            "query": query,
            "origin": self._origin,
            "payload": {"via": "rag-fallthrough"},
        }
        try:
            data = self._post(payload)
        except Exception as error:  # noqa: BLE001 — ruter opcion
            _logger.debug("fallthrough: ruter nedostupan (%s)", error)
            return []
        if not isinstance(data, dict) or not data.get("ok"):
            return []
        return _extract_snippets(data.get("data"))

    def _post(self, payload: dict) -> object:
        body = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            self._router_url, data=body, method="POST",
            headers={"content-type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=self._timeout) as resp:
            raw = resp.read().decode("utf-8")
        return json.loads(raw) if raw else None


class LearnedAtomStore:
    """Lokalna baza NAUČENIH atoma (markdown + frontmatter), bez Postgresa.

    Ćelija ovde upisuje ono što je naučila preko rutera i odatle čita sledeći
    put — brz lokalni pogodak koji radi i kada je Postgres RAG ugašen."""

    def __init__(self, root: Path, domain: str) -> None:
        self._dir = Path(root) / ".ai" / "atomi" / "nauceno"
        self._domain = domain

    def _atoms(self) -> list[Path]:
        try:
            return sorted(self._dir.glob("*.md"))
        except Exception:  # noqa: BLE001
            return []

    def search(self, query: str, k: int = 3) -> list[str]:
        tokens = _tokens(query)
        if not tokens:
            return []
        scored: list[tuple[int, str]] = []
        for p in self._atoms():
            try:
                text = p.read_text(encoding="utf-8")
            except Exception:  # noqa: BLE001, S112
                continue
            hay = text.lower()
            score = sum(1 for t in tokens if t in hay)
            if score:
                body = _strip_frontmatter(text).strip()
                if body:
                    scored.append((score, body[:_SNIPPET_MAX]))
        scored.sort(key=lambda s: s[0], reverse=True)
        return [b for _, b in scored[:k]]

    def write(self, query: str, snippets: list[str], *, capability: str | None,
              source: str | None) -> Path | None:
        text = "\n\n".join(s for s in snippets if s and s.strip())
        if not text.strip():
            return None
        slug = slugify(query)
        now = datetime.now(timezone.utc).isoformat()
        try:
            self._dir.mkdir(parents=True, exist_ok=True)
            title = query.replace("\n", " ").strip()[:120]
            content = (
                "---\n"
                f"id: {slug}\n"
                f"title: {title}\n"
                f"type: {capability or 'note'}\n"
                f"domain: {self._domain}\n"
                f"source: {source or 'router'}\n"
                "origin: fallthrough\n"
                f"created: {now}\n"
                f"updated: {now}\n"
                "---\n\n"
                f"{text}\n"
            )
            path = self._dir / f"{slug}.md"
            path.write_text(content, encoding="utf-8")
        except Exception as error:  # noqa: BLE001
            _logger.debug("nauceno: upis nije uspeo (%s)", error)
            return None

        # CISA petlja (F4): best-effort upsert naučenog atoma u globalnu
        # vektorsku bazu (`cross_domain_knowledge`), da ga drugi domeni nađu
        # semantički. Import je lenj/lokalan (core/cell/memory_client.py) —
        # ako Qdrant/Ollama nisu gore ili modul fali, atom je VEĆ upisan na
        # disku iznad, ovo nikad ne sme da sruši write().
        try:
            from core.cell import memory_client
            memory_client.upsert(
                "cross_domain_knowledge", slug, text,
                {"origin_domain": self._domain, "markdown": f"[[{slug}]]",
                 "updated": now},
            )
        except Exception as error:  # noqa: BLE001 — vektor upsert je bonus sloj
            _logger.debug("nauceno: vektor upsert nije uspeo (%s)", error)

        return path


class RagFallthrough:
    """Retriever koji prosleđuje ka ruteru kad lokalni RAG nema odgovor.

    Isti ugovor kao `LocalRetriever` (`retrieve(query) -> list[str]`), pa je
    drop-in zamena u `*_assistant_runtime.py`. Redosled:
      1) postojeći lokalni RAG (Postgres, namespace cell:<domain>),
      2) naučeni atomi (lokalni fajlovi — rade i bez Postgresa),
      3) FALLTHROUGH ka ruteru; rezultat se upiše kao nov atom (lokalno + graf).
    """

    def __init__(self, local, domain: str, root: Path, *,
                 client: FallthroughClient | None = None,
                 learned: LearnedAtomStore | None = None,
                 write_graph: bool = True) -> None:
        self._local = local
        self._domain = domain
        self._client = client or FallthroughClient(origin=domain)
        self._learned = learned or LearnedAtomStore(root, domain)
        self._write_graph = write_graph

    def retrieve(self, query: str) -> list[str]:
        try:
            hits = self._local.retrieve(query) if self._local else []
        except Exception:  # noqa: BLE001
            hits = []
        if hits:
            return hits

        learned_hits = self._learned.search(query)
        if learned_hits:
            return learned_hits

        cap = infer_capability(query)
        remote = self._client.ask(query, capability=cap)
        if not remote:
            return []
        self._learned.write(query, remote, capability=cap, source="router")
        if self._write_graph:
            _ggraph_add(query, remote, cap)
        return remote


def build_fallthrough_retriever(local, domain: str, root: Path) -> RagFallthrough:
    """Umotaj lokalni retriever u FALLTHROUGH sloj (jedan poziv iz runtime-a)."""
    return RagFallthrough(local, domain, root)
