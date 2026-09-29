"""Ćelijski API: ono što ćelija izlaže CORE-u.

Ruta je namerno `/cell/status`, a ne `/status`, da se ne sudari sa sistemskim
statusom iz `apps/api/routers/system.py`.
"""

from pathlib import Path

from fastapi import APIRouter, HTTPException, status

from apps.api.schemas.cell import (
    CellAiConfigResponse,
    CellAiConfigUpdateRequest,
    CellAtomResponse,
    CellAtomUpdateRequest,
    CellPersonaResponse,
    CellPersonaUpdateRequest,
    CellStatusResponse,
)
from core.ai.persona_store import PersonaStore
from core.cell.ai_config import read_ai_config, write_ai_config
from core.cell.manifest import CellManifest
from core.cell.status import build_cell_status
from core.domains.filmium.curator import atom_files

router = APIRouter(prefix="/cell", tags=["cell"])

_manifest: CellManifest | None = None
_PERSONA_SCOPE = "filmium"


def bind_manifest(manifest: CellManifest | None) -> None:
    """Vezuje manifest za router; poziva se pri podizanju ćelije."""

    global _manifest
    _manifest = manifest


def _persona_store() -> PersonaStore:
    """Persona store ćelije; zasebna funkcija da bi test mogao da je zameni."""

    return PersonaStore()


def _require_manifest() -> CellManifest:
    """Manifest ćelije ili 503 ako nije učitan."""

    if _manifest is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Ćelija nema učitan manifest.",
        )
    return _manifest


def _atoms_root(manifest: CellManifest) -> Path:
    """Koren Kurator atoma u ćeliji."""

    return manifest.root / ".ai" / "atomi" / "personas" / "kurator"


@router.get("/status", response_model=CellStatusResponse)
def read_cell_status() -> CellStatusResponse:
    """Vraća stanje ćelije."""

    if _manifest is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Ćelija nema učitan manifest.",
        )

    return CellStatusResponse(**build_cell_status(_manifest))


@router.get("/personas", response_model=list[CellPersonaResponse])
def list_cell_personas() -> list[CellPersonaResponse]:
    """Vraća persone FILMIUM opsega."""

    return [
        CellPersonaResponse(id=doc.id, name=doc.name, markdown=doc.markdown, customized=doc.customized)
        for doc in _persona_store().list(_PERSONA_SCOPE)
    ]


@router.put("/personas/{persona_id}", response_model=CellPersonaResponse)
def save_cell_persona(persona_id: str, body: CellPersonaUpdateRequest) -> CellPersonaResponse:
    """Upisuje izmenjen tekst persone; prazan tekst se odbija."""

    try:
        doc = _persona_store().save(_PERSONA_SCOPE, persona_id, body.markdown)
    except ValueError as error:
        # `HTTP_422_UNPROCESSABLE_ENTITY` je zastareo u Starlette-u (baca
        # `StarletteDeprecationWarning`); ovo je nov ćelijski kod, pa koristi
        # `HTTP_422_UNPROCESSABLE_CONTENT`. 13 postojećih FILMIUM routera i
        # dalje koristi stari naziv — repo-širok zamenjivanje je van dometa
        # ovog taska (parkiran nalaz).
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(error)) from error
    except KeyError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Nepoznata persona: {persona_id}") from error

    return CellPersonaResponse(id=doc.id, name=doc.name, markdown=doc.markdown, customized=doc.customized)


# ========== AI PODEŠAVANJA (lokalni model + adresa) ==========

@router.get("/ai-config", response_model=CellAiConfigResponse)
def read_cell_ai_config() -> CellAiConfigResponse:
    """Model i adresa lokalne Ollame + lista dostupnih modela."""

    cfg = read_ai_config(_require_manifest().root)
    return CellAiConfigResponse(
        curator_model=cfg.curator_model, endpoint=cfg.endpoint,
        default_endpoint=cfg.default_endpoint, available_models=cfg.available_models,
    )


