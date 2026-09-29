# ========== ROUTER: FILMIUM TORRENTI ==========
from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator

from fastapi import (
    APIRouter,
    Depends,
    File,
    HTTPException,
    Request,
    UploadFile,
    status,
)
from fastapi.responses import StreamingResponse

from apps.api.schemas.filmium_torrents import (
    DiscoveredStartRequest,
    DiscoveredTorrentResponse,
    TorrentAddRequest,
    TorrentApproveRequest,
    TorrentBulkResponse,
    TorrentFileResponse,
    TorrentHealthResponse,
    TorrentProgressResponse,
    TorrentResponse,
    TorrentRevealResponse,
    TorrentSettingsRequest,
    TorrentSettingsResponse,
)
from core.domains.filmium.torrents.torrent_models import (
    TorrentSettings,
    TorrentStatus,
)
from core.domains.filmium.torrents.torrent_service import (
    TorrentService,
    TorrentServiceError,
)

router = APIRouter(
    prefix="/api/v1/filmium/torrents",
    tags=["FILMIUM Torrenti"],
)

# Razmak između dva SSE otkucaja.
STREAM_INTERVAL_SECONDS = 1.0


def get_service() -> TorrentService:
    # Lenjo: torrent/qBittorrent graf se gradi tek na prvi zahtev, ne pri startu.
    from apps.api import torrent_runtime

    return torrent_runtime.get_service()


def _not_found(error: TorrentServiceError) -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error))


def _bad_request(error: TorrentServiceError) -> HTTPException:
    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error))


def _raise(error: TorrentServiceError) -> None:
    if "nije pronađen" in str(error):
        raise _not_found(error)
    raise _bad_request(error)


# ==========          ZDRAVLJE          ==========

@router.get("/health", response_model=TorrentHealthResponse)
def health(
    service: TorrentService = Depends(get_service),
) -> TorrentHealthResponse:
    return TorrentHealthResponse.from_domain(service.health())


# ==========          PODEŠAVANJA          ==========

@router.get("/settings", response_model=TorrentSettingsResponse)
def read_settings(
    service: TorrentService = Depends(get_service),
) -> TorrentSettingsResponse:
    return TorrentSettingsResponse.from_domain(service.settings())


@router.put("/settings", response_model=TorrentSettingsResponse)
def write_settings(
    payload: TorrentSettingsRequest,
    service: TorrentService = Depends(get_service),
) -> TorrentSettingsResponse:
    current = service.settings()
    saved = service.save_settings(
        TorrentSettings(
            host=payload.host,
            port=payload.port,
            username=payload.username,
            # `None` (polje izostavljeno) znači „zadrži postojeću lozinku";
            # prazan string je izričito brisanje sačuvane lozinke.
            password=(
                current.password if payload.password is None else payload.password
            ),
            watch_folders=tuple(payload.watch_folders),
            download_path=payload.download_path,
            max_download_kbs=payload.max_download_kbs,
            max_upload_kbs=payload.max_upload_kbs,
            max_active=payload.max_active,
            auto_start=payload.auto_start,
            seed_after_complete=payload.seed_after_complete,
            delete_source_torrent=payload.delete_source_torrent,
            unselected_extensions=tuple(payload.unselected_extensions),
        )
    )
    return TorrentSettingsResponse.from_domain(saved)


# ==========          LISTA I DODAVANJE          ==========

@router.get("/", response_model=list[TorrentResponse])
def list_torrents(
    status_filter: str | None = None,
    service: TorrentService = Depends(get_service),
) -> list[TorrentResponse]:
    parsed: TorrentStatus | None = None
    if status_filter:
        try:
            parsed = TorrentStatus(status_filter)
        except ValueError as error:
            allowed = ", ".join(item.value for item in TorrentStatus)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Nepoznat status '{status_filter}'. "
                    f"Dozvoljene vrednosti: {allowed}."
                ),
            ) from error
    return [TorrentResponse.from_domain(item) for item in service.list(parsed)]


