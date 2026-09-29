# ========== ŠEME FILMIUM KURATOR ==========
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from core.domains.filmium.curator import CuratorAnswer
from core.domains.filmium.curator.intent_router import AgentResult


class CuratorAskRequest(BaseModel):
    question: str = Field(..., min_length=1)
    top_n: int = Field(default=10, ge=1, le=25)


class CuratorAnswerResponse(BaseModel):
    answer: str
    sources: list[str]
    is_fallback: bool

    @classmethod
    def from_domain(cls, result: CuratorAnswer) -> CuratorAnswerResponse:
        return cls(
            answer=result.answer,
            sources=list(result.sources),
            is_fallback=result.is_fallback,
        )


class CuratorCommandRequest(BaseModel):
    message: str = Field(..., min_length=1)


class CuratorCommandResponse(BaseModel):
    kind: str
    intent: str
    params: dict[str, Any] = Field(default_factory=dict)
    reply: str = ""
    preview: dict[str, Any] | None = None
    confirm_token: str | None = None
    sources: list[str] = Field(default_factory=list)
    log_id: str | None = None

    @classmethod
    def from_domain(cls, result: AgentResult) -> CuratorCommandResponse:
        return cls(
            kind=result.kind, intent=result.intent, params=result.params,
            reply=result.reply, preview=result.preview,
            confirm_token=result.confirm_token, sources=list(result.sources),
            log_id=result.log_id,
        )


class CuratorConfirmRequest(BaseModel):
    token: str = Field(..., min_length=1)


class CuratorRefuteRequest(BaseModel):
    log_id: str | None = None
