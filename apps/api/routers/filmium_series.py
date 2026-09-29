import json
import mimetypes
import re
import shutil
import subprocess
from pathlib import Path
from typing import Annotated

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
    Request,
    status,
)
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel

from apps.api.dependencies import get_series_import_service
from apps.api.schemas.filmium_series import (
    ReplaceFileRequest,
    ReplaceFileResponse,
    RevealPathRequest,
    RevealPathResponse,
    SeriesImportRequest,
    SeriesImportResponse,
    SeriesLibraryScanResponse,
    SeriesPreviewRequest,
    SeriesProbeRequest,
    SeriesProbeResponse,
    SeriesTmdbMatchRequest,
    SeriesTmdbResponse,
    SeriesTmdbSeasonRequest,
    SeriesTmdbSeasonResponse,
)
from apps.api.streaming import import_progress_stream
from core.domains.filmium import tmdb_client
from core.domains.filmium.series_import_service import (
    SeriesImportError,
    SeriesImportService,
)

router = APIRouter(
    prefix="/api/v1/filmium/libraries",
    tags=["FILMIUM Series"],
)

SeriesImportServiceDependency = Annotated[
    SeriesImportService,
    Depends(get_series_import_service),
]


def _import_error(error: SeriesImportError) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        detail=str(error),
    )


# ==========          PREGLED SERIJE          ==========

@router.post(
    "/{root_id}/series/preview",
    response_model=SeriesLibraryScanResponse,
)
def preview_series(
    root_id: int,
    request: SeriesPreviewRequest,
    service: SeriesImportServiceDependency,
) -> SeriesLibraryScanResponse:
    try:
        root_path, scans = service.preview_library(
            root_id,
            request.relative_directory,
        )
    except SeriesImportError as error:
        raise _import_error(error) from error

    return SeriesLibraryScanResponse.from_domain(scans, root_path)


# ==========          OSVEŽAVANJE BIBLIOTEKE          ==========

class LibraryRefreshResponse(BaseModel):
    """Sažetak osvežavanja FILMIUM biblioteke serija."""

    scanned_series: int
    new_series: int
    posters_added: int
    backdrops_added: int
    season_posters_added: int
    season_backdrops_added: int
    seasons_added: int
    episodes_added: int
    manifests_written: int
    removed_series: int
    movie_folders_scanned: int
    movie_sources_added: int
    errors: int


def _refresh_response(summary) -> LibraryRefreshResponse:
    return LibraryRefreshResponse(
        scanned_series=summary.scanned_series,
        new_series=summary.new_series,
        posters_added=summary.posters_added,
        backdrops_added=summary.backdrops_added,
        season_posters_added=summary.season_posters_added,
        season_backdrops_added=summary.season_backdrops_added,
        seasons_added=summary.seasons_added,
        episodes_added=summary.episodes_added,
        manifests_written=summary.manifests_written,
        removed_series=summary.removed_series,
        movie_folders_scanned=summary.movie_folders_scanned,
        movie_sources_added=summary.movie_sources_added,
        errors=summary.errors,
    )


@router.post(
    "/refresh",
    response_model=LibraryRefreshResponse,
)
def refresh_library(
    service: SeriesImportServiceDependency,
) -> LibraryRefreshResponse:
    """Skenira sve registrovane biblioteke i dopunjava bazu (slike,
    prevode/epizode, nove serije, JSON manifeste). Uklanja serije kojih
    više nema na disku."""

    return _refresh_response(service.refresh_library())


@router.post(
    "/refresh/media/{media_id}",
    response_model=LibraryRefreshResponse,
)
def refresh_single_media(
    media_id: int,
    service: SeriesImportServiceDependency,
) -> LibraryRefreshResponse:
    """Osvežava samo folder jedne serije (dugme na stranici detalja)."""

    return _refresh_response(service.refresh_media(media_id))


# ==========          MEDIA-PROBE EPIZODE (ffprobe)          ==========

