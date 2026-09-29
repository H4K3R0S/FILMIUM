# ========== KURATOR RUNTIME (RAG za API, ćelija) ==========
# CuratorService se gradi preko core.cell.ai.build_cell_curator
# (lokalna Ollama iz cell.json), a ne preko CORE-ovog punog AI
# runtime-a — ćelija ne nosi core.integrations ni core.security.
from __future__ import annotations

from pathlib import Path

from apps.api.dependencies import get_library_root_service
from core.ai.ollama_client import OllamaClient
from core.cell.ai import build_cell_curator
from core.cell.manifest import load_cell_manifest
from core.domains.filmium.curator import CuratorService, MediaRetriever
from core.domains.filmium.curator.atoms import AtomLoader
from core.domains.filmium.curator.confirm import ConfirmStore
from core.domains.filmium.curator.executors import Executors
from core.domains.filmium.curator.intent_router import CuratorAgent
from core.domains.filmium.curator.interaction_log import InteractionLog
from core.domains.filmium.curator.media_resolver import MediaResolver
from core.domains.filmium.curator.recommender import Recommender
from core.domains.filmium.external_player import launch_vlc
from core.domains.filmium.media_source_repository import MediaSourceRepository
from core.domains.filmium.repository import MediaRepository


def _scan_library(root_id: int | None) -> dict:
    """AI skenira registrovane biblioteke (dati root_id ili sve)."""
    svc = get_library_root_service()
    if root_id is not None:
        svc.scan_library_root(root_id)
        return {"roots": 1, "root_id": root_id}
    roots = svc.list_library_roots()
    for root in roots:
        svc.scan_library_root(root.id)
    return {"roots": len(roots)}


def _enrich_media(media_id: int) -> dict:
    """AI povlači TMDB match + spoljne provajdere (IMDb/RT/TVmaze/Jikan), persistuje spoljne ocene."""
    from apps.api.dependencies import get_filmium_service
    from core.domains.filmium import tmdb_client
    from core.domains.filmium.media_external import (
        apply_external_enrichment,
        open_connection,
    )

    result: dict = {"media_id": media_id}
    try:
        item = get_filmium_service().get_media_item(media_id)
    except Exception:  # noqa: BLE001 — nepostojeći id ne sme da obori agent
        return {"media_id": media_id, "error": "not_found"}

    if tmdb_client.is_tmdb_available():
        title = item.original_title or item.title
        enr = (tmdb_client.enrich_series(title, item.release_year)
               if item.media_type.value == "series"
               else tmdb_client.enrich_movie(title, item.release_year))
        result["tmdb_matched"] = enr is not None
    else:
        result["tmdb"] = "unavailable"

    try:
        con = open_connection()
        try:
            summary = apply_external_enrichment(con, media_id)
            con.commit()
        finally:
            con.close()
        result["external_ratings"] = bool(summary.get("ratings_external"))
    except Exception:  # noqa: BLE001 — best-effort, ne obara agent
        result["external_ratings"] = False
    return result


def _wishlist_add(title: str) -> dict:
    """Dodaj naslov u listu željenih filmova (posle korisnikove potvrde)."""
    from apps.api.dependencies import get_wishlist_service
    from core.domains.filmium.wishlist_models import WishlistEntryCreate

    entry = get_wishlist_service().create_entry(WishlistEntryCreate(title=title))
    return {"wishlist_id": getattr(entry, "id", None)}


def _wishlist_titles() -> list[str]:
    """Naslovi već u listi želja (za proveru duplikata)."""
    from apps.api.dependencies import get_wishlist_service

    return [e.title for e in get_wishlist_service().list_entries()]


def _tmdb_lookup(title: str) -> dict | None:
    """Info o naslovu sa TMDB-a kad ga nema u bazi (za info intent)."""
    from core.domains.filmium import tmdb_client

    if not tmdb_client.is_tmdb_available():
        return None
    enr = tmdb_client.enrich_movie(title)
    if enr is None:
        return None
    return {
        "title": getattr(enr, "title", title),
        "year": getattr(enr, "release_year", None),
        "overview": getattr(enr, "overview", None),
    }


# Koren ćelije: ovaj fajl živi na `<koren>/apps/api/curator_runtime.py`.
_MANIFEST = load_cell_manifest(Path(__file__).resolve().parents[2])
_repository = MediaRepository()
_retriever = MediaRetriever(_repository.list_all)
_service = build_cell_curator(_MANIFEST, _retriever)


def get_service() -> CuratorService:
    return _service


# ========== CURATOR AGENT (intent-router) ==========
# Isti manifest/model kao CuratorService iznad; agent dodaje izvršavanje
# namera (search/play/play_vlc/edit_metadata) preko Executors sloja.
_ATOMI_ROOT = _MANIFEST.root / ".ai" / "atomi" / "personas" / "kurator"
_LOG_ROOT = _MANIFEST.root / ".ai" / "atomi" / "logs" / "kurator"

_media_sources = MediaSourceRepository()


