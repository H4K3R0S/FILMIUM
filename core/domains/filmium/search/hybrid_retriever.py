# core/domains/filmium/search/hybrid_retriever.py
# ==========          HYBRID RETRIEVER (FTS5 + vektor + RRF + rerank)          ==========
# Zamenjuje/omotava `LocalRetriever` (apps/api/agent_retriever.py). ISTI JAVNI
# UGOVOR: `retrieve(query) -> list[str]`, snippeti ≤400 znakova — drop-in, ne
# menja pozivaoce (filmium_assistant_runtime.py, solve.py).
#
# Slojevi (svaki degradira nezavisno, v. UNAPREDJENJE 01-ARHITEKTURA/
# 02-hibridna-pretraga.md):
#   (0) query keš (LRU + TTL 60s, ključ = slugify(query))
#   (1) FTS5 leksička pretraga — UVEK radi, bez mreže/Postgresa
#   (2) vektor (postojeći LocalRetriever/pgvector) — best-effort, try/except -> []
#   (3) RRF fuzija FTS + vektor rezultata
#   (4) rerank bonus: status verified/stable, confidence, sveže `updated`,
#       egzaktan id/title pogodak, tip koji odgovara capability
#
# Sve tolerantno: greška bilo gde -> [] (Agent nikad ne pada zbog pretrage).
from __future__ import annotations

import logging
import time
from collections import OrderedDict
from datetime import datetime

from core.cell.fallthrough import infer_capability, slugify
from core.domains.filmium.search import fts_index, vector_index

_logger = logging.getLogger(__name__)

_SNIPPET_MAX = 400
_CACHE_TTL = 60.0
_CACHE_MAX = 128
_RRF_K = 60  # standardni RRF konstant (60) — v. plan
_HALF_LIFE_DAYS = 30.0

# Best-effort mapiranje capability (fallthrough.py) -> tip atoma koji joj
# najčešće odgovara u ovoj ćeliji (persona/tool/command). Ako se ne poklopi,
# bonus je prosto 0 — nikad greška.
_CAPABILITY_TYPE_HINTS: dict[str, set[str]] = {
    "code": {"tool", "command"},
    "recon": {"tool", "persona"},
    "orchestration": {"persona"},
    "film": {"tool"},
}


class _TTLCache:
    """Prost LRU+TTL keš upita (bez spoljnih zavisnosti)."""

    def __init__(self, maxsize: int = _CACHE_MAX, ttl: float = _CACHE_TTL) -> None:
        self._maxsize = maxsize
        self._ttl = ttl
        self._data: OrderedDict[str, tuple[float, list[str]]] = OrderedDict()

    def get(self, key: str) -> list[str] | None:
        item = self._data.get(key)
        if item is None:
            return None
        ts, value = item
        if time.monotonic() - ts > self._ttl:
            self._data.pop(key, None)
            return None
        self._data.move_to_end(key)
        return value

    def put(self, key: str, value: list[str]) -> None:
        self._data[key] = (time.monotonic(), list(value))
        self._data.move_to_end(key)
        while len(self._data) > self._maxsize:
            self._data.popitem(last=False)


def _parse_updated(value: object) -> float | None:
    """`updated`/ISO datum -> unix timestamp. `None` ako se ne da parsirati."""
    if not value or not isinstance(value, str):
        return None
    try:
        v = value.strip()
        if v.endswith("Z"):
            v = v[:-1] + "+00:00"
        return datetime.fromisoformat(v).timestamp()
    except Exception:  # noqa: BLE001 — best-effort
        return None


def _recency_decay(updated: object) -> float:
    """exp opadanje, poluživot 30 dana. Nepoznato `updated` -> 0 (bez bonusa,
    ne penal — atomi bez datuma nisu nužno stari)."""
    ts = _parse_updated(updated)
    if ts is None:
        return 0.0
    age_days = max(0.0, (time.time() - ts) / 86400.0)
    return 0.5 ** (age_days / _HALF_LIFE_DAYS)