@router.post(
    "/{root_id}/series/media-probe",
    response_model=SeriesProbeResponse,
)
def probe_series_episode(
    root_id: int,
    request: SeriesProbeRequest,
    service: SeriesImportServiceDependency,
) -> SeriesProbeResponse:
    try:
        info = service.probe_episode(root_id, request.source)
    except SeriesImportError as error:
        raise _import_error(error) from error

    return SeriesProbeResponse.from_domain(info)


# ==========          OTKRIJ U EXPLORER-U          ==========

@router.post(
    "/{root_id}/reveal",
    response_model=RevealPathResponse,
)
def reveal_path(
    root_id: int,
    request: RevealPathRequest,
    service: SeriesImportServiceDependency,
) -> RevealPathResponse:
    try:
        revealed = service.reveal_file(root_id, request.relative_path)
    except SeriesImportError as error:
        raise _import_error(error) from error

    return RevealPathResponse(revealed=revealed)


@router.post(
    "/{root_id}/replace-file",
    response_model=ReplaceFileResponse,
)
def replace_file(
    root_id: int,
    request: ReplaceFileRequest,
    service: SeriesImportServiceDependency,
) -> ReplaceFileResponse:
    try:
        replaced = service.replace_file(
            root_id,
            request.relative_path,
            request.source_path,
        )
    except SeriesImportError as error:
        raise _import_error(error) from error

    return ReplaceFileResponse(replaced=replaced)


# ==========          SLIČICA EPIZODE (ffmpeg)          ==========

@router.get(
    "/{root_id}/series/episode-thumbnail",
    response_class=FileResponse,
)
def series_episode_thumbnail(
    root_id: int,
    service: SeriesImportServiceDependency,
    source: str = Query(min_length=1),
) -> FileResponse:
    try:
        thumbnail = service.episode_thumbnail(root_id, source)
    except SeriesImportError as error:
        raise _import_error(error) from error

    if thumbnail is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Sličica epizode nije dostupna.",
        )

    return FileResponse(
        thumbnail,
        media_type="image/jpeg",
        headers={
            "Cache-Control": "private, max-age=300",
            "X-Content-Type-Options": "nosniff",
        },
    )


# ==========          REPRODUKCIJA (STREAM)          ==========

_STREAM_CHUNK = 1024 * 1024  # 1 MB


def _guess_video_type(path: Path) -> str:
    guessed, _ = mimetypes.guess_type(str(path))
    if guessed:
        return guessed
    suffix = path.suffix.lower()
    return {
        ".mkv": "video/x-matroska",
        ".mp4": "video/mp4",
        ".m4v": "video/mp4",
        ".webm": "video/webm",
        ".avi": "video/x-msvideo",
        ".mov": "video/quicktime",
    }.get(suffix, "application/octet-stream")


def _parse_range(range_header: str | None, size: int) -> tuple[int, int]:
    """Parsira ``Range: bytes=start-end`` u (start, end) inkluzivno."""

    if not range_header or not range_header.startswith("bytes="):
        return 0, size - 1

    spec = range_header.removeprefix("bytes=").split(",")[0].strip()
    start_text, _, end_text = spec.partition("-")

    try:
        if start_text == "":
            length = int(end_text)
            start = max(0, size - length)
            end = size - 1
        else:
            start = int(start_text)
            end = int(end_text) if end_text else size - 1
    except ValueError:
        return 0, size - 1

    start = max(0, start)
    end = min(end, size - 1)
    if start > end:
        start, end = 0, size - 1
    return start, end