@router.put("/ai-config", response_model=CellAiConfigResponse)
def save_cell_ai_config(body: CellAiConfigUpdateRequest) -> CellAiConfigResponse:
    """Upisuje model i adresu u cell.json; primenjuje se po ponovnom pokretanju."""

    cfg = write_ai_config(
        _require_manifest().root,
        curator_model=body.curator_model, endpoint=body.endpoint,
    )
    return CellAiConfigResponse(
        curator_model=cfg.curator_model, endpoint=cfg.endpoint,
        default_endpoint=cfg.default_endpoint, available_models=cfg.available_models,
    )


# ========== KURATOR ATOMI (persona.md, tools, commands) ==========

@router.get("/kurator/atoms", response_model=list[CellAtomResponse])
def list_kurator_atoms() -> list[CellAtomResponse]:
    """Uređivi atom fajlovi Kuratora."""

    root = _atoms_root(_require_manifest())
    return [CellAtomResponse(path=a.path, content=a.content) for a in atom_files.list_atoms(root)]


@router.put("/kurator/atoms/{atom_path:path}", response_model=CellAtomResponse)
def save_kurator_atom(atom_path: str, body: CellAtomUpdateRequest) -> CellAtomResponse:
    """Upisuje sadržaj jednog atoma; prazan tekst / loša putanja se odbijaju."""

    root = _atoms_root(_require_manifest())
    try:
        atom = atom_files.write_atom(root, atom_path, body.content)
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(error)
        ) from error
    return CellAtomResponse(path=atom.path, content=atom.content)


import urllib.request as _sp2_urllib


def _ollama_reachable(endpoint: str) -> bool:
    """Kratka provera da li je Ollama dostupna (bez sistemskog proxy-ja)."""

    url = endpoint.rstrip("/") + "/api/tags"
    opener = _sp2_urllib.build_opener(_sp2_urllib.ProxyHandler({}))
    try:
        with opener.open(url, timeout=1.0) as response:
            return 200 <= response.status < 500
    except Exception:  # noqa: BLE001
        return False


@router.get("/health")
def read_cell_health() -> dict:
    """Zdravlje celije: sopstveni podsistemi (API, Ollama, RAG) — bez CORE-a."""

    try:
        if _manifest is None:
            return {"api": True, "ollama": False, "rag": None}
        st = build_cell_status(_manifest)
        endpoint = st.get("ai_endpoint") or "http://localhost:11434"
        rag_enabled = bool(st.get("rag_enabled"))
        return {"api": True, "ollama": _ollama_reachable(endpoint), "rag": True if rag_enabled else None}
    except Exception:  # noqa: BLE001 — health ruta nikad ne baca (ugovor)
        return {"api": True, "ollama": False, "rag": None}


@router.post("/rag/init")
def init_cell_rag() -> dict:
    """Osigura sopstvenu RAG bazu celije (napravi + migriraj); tolerantno."""

    from core.cell.rag_bootstrap import ensure_cell_rag_db

    return {"ready": ensure_cell_rag_db()}


@router.post("/rag/ingest")
def ingest_cell_rag() -> dict:
    """Ingestuje atome/logove celije u SOPSTVENU bazu (namespace cell:<domen>)."""

    if _manifest is None:
        return {"ok": False, "reason": "nema manifesta"}
    try:
        from core.rag.agent_knowledge import ingest_cell
        from core.rag.config import load_rag_config
        from core.rag.connection import rag_connection
        from core.rag.embedder import Embedder

        cfg = load_rag_config()
        embedder = Embedder(cfg.embedding_model, endpoint=cfg.embedding_endpoint)
        with rag_connection(cfg.dsn) as conn:
            summary = ingest_cell(conn, _manifest.domain_id, _manifest.root, embedder=embedder)
        return {"ok": True, **summary}
    except Exception as error:  # noqa: BLE001
        return {"ok": False, "reason": str(error)[:200]}