@router.post(
    "/add",
    response_model=TorrentResponse,
    status_code=status.HTTP_201_CREATED,
)
def add_torrent(
    payload: TorrentAddRequest,
    service: TorrentService = Depends(get_service),
) -> TorrentResponse:
    try:
        return TorrentResponse.from_domain(service.add(payload.source))
    except TorrentServiceError as error:
        _raise(error)
        raise  # pragma: no cover — _raise uvek baca


# ==========          PRONAĐENI .torrent FAJLOVI          ==========

@router.get("/discovered", response_model=list[DiscoveredTorrentResponse])
def list_discovered(
    service: TorrentService = Depends(get_service),
) -> list[DiscoveredTorrentResponse]:
    """Sve što stoji kao .torrent fajl u nadziranim folderima.

    Čita se sam fajl, pa lista radi i kada qBittorrent nije pokrenut.
    """

    return [
        DiscoveredTorrentResponse.from_domain(item)
        for item in service.discover()
    ]


@router.post("/discovered/start", response_model=TorrentResponse)
def start_discovered(
    payload: DiscoveredStartRequest,
    service: TorrentService = Depends(get_service),
) -> TorrentResponse:
    """Pušta pronađen torrent sa tačno onim fajlovima koje je korisnik štiklirao."""

    try:
        return TorrentResponse.from_domain(
            service.start_discovered(payload.source_path, payload.selected_paths)
        )
    except TorrentServiceError as error:
        _raise(error)
        raise  # pragma: no cover


@router.delete("/discovered", status_code=status.HTTP_204_NO_CONTENT)
def remove_discovered(
    source_path: str,
    service: TorrentService = Depends(get_service),
) -> None:
    """Briše .torrent fajl iz nadziranog foldera; kartica time nestaje."""

    try:
        service.remove_discovered(source_path)
    except TorrentServiceError as error:
        _raise(error)