def _confidence_bonus(value: object) -> float:
    try:
        return max(0.0, min(1.0, float(value)))
    except (TypeError, ValueError):
        return 0.0


class HybridRetriever:
    """FTS5 (uvek) + vektor (best-effort) + RRF + rerank.

    Drop-in zamena za `LocalRetriever`: isti `retrieve(query) -> list[str]`.
    FTS indeks se lenjo gradi/sinhronizuje pri prvom `retrieve` u procesu.
    """

    def __init__(self, domain: str, k: int = 5, *, vector=None) -> None:
        self._domain = domain
        self._k = max(1, int(k))
        self._cache = _TTLCache()
        self._index_ready = False

        if vector is not None:
            # Eksplicitno prosleđen vektor sloj (npr. iz testova) — koristi ga.
            self._vector = vector
        else:
            # Podrazumevano: postojeći LocalRetriever (Postgres/pgvector). Ako
            # sam import padne (npr. modul nedostupan), vektor sloj je None —
            # HybridRetriever i dalje radi samo na FTS-u.
            try:
                from apps.api.agent_retriever import LocalRetriever

                self._vector = LocalRetriever(domain=domain, k=self._k)
            except Exception as error:  # noqa: BLE001
                _logger.debug(
                    "HybridRetriever: LocalRetriever nedostupan (%s)", error
                )
                self._vector = None

    def _ensure_index(self) -> None:
        """Lenjo gradi/sinhronizuje FTS indeks — jednom po procesu."""
        if self._index_ready:
            return
        self._index_ready = True  # postavi PRE (ne pokušavaj opet na svaki upit)
        try:
            if fts_index.count() == 0:
                fts_index.rebuild()
            else:
                fts_index.sync()
        except Exception as error:  # noqa: BLE001
            _logger.debug("HybridRetriever: priprema FTS indeksa nije uspela (%s)", error)
        try:
            vector_index.sync(self._domain)  # embeduj atome u Qdrant (best-effort)
        except Exception as error:  # noqa: BLE001
            _logger.debug("HybridRetriever: vektor (Qdrant) sync nije uspeo (%s)", error)

    def retrieve(self, query: str) -> list[str]:
        q = (query or "").strip()
        if not q:
            return []
        cache_key = slugify(q)
        cached = self._cache.get(cache_key)
        if cached is not None:
            return cached
        try:
            out = self._retrieve_uncached(q)
        except Exception as error:  # noqa: BLE001 — pretraga nikad ne ruši Agenta
            _logger.debug("HybridRetriever: retrieve nije uspeo (%s)", error)
            out = []
        self._cache.put(cache_key, out)
        return out

    def _retrieve_uncached(self, q: str) -> list[str]:
        fused = self._ranked(q)
        return [h["snippet"][:_SNIPPET_MAX] for h in fused[: self._k]]

    def rank(self, query: str) -> list[dict]:
        """Kao `retrieve`, ali vraća FUZOVANE pogotke sa `id`-jem (za merenje/
        bench i sve što treba rang atoma, ne samo snippete):
        `[{"id", "snippet", "score"}, ...]` opadajuće. Tolerantno -> []."""
        q = (query or "").strip()
        if not q:
            return []
        try:
            return self._ranked(q)
        except Exception as error:  # noqa: BLE001
            _logger.debug("HybridRetriever.rank nije uspeo (%s)", error)
            return []

    def _ranked(self, q: str) -> list[dict]:
        """Deljeno jezgro za `retrieve`/`rank`: FTS + Qdrant vektor + RRF +
        rerank -> fuzovana lista `[{id, snippet, score}]`."""
        self._ensure_index()

        try:
            lex_hits = fts_index.search(q, k=max(self._k * 2, 10))
        except Exception as error:  # noqa: BLE001
            _logger.debug("HybridRetriever: FTS pretraga nije uspela (%s)", error)
            lex_hits = []

        # Vektor sloj = Qdrant (atoms_<domen>) preko memory_client — ZAMENJUJE
        # mrtav pgvector. Vraća dict-ove sa `id` -> fuzija po id-u sa FTS-om.
        vec_hits: list[dict] = []
        try:
            vec_hits = vector_index.search(self._domain, q, k=max(self._k * 2, 10)) or []
        except Exception as error:  # noqa: BLE001
            _logger.debug("HybridRetriever: Qdrant vektor pretraga nedostupna (%s)", error)
            vec_hits = []
        # Ako je vektor sloj EKSPLICITNO injektovan (npr. mock u testu), dodaj i
        # njegove string-snippete kao vektor kandidate (kompatibilnost unazad).
        if self._vector is not None:
            try:
                for snip in (self._vector.retrieve(q) or []):
                    if snip:
                        vec_hits.append({"id": None, "snippet": snip})
            except Exception as error:  # noqa: BLE001
                _logger.debug("HybridRetriever: injektovani vektor sloj nedostupan (%s)", error)

        return self._rrf_fuse(q, lex_hits, vec_hits)

    def _rrf_fuse(
        self, query: str, lex_hits: list[dict], vec_hits: list[dict]
    ) -> list[dict]:
        """Reciprocal Rank Fusion + deterministički rerank bonus.
        Vraća `[{id, snippet, score}]` opadajuće po score-u."""
        scores: dict[str, float] = {}
        snippet_of: dict[str, str] = {}
        id_of: dict[str, str | None] = {}
        order: list[str] = []

        def _bump(key: str, snippet: str, rank: int, real_id, bonus: float) -> None:
            if key not in snippet_of:
                snippet_of[key] = snippet
                id_of[key] = real_id
                order.append(key)
            elif real_id and not id_of.get(key):
                id_of[key] = real_id
            scores[key] = scores.get(key, 0.0) + 1.0 / (_RRF_K + rank) + bonus

        for rank, hit in enumerate(lex_hits, start=1):
            snippet = (hit.get("snippet") or "").strip()
            if not snippet:
                continue
            real_id = hit.get("id")
            key = str(real_id or snippet[:60])
            _bump(key, snippet, rank, real_id, self._rerank_bonus(query, hit))

        for rank, hit in enumerate(vec_hits, start=1):
            snippet = (hit.get("snippet") or "").strip()
            if not snippet:
                continue
            # ISTI id kao leksički pogodak -> spaja rangove (atom nadjen i FTS-om
            # i vektorski rangira više). Bez id-a (injektovani mock) -> po snippetu.
            real_id = hit.get("id")
            key = str(real_id or f"vec:{snippet[:60]}")
            _bump(key, snippet, rank, real_id, self._rerank_bonus(query, hit))

        order.sort(key=lambda key: scores.get(key, 0.0), reverse=True)
        return [
            {"id": id_of.get(key), "snippet": snippet_of[key], "score": scores.get(key, 0.0)}
            for key in order
        ]

    def _rerank_bonus(self, query: str, hit: dict) -> float:
        """score += 0.15*(status verified/stable) + 0.10*confidence
        + 0.10*recency_decay(updated) + 0.25*exact_id_or_title_match
        + 0.10*type_matches_capability(query)."""
        bonus = 0.0
        try:
            status = str(hit.get("status") or "").strip().lower()
            if status in {"verified", "stable"}:
                bonus += 0.15

            bonus += 0.10 * _confidence_bonus(hit.get("confidence"))
            bonus += 0.10 * _recency_decay(hit.get("updated"))

            qs = query.strip().lower()
            atom_id = str(hit.get("id") or "").strip().lower()
            title = str(hit.get("title") or "").strip().lower()
            if qs and (qs == atom_id or qs == title):
                bonus += 0.25

            cap = infer_capability(query)
            atype = str(hit.get("type") or "").strip().lower()
            if cap and atype and atype in _CAPABILITY_TYPE_HINTS.get(cap, set()):
                bonus += 0.10
        except Exception as error:  # noqa: BLE001 — rerank je opcion
            _logger.debug("HybridRetriever: rerank bonus nije uspeo (%s)", error)
        return bonus