@router.get("/{root_id}/stream")
def stream_media_file(
    root_id: int,
    request: Request,
    service: SeriesImportServiceDependency,
    source: str = Query(min_length=1),
) -> StreamingResponse:
    """Reprodukuje video fajl uz podršku za Range (seek u plejeru)."""

    try:
        path = service.resolve_playable_video(root_id, source)
    except SeriesImportError as error:
        raise _import_error(error) from error

    size = path.stat().st_size
    start, end = _parse_range(request.headers.get("range"), size)
    length = end - start + 1

    def iter_file():
        with path.open("rb") as handle:
            handle.seek(start)
            remaining = length
            while remaining > 0:
                chunk = handle.read(min(_STREAM_CHUNK, remaining))
                if not chunk:
                    break
                remaining -= len(chunk)
                yield chunk

    headers = {
        "Content-Range": f"bytes {start}-{end}/{size}",
        "Accept-Ranges": "bytes",
        "Content-Length": str(length),
        "Cache-Control": "private, max-age=0",
    }

    return StreamingResponse(
        iter_file(),
        status_code=status.HTTP_206_PARTIAL_CONTENT,
        media_type=_guess_video_type(path),
        headers=headers,
    )


# ==========          SPOLJNI PLEJER (VLC)          ==========

class ExternalPlayerResponse(BaseModel):
    vlc_available: bool


class ExternalPlayLaunchResponse(BaseModel):
    launched: bool
    player: str


@router.get(
    "/external-player",
    response_model=ExternalPlayerResponse,
)
def external_player_status() -> ExternalPlayerResponse:
    """Da li je VLC dostupan za spoljnu reprodukciju."""

    from core.domains.filmium import external_player

    return ExternalPlayerResponse(
        vlc_available=external_player.vlc_available(),
    )


@router.post(
    "/{root_id}/play-external",
    response_model=ExternalPlayLaunchResponse,
)
def play_external(
    root_id: int,
    service: SeriesImportServiceDependency,
    source: str = Query(min_length=1),
) -> ExternalPlayLaunchResponse:
    """Otvara video u VLC-u (svi kodeci, bez ograničenja webview-a)."""

    from core.domains.filmium import external_player

    try:
        path = service.resolve_playable_video(root_id, source)
    except SeriesImportError as error:
        raise _import_error(error) from error

    if not external_player.launch_vlc(path):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "VLC nije pronađen. Instaliraj VLC (winget install "
                "VideoLAN.VLC) ili ga dodaj u PATH."
            ),
        )

    return ExternalPlayLaunchResponse(launched=True, player="vlc")


# ==========          MPV (ugradjen plejer)          ==========

class MpvPlayRequest(BaseModel):
    window_id: str | None = None
    geometry: str | None = None
    subtitle: str | None = None


class MpvPlayResponse(BaseModel):
    launched: bool


@router.post(
    "/{root_id}/play-mpv",
    response_model=MpvPlayResponse,
)
def play_mpv(
    root_id: int,
    request: MpvPlayRequest,
    service: SeriesImportServiceDependency,
    source: str = Query(min_length=1),
) -> MpvPlayResponse:
    """Pušta video u ugradjenom mpv-u (overlay lepljen za region)."""

    from core.media_player import mpv_player

    try:
        path = service.resolve_playable_video(root_id, source)
    except SeriesImportError as error:
        raise _import_error(error) from error

    subtitle_path = None
    if request.subtitle:
        try:
            subtitle_path = service.resolve_media_file(
                root_id, request.subtitle
            )
        except SeriesImportError:
            subtitle_path = None

    if not mpv_player.available():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="mpv nije pronađen — instaliraj sistemski mpv (Linux/Kali: `sudo apt install -y mpv`) ili stavi mpv.exe u bin/ (Windows).",
        )

    launched = mpv_player.play(
        path,
        window_id=request.window_id,
        geometry=request.geometry,
        subtitle_path=subtitle_path,
    )
    return MpvPlayResponse(launched=launched)


# ==========          PREKODIRANJE UŽIVO (ffmpeg)          ==========

# Kontejneri koje webview (Chromium/WebView2) pušta direktno.
_DIRECT_CONTAINERS = {".mp4", ".m4v", ".mov", ".webm"}


