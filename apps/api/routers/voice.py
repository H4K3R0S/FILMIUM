"""GLAS voice proxy — /api/v1/voice/* → sistemski GLAS servis (:4809).

Domen ne zove GLAS direktno iz GUI-ja (Tauri CORS); GUI gađa ovaj proxy, a on
prosleđuje GLAS-u. GLAS nedostupan → 503; GLAS 4xx/5xx → propušta status."""
from __future__ import annotations

import os

import httpx
from fastapi import APIRouter, Body, File, HTTPException, Query, UploadFile
from fastapi.responses import Response

GLAS_URL = os.environ.get("GLAS_URL", "http://127.0.0.1:4809")
_TIMEOUT = httpx.Timeout(connect=3.0, read=120.0, write=30.0, pool=3.0)

router = APIRouter(prefix="/api/v1/voice", tags=["Voice"])


def _glas(e: Exception) -> HTTPException:
    if isinstance(e, httpx.HTTPStatusError):
        return HTTPException(e.response.status_code, f"GLAS: {e.response.text or e}")
    return HTTPException(503, f"GLAS servis nedostupan: {e}")


@router.post("/transcribe")
def transcribe(file: UploadFile = File(...), lang: str = Query("auto")) -> dict:
    # Sync `def` → FastAPI ga vrti u threadpool-u, pa blokirajući httpx.post
    # ne zamrzava event-loop cele ćelije tokom transkripcije.
    data = file.file.read()
    try:
        r = httpx.post(
            f"{GLAS_URL}/transcribe",
            params={"lang": lang},
            files={"file": (file.filename or "audio.webm", data, "application/octet-stream")},
            timeout=_TIMEOUT,
        )
        r.raise_for_status()
        return r.json()
    except Exception as e:
        raise _glas(e) from e


@router.post("/speak")
def speak(payload: dict = Body(...)):
    text = (payload.get("text") or "").strip()
    if not text:
        raise HTTPException(400, "prazan tekst")
    try:
        r = httpx.post(
            f"{GLAS_URL}/speak",
            json={"text": text, "lang": payload.get("lang"), "voice": payload.get("voice")},
            timeout=_TIMEOUT,
        )
        r.raise_for_status()
        return Response(content=r.content, media_type="audio/wav")
    except Exception as e:
        raise _glas(e) from e


@router.get("/voices")
def voices() -> dict:
    try:
        r = httpx.get(f"{GLAS_URL}/voices", timeout=httpx.Timeout(5.0))
        r.raise_for_status()
        return r.json()
    except Exception as e:  # noqa: BLE001 - GLAS dole → prazna lista, GUI ne puca
        return {"voices": [], "error": str(e)}