def _resolve_video_path(media_id: int) -> str | None:
    """Nalazi apsolutnu putanju glavnog video fajla za dati media_id.

    Isti obrazac kao `get_media_technical` u `apps/api/routers/filmium.py`:
    `MediaSourceRepository.list_for_media` vraća izvore sa fajlovima; putanja
    je root_path_snapshot + relative_directory + relative_path video fajla.

    Odbrambeno: malformisan/nepotpun izvor (npr. None polje) ne sme da
    izazove 500 — `play_vlc` u tom slučaju samo degradira na launched=False;
    web-plejer put (`play`) ovu funkciju ne koristi.
    """

    try:
        for source in _media_sources.list_for_media(media_id):
            for file in source.files:
                if file.role.value == "video":
                    return str(
                        Path(source.root_path_snapshot)
                        / source.relative_directory
                        / file.relative_path
                    )
    except (TypeError, ValueError, AttributeError, OSError):
        return None

    return None


_ollama = OllamaClient(endpoint=_MANIFEST.ai_endpoint, timeout=60.0)

# NAPOMENA (domen-lokalni Kurator): Kurator NE koristi RAG-kontekst niti
# centralni ruter. Tok je: Filmium se pokrene → poziva lokalnu Ollamu → model
# čita SVOJU personu (`_sa_personom`) + katalog komandi i po tome rutira nameru.
# Ranije je ovde stajao `build_fallthrough_retriever` koji je na promašaj lokalne
# baze pitao centralni ruter (:4800) i gradio FTS/vektor indeks NA request-putanji
# — to je usporavalo prvi odgovor na 100+ s i izlazilo iz domena. Uklonjeno:
# `retrieve=None` (v. CuratorAgent._sa_kontekstom — graciozno preskače kontekst).


# Model ostaje topao 10min posle poziva → sledeći upit u sesiji ~1s umesto ~5s
# (hladno učitavanje). Kratko jer GPU deli miner — posle 10min neaktivnosti
# Ollama oslobodi VRAM.
_KEEP_ALIVE = "10m"


def _generate(
    model: str,
    prompt: str,
    *,
    system: str | None = None,
    fmt: str | None = None,
) -> str:
    return _ollama.generate(model, prompt, system=system, fmt=fmt, keep_alive=_KEEP_ALIVE)


_MODEL = _MANIFEST.ai_curator_model or "qwen2.5:7b"


def _curate(pool: list, req: dict) -> list[int]:
    """AI-sloj preporuke (3): iz bodovanog poola kandidata izabere do `limit`
    naslova za korisnikov zahtev/raspoloženje. Vrati listu media_id-jeva. Robusno
    po REDNOM BROJU (ne po naslovu) — model vraća JSON {"picks":[brojevi]}."""
    import json

    limit = int(req.get("limit", 20))
    lines = []
    for i, m in enumerate(pool):
        genres = ", ".join(getattr(m, "genres", ()) or ())
        year = getattr(m, "release_year", "") or ""
        lines.append(f"{i}. {getattr(m, 'title', '')} ({year}) [{genres}]")

    zelje = []
    if req.get("genre"):
        zelje.append(f"žanr: {req['genre']}")
    if req.get("mood"):
        zelje.append(f"raspoloženje: {req['mood']}")
    hint = f" (uzmi u obzir: {', '.join(zelje)})" if zelje else ""

    prompt = (
        f"Ti si filmski kurator. Iz liste kandidata izaberi do {limit} naslova "
        f"koje bi korisnik najverovatnije voleo{hint}. Biraj raznovrsno i kvalitetno. "
        'Vrati ISKLJUČIVO JSON: {"picks": [redni_brojevi]} — redni brojevi iz liste.\n\n'
        + "\n".join(lines)
    )
    try:
        raw = _ollama.generate(_MODEL, prompt, fmt="json", keep_alive=_KEEP_ALIVE)
        picks = json.loads(raw).get("picks", [])
    except Exception:  # noqa: BLE001 — AI zataji → Recommender pada na skor
        return []
    ids: list[int] = []
    for p in picks:
        try:
            idx = int(p)
        except (TypeError, ValueError):
            continue
        if 0 <= idx < len(pool):
            mid = getattr(pool[idx], "id", None)
            if mid is not None:
                ids.append(int(mid))
    return ids


_recommender = Recommender(_repository.list_all, curate=_curate)


_agent = CuratorAgent(
    atoms=AtomLoader(_ATOMI_ROOT),
    executors=Executors(
        retriever=_retriever,
        repository=_repository,
        launch_vlc=launch_vlc,
        resolve_video_path=_resolve_video_path,
        scan_library=_scan_library,
        enrich_media=_enrich_media,
        wishlist_add=_wishlist_add,
        wishlist_titles=_wishlist_titles,
        tmdb_lookup=_tmdb_lookup,
        recommender=_recommender,
    ),
    confirm=ConfirmStore(),
    log=InteractionLog(_LOG_ROOT),
    generate=_generate,
    model=_MODEL,
    resolver=MediaResolver(_repository.list_all),
    retrieve=None,  # domen-lokalno: bez RAG-a/centralnog rutera (v. napomenu gore)
)


def get_agent() -> CuratorAgent:
    return _agent