@router.post(
    "/upload",
    response_model=DiscoveredTorrentResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_torrent_file(
    file: UploadFile = File(...),
    service: TorrentService = Depends(get_service),
) -> DiscoveredTorrentResponse:
    """Prima prevučen .torrent fajl i upisuje ga u nadzirani folder.

    Ništa se ne pušta na skidanje — fajl samo postaje kartica sa spiskom
    sadržaja, kao i svaki drugi .torrent iz nadziranog foldera.
    """

    data = await file.read()
    try:
        return DiscoveredTorrentResponse.from_domain(
            service.save_torrent_bytes(file.filename or "", data)
        )
    except TorrentServiceError as error:
        _raise(error)
        raise  # pragma: no cover


# ==========          FAJLOVI I ODOBRENJE          ==========

@router.get("/{info_hash}/files", response_model=list[TorrentFileResponse])
def list_files(
    info_hash: str,
    service: TorrentService = Depends(get_service),
) -> list[TorrentFileResponse]:
    try:
        return [
            TorrentFileResponse.from_domain(item)
            for item in service.files(info_hash)
        ]
    except TorrentServiceError as error:
        _raise(error)
        raise  # pragma: no cover


@router.post("/{info_hash}/approve", response_model=TorrentResponse)
def approve(
    info_hash: str,
    payload: TorrentApproveRequest,
    service: TorrentService = Depends(get_service),
) -> TorrentResponse:
    try:
        return TorrentResponse.from_domain(
            service.approve(info_hash, payload.selected_indexes)
        )
    except TorrentServiceError as error:
        _raise(error)
        raise  # pragma: no cover


# ==========          GRUPNE RADNJE          ==========

@router.post("/pause-all", response_model=TorrentBulkResponse)
def pause_all(
    service: TorrentService = Depends(get_service),
) -> TorrentBulkResponse:
    """Pauzira sve torrente koji se trenutno skidaju."""

    return TorrentBulkResponse(affected=service.pause_all())


@router.post("/start-all", response_model=TorrentBulkResponse)
def start_all(
    service: TorrentService = Depends(get_service),
) -> TorrentBulkResponse:
    """Pokreće sve torrente koji mogu da krenu.

    Pauzirani se nastavljaju, oni koji čekaju izbor fajlova kreću sa već
    upisanim izborom, a pronađeni .torrent fajlovi se predaju klijentu sa
    podrazumevanim izborom (ekstenzije iz filtera ostaju neštiklirane).
    """

    started, failed = service.start_all()
    return TorrentBulkResponse(affected=started, failed=failed)


# ==========          KONTROLA          ==========

@router.post("/{info_hash}/pause", response_model=TorrentResponse)
def pause(
    info_hash: str,
    service: TorrentService = Depends(get_service),
) -> TorrentResponse:
    try:
        return TorrentResponse.from_domain(service.pause(info_hash))
    except TorrentServiceError as error:
        _raise(error)
        raise  # pragma: no cover


@router.post("/{info_hash}/resume", response_model=TorrentResponse)
def resume(
    info_hash: str,
    service: TorrentService = Depends(get_service),
) -> TorrentResponse:
    try:
        return TorrentResponse.from_domain(service.resume(info_hash))
    except TorrentServiceError as error:
        _raise(error)
        raise  # pragma: no cover


@router.post("/{info_hash}/handoff", status_code=status.HTTP_204_NO_CONTENT)
def mark_library_handoff(
    info_hash: str,
    service: TorrentService = Depends(get_service),
) -> None:
    """Beleži da je torrent poslat ka ekranu uvoza u biblioteku.

    Zapis preživljava uklanjanje torrenta — po njemu se kasnije brisanje
    izvornog .torrent fajla radi bez dodatnog pitanja.
    """

    try:
        service.mark_library_handoff(info_hash)
    except TorrentServiceError as error:
        _raise(error)


@router.post("/{info_hash}/reveal", response_model=TorrentRevealResponse)
def reveal(
    info_hash: str,
    service: TorrentService = Depends(get_service),
) -> TorrentRevealResponse:
    """Otvara folder sa preuzetim sadržajem u menadžeru fajlova.

    Putanja dolazi iz zapisa o torrentu, ne iz zahteva.
    """

    try:
        folder = service.content_folder(info_hash)
        return TorrentRevealResponse(
            revealed=service.reveal(info_hash),
            folder=folder,
        )
    except TorrentServiceError as error:
        _raise(error)
        raise  # pragma: no cover


@router.delete("/{info_hash}", status_code=status.HTTP_204_NO_CONTENT)
def remove(
    info_hash: str,
    delete_files: bool = False,
    service: TorrentService = Depends(get_service),
) -> None:
    try:
        service.remove(info_hash, delete_files=delete_files)
    except TorrentServiceError as error:
        _raise(error)


# ==========          SSE PROGRES          ==========

@router.get("/stream")
async def stream(
    request: Request,
    service: TorrentService = Depends(get_service),
) -> StreamingResponse:
    """Jedan strim za sve aktivne torrente; otkucaj svake sekunde.

    Ruta NE anketira klijenta. Pozadinska nit (`TorrentPoller`) je jedini
    vlasnik prelaza stanja i notifikacija; ovde se samo emituje poslednji
    snimak koji je ta nit sačuvala. Da strim sam zove `poll()`, dva otvorena
    strima (Dashboard i stranica Torrenti) bila bi dva pisca nad istom
    bazom i mogla bi da pošalju duplu notifikaciju.

    Async generator — sinhrona `def` ruta sa `time.sleep` bi ovde držala
    nit iz deljenog Starlette threadpool-a za ceo životni vek konekcije i
    mogla bi da iscrpi radnike za SVE sinhrone rute u CORE-u.
    """

    async def events() -> AsyncIterator[str]:
        while True:
            if await request.is_disconnected():
                break
            progress = service.latest_progress()
            payload = [
                TorrentProgressResponse.from_domain(item).model_dump()
                for item in progress
            ]
            body = json.dumps(payload, ensure_ascii=False, default=str)
            yield f"event: progress\ndata: {body}\n\n"
            await asyncio.sleep(STREAM_INTERVAL_SECONDS)

    return StreamingResponse(events(), media_type="text/event-stream")
