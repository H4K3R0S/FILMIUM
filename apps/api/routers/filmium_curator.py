# ========== ROUTER: FILMIUM KURATOR (RAG preporuka) ==========
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from apps.api.schemas.filmium_curator import (
    CuratorAnswerResponse,
    CuratorAskRequest,
    CuratorCommandRequest,
    CuratorCommandResponse,
    CuratorConfirmRequest,
    CuratorRefuteRequest,
)
from core.domains.filmium.curator import CuratorService
from core.domains.filmium.curator.intent_router import CuratorAgent

router = APIRouter(
    prefix="/api/v1/filmium/curator",
    tags=["FILMIUM Kurator"],
)


def get_service() -> CuratorService:
    # Lenjo: teški curator/Ollama graf se gradi tek na prvi zahtev, ne pri startu.
    from apps.api import curator_runtime

    return curator_runtime.get_service()


def get_agent() -> CuratorAgent:
    from apps.api import curator_runtime

    return curator_runtime.get_agent()


@router.post("/ask", response_model=CuratorAnswerResponse)
def ask_curator(
    payload: CuratorAskRequest,
    service: CuratorService = Depends(get_service),
) -> CuratorAnswerResponse:
    """Preporuka na srpskom iz korisnikove biblioteke (RAG nad FILMIUM bazom)."""

    result = service.ask(payload.question, top_n=payload.top_n)
    return CuratorAnswerResponse.from_domain(result)


@router.post("/command", response_model=CuratorCommandResponse)
def curator_command(
    payload: CuratorCommandRequest,
    agent: CuratorAgent = Depends(get_agent),
) -> CuratorCommandResponse:
    """Prepoznaj komandu i izvrši (ili predloži za upis)."""

    return CuratorCommandResponse.from_domain(agent.handle(payload.message))


@router.post("/confirm")
def curator_confirm(
    payload: CuratorConfirmRequest,
    agent: CuratorAgent = Depends(get_agent),
) -> dict:
    """Izvrši potvrđeni upis po tokenu."""

    try:
        return agent.confirm(payload.token)
    except KeyError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)
        ) from error


@router.post("/refute")
def curator_refute(
    payload: CuratorRefuteRequest,
    agent: CuratorAgent = Depends(get_agent),
) -> dict:
    """Obeleži poslednju (ili datu) akciju kao pogrešnu u RAG-logu."""

    return {"refuted": agent.refute(payload.log_id)}
