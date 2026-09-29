"""Player kontrole (mpv overlay) za ćeliju — status, repozicija, pauza, seek,
fullscreen, stop. Frontend (`services/filmiumPlayer.ts`) zove `/api/v1/player/mpv/*`.

Ranije je ovaj sloj postojao samo u CORE/Tauri app-u; ćelija ga nije registrovala
pa je `GET /mpv/status` vraćao 404 → GUI je stalno prikazivao „mpv nije pronađen".
"""

from fastapi import APIRouter
from pydantic import BaseModel

from core.media_player import mpv_player

router = APIRouter(prefix="/api/v1/player", tags=["Player"])


class MpvStatus(BaseModel):
    available: bool
    running: bool


class GeometryBody(BaseModel):
    geometry: str


class SeekBody(BaseModel):
    seconds: float


class FullscreenBody(BaseModel):
    enabled: bool


@router.get("/mpv/status", response_model=MpvStatus)
def mpv_status() -> MpvStatus:
    return MpvStatus(available=mpv_player.available(), running=mpv_player.is_running())


@router.post("/mpv/reposition")
def mpv_reposition(body: GeometryBody) -> dict:
    return {"ok": mpv_player.reposition(body.geometry)}


@router.post("/mpv/pause")
def mpv_pause() -> dict:
    return {"ok": mpv_player.pause_toggle()}


@router.post("/mpv/seek")
def mpv_seek(body: SeekBody) -> dict:
    return {"ok": mpv_player.seek(body.seconds)}


@router.post("/mpv/fullscreen")
def mpv_fullscreen(body: FullscreenBody) -> dict:
    return {"ok": mpv_player.set_fullscreen(body.enabled)}


@router.post("/mpv/stop")
def mpv_stop() -> dict:
    return {"ok": mpv_player.stop()}
