# apps/api/routers/filmium_approvals.py
# ==========          ROUTER: FILMIUM APPROVALS (F7a)          ==========
# Covek (preko Second Brain GUI-ja) ODOBRAVA/ODBIJA gate koji je
# `core/cell/executor.py::Executor.run()` napravio za HIGH/CRITICAL akciju
# (v. core/cell/approvals.py i UNAPREDJENJE/01-ARHITEKTURA/05-approval-gates.md).
#
# ----------          MODEL POVERENJA (trust model)          ----------
# - `Approvals` u SQLite bazi cuva SAMO `sha256(token)` — plaintext token se
#   NIGDE ne upisuje na disk. `create_gate()` ga vraca pozivaocu TACNO JEDNOM.
# - Taj isti token Executor best-effort emituje preko SSE (`type:"gate"`,
#   `POST /api/events` ka Second Brain — v. `core/cell/executor.py::_http_emit`
#   i `run()`). Covek ga cita TAMO (u GUI-ju), ne ovde.
# - Ovaj ruter NIKAD ne vraca token nazad: `GET` lista sadrzi samo gate_id/
#   tool/risk/reason/requested_at/expires_at — bez token/token_hash polja.
# - `POST /{gate_id}/approve` FAIL-CLOSED verifikuje token kroz
#   `Approvals.approve()` (`hmac.compare_digest`, konstantno vreme). Pogresan
#   ili istekao token NIKAD ne odobrava, bez obzira ko/odakle pita — ovaj
#   ruter ne slabi taj model, samo ga izlaze preko HTTP-a.
# - Localhost, single-user OS: nema dodatne autentifikacije iznad ovoga, isto
#   kao ostali `/api/v1/filmium/*` ruteri (v. cell_app.py — TrustedHostMiddleware
#   na 127.0.0.1/localhost, bez CORS-a). Emitovanje tokena preko lokalnog SSE
#   ka lokalnom GUI-ju je u ovom modelu prihvatljivo.
from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from core.cell.approvals import PENDING, Approvals, Gate
from core.cell.executor import Executor

router = APIRouter(prefix="/api/v1/filmium/approvals", tags=["FILMIUM Approvals"])


def _iso(ts: float | None) -> str | None:
    if ts is None:
        return None
    return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()


def _gate_summary(gate: Gate) -> dict:
    """Javni prikaz gate-a za GUI listu — NAMERNO bez token/token_hash."""

    return {
        "gate_id": gate.id,
        "tool": gate.tool,
        "risk": gate.risk,
        "reason": gate.reason,
        "requested_at": _iso(gate.requested_at),
        "expires_at": _iso(gate.expires_at),
    }


# ----------          DELJENE INSTANCE (lenj build)          ----------
# `cell_app.py` uvozi sve `API_ROUTERS` module pri boot-u — ako bi se
# `Approvals()`/`Executor()` gradili na module-nivou, boot bi otvarao SQLite
# konekciju odmah. Umesto toga, grade se tek pri prvom zahtevu (isto kao
# ostali lenji runtime moduli u `apps/api/` — npr. `curator_runtime.py/disk_runtime.py`).
_approvals: Approvals | None = None
_executor: Executor | None = None


def get_approvals() -> Approvals:
    global _approvals
    if _approvals is None:
        _approvals = Approvals()
    return _approvals


def get_executor() -> Executor:
    global _executor
    if _executor is None:
        _executor = Executor(domain="filmium", approvals=get_approvals())
    return _executor


# ----------          TELA ZAHTEVA          ----------

class ApproveRequest(BaseModel):
    token: str = Field(..., min_length=1)
    note: str = ""


class RejectRequest(BaseModel):
    note: str = ""


# ----------          RUTE          ----------

@router.get("")
def list_pending(approvals: Approvals = Depends(get_approvals)) -> list[dict]:
    """Molbe na cekanju (HIGH/CRITICAL gate-ovi) — BEZ tokena."""

    return [_gate_summary(gate) for gate in approvals.list_pending()]


@router.post("/{gate_id}/approve")
def approve(
    gate_id: str,
    payload: ApproveRequest,
    approvals: Approvals = Depends(get_approvals),
    executor: Executor = Depends(get_executor),
) -> dict:
    """Odobrava gate SAMO uz tacan token (FAIL-CLOSED, v. trust model gore) i
    odmah izvrsava odobrenu akciju preko `Executor.execute_approved()`.

    Nepoznat `gate_id` -> 404. Pogresan token dok je gate jos na cekanju ->
    403 (molba ostaje pending, sme se probati ponovo). Gate koji vise nije
    na cekanju (vec odluceno ili istekao) -> 409, cak i uz tacan token.
    """

    if approvals.get(gate_id) is None:
        raise HTTPException(status_code=404, detail=f"gate `{gate_id}` ne postoji")

    odobren = approvals.approve(gate_id, payload.token, payload.note)
    if odobren is None:
        posle = approvals.get(gate_id)
        if posle is not None and posle.status != PENDING:
            raise HTTPException(
                status_code=409,
                detail=(
                    f"gate `{gate_id}` vise nije na cekanju "
                    f"(status={posle.status}) — nije odobreno"
                ),
            )
        raise HTTPException(
            status_code=403,
            detail="pogresan token — odobrenje odbijeno (fail-closed)",
        )

    rezultat = executor.execute_approved(odobren)
    return asdict(rezultat)


@router.post("/{gate_id}/reject")
def reject(
    gate_id: str,
    payload: RejectRequest,
    approvals: Approvals = Depends(get_approvals),
) -> dict:
    """Odbija gate na cekanju. Bez tokena — odbijanje ne otvara pristup
    nicemu, pa nema sta fail-closed da se proverava (isto kao `Approvals.reject`)."""

    postojeci = approvals.get(gate_id)
    if postojeci is None:
        raise HTTPException(status_code=404, detail=f"gate `{gate_id}` ne postoji")

    odbijen = approvals.reject(gate_id, payload.note)
    if odbijen is None:
        raise HTTPException(
            status_code=409,
            detail=(
                f"gate `{gate_id}` vise nije na cekanju "
                f"(status={postojeci.status}) — nije odbijeno"
            ),
        )
    return {
        "gate_id": odbijen.id,
        "status": odbijen.status,
        "note": odbijen.note,
        "decided_at": _iso(odbijen.decided_at),
    }