def _probe_av_codecs(path: Path) -> tuple[str | None, str | None]:
    """Vraća (video_codec, audio_codec) preko ffprobe-a; None na grešku."""

    if shutil.which("ffprobe") is None:
        return None, None

    try:
        result = subprocess.run(
            [
                "ffprobe", "-v", "error",
                "-show_entries", "stream=codec_type,codec_name",
                "-of", "json", str(path),
            ],
            capture_output=True,
            timeout=15,
            check=False,
        )
        data = json.loads(result.stdout or b"{}")
    except (OSError, subprocess.SubprocessError, ValueError):
        return None, None

    video_codec: str | None = None
    audio_codec: str | None = None
    for stream in data.get("streams", []):
        kind = stream.get("codec_type")
        name = stream.get("codec_name")
        if kind == "video" and video_codec is None:
            video_codec = name
        elif kind == "audio" and audio_codec is None:
            audio_codec = name

    return video_codec, audio_codec


class PlayInfoResponse(BaseModel):
    direct_ok: bool
    video_codec: str | None
    audio_codec: str | None


@router.get("/{root_id}/playinfo", response_model=PlayInfoResponse)
def play_info(
    root_id: int,
    service: SeriesImportServiceDependency,
    source: str = Query(min_length=1),
) -> PlayInfoResponse:
    """Da li webview može direktno da pušta fajl (inače → kompatibilni tok)."""

    try:
        path = service.resolve_playable_video(root_id, source)
    except SeriesImportError as error:
        raise _import_error(error) from error

    video_codec, audio_codec = _probe_av_codecs(path)
    container_ok = path.suffix.lower() in _DIRECT_CONTAINERS
    video_ok = video_codec in {"h264", "avc1", "vp8", "vp9", "av1", None}
    audio_ok = audio_codec in {"aac", "mp3", "opus", "vorbis", None}

    return PlayInfoResponse(
        direct_ok=container_ok and video_ok and audio_ok,
        video_codec=video_codec,
        audio_codec=audio_codec,
    )


@router.get("/{root_id}/stream/transcode")
def transcode_media_file(
    root_id: int,
    service: SeriesImportServiceDependency,
    source: str = Query(min_length=1),
) -> StreamingResponse:
    """Prekodira video u H.264/AAC (fragmentovani MP4) za webview plejer.

    Fallback za kodeke koje webview ne podržava (npr. HEVC/H.265). Sekvencijalno
    je (bez preciznog seek-a) i troši CPU, ali radi sa bilo kojim kodekom.
    """

    if shutil.which("ffmpeg") is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="ffmpeg nije dostupan na sistemu.",
        )

    try:
        path = service.resolve_playable_video(root_id, source)
    except SeriesImportError as error:
        raise _import_error(error) from error

    video_codec, audio_codec = _probe_av_codecs(path)

    # H.264 sliku samo prepakujemo (brzo, bez gubitka); ostalo prekodiramo.
    if video_codec in {"h264", "avc1"}:
        video_args = ["-c:v", "copy"]
    else:
        video_args = [
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "23",
        ]

    # AAC/MP3 zvuk prepakujemo; AC3/DTS/EAC3/TrueHD prekodiramo u AAC.
    if audio_codec in {"aac", "mp3"}:
        audio_args = ["-c:a", "copy"]
    else:
        audio_args = ["-c:a", "aac", "-b:a", "192k", "-ac", "2"]

    command = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel", "error",
        "-i", str(path),
        *video_args,
        *audio_args,
        "-movflags", "frag_keyframe+empty_moov+default_base_moof",
        "-f", "mp4",
        "pipe:1",
    ]

    process = subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
    )

    def iter_transcode():
        try:
            while True:
                chunk = process.stdout.read(64 * 1024)
                if not chunk:
                    break
                yield chunk
        finally:
            if process.poll() is None:
                process.kill()
            try:
                process.stdout.close()
            except OSError:
                pass
            process.wait()

    return StreamingResponse(
        iter_transcode(),
        media_type="video/mp4",
        headers={"Cache-Control": "no-store"},
    )


# ==========          PREVODI (WebVTT)          ==========

def _attempt_decode(raw: bytes, encoding: str) -> str | None:
    """Pokusaj dekodiranja jednim kodiranjem; None ako ne uspe."""

    try:
        return raw.decode(encoding)
    except UnicodeDecodeError:
        return None


def _decode_subtitle(raw: bytes) -> str:
    """Dekodira prevod probajući UTF-8 pa česte kodne strane za srpski."""

    for encoding in ("utf-8-sig", "utf-8", "cp1250", "iso-8859-2", "latin-1"):
        decoded = _attempt_decode(raw, encoding)
        if decoded is not None:
            return decoded
    return raw.decode("utf-8", errors="replace")


_SRT_TIME = re.compile(
    r"(\d{2}:\d{2}:\d{2}),(\d{3})",
)


def _to_webvtt(text: str, suffix: str) -> str:
    """Pretvara SRT u WebVTT; VTT vraća kako jeste."""

    if suffix == ".vtt" or text.lstrip().startswith("WEBVTT"):
        return text

    body = _SRT_TIME.sub(r"\1.\2", text.replace("\r\n", "\n"))
    return "WEBVTT\n\n" + body


@router.get("/{root_id}/subtitle")
def stream_subtitle(
    root_id: int,
    service: SeriesImportServiceDependency,
    source: str = Query(min_length=1),
) -> StreamingResponse:
    """Servira prevod kao WebVTT (za <track> u plejeru)."""

    try:
        path = service.resolve_media_file(root_id, source)
    except SeriesImportError as error:
        raise _import_error(error) from error

    try:
        raw = path.read_bytes()
    except OSError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Prevod nije dostupan.",
        ) from error

    vtt = _to_webvtt(_decode_subtitle(raw), path.suffix.lower())

    return StreamingResponse(
        iter([vtt.encode("utf-8")]),
        media_type="text/vtt; charset=utf-8",
        headers={"Cache-Control": "private, max-age=60"},
    )


# ==========          TMDB OBOGAĆIVANJE          ==========

@router.post(
    "/tmdb/series-match",
    response_model=SeriesTmdbResponse,
)
def tmdb_series_match(
    request: SeriesTmdbMatchRequest,
) -> SeriesTmdbResponse:
    configured = tmdb_client.is_tmdb_available()
    series = (
        tmdb_client.match_series(request.title, request.year)
        if configured
        else None
    )
    return SeriesTmdbResponse.from_domain(series, configured)


@router.post(
    "/tmdb/season",
    response_model=SeriesTmdbSeasonResponse,
)
def tmdb_series_season(
    request: SeriesTmdbSeasonRequest,
) -> SeriesTmdbSeasonResponse:
    episodes = (
        tmdb_client.get_season_episodes(
            request.tmdb_id,
            request.season_number,
        )
        if tmdb_client.is_tmdb_available()
        else []
    )
    return SeriesTmdbSeasonResponse.from_domain(episodes)


# ==========          UVOZ SERIJE          ==========

@router.post(
    "/{root_id}/series/confirm",
    response_model=SeriesImportResponse,
)
def confirm_series_import(
    root_id: int,
    request: SeriesImportRequest,
    service: SeriesImportServiceDependency,
) -> SeriesImportResponse:
    try:
        result = service.import_from_library(
            root_id,
            request.relative_directory,
            target_library_root_id=request.target_library_root_id,
            confirmed=request.confirmed,
            content_mode=request.content_mode,
            synchronized=request.synchronized,
        )
    except SeriesImportError as error:
        raise _import_error(error) from error

    return SeriesImportResponse.from_domain(result)


@router.post("/{root_id}/series/confirm/stream")
def confirm_series_import_stream(
    root_id: int,
    request: SeriesImportRequest,
    service: SeriesImportServiceDependency,
) -> StreamingResponse:
    """Kao ``series/confirm``, ali strimuje per-fajl progres (SSE)."""

    def run(on_progress):
        return service.import_from_library(
            root_id,
            request.relative_directory,
            target_library_root_id=request.target_library_root_id,
            confirmed=request.confirmed,
            on_progress=on_progress,
            content_mode=request.content_mode,
            synchronized=request.synchronized,
        )

    return import_progress_stream(
        run,
        lambda result: SeriesImportResponse.from_domain(result).model_dump(
            mode="json"
        ),
    )
