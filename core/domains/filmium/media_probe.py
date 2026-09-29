"""Media-probe sloj koji čita tehničke podatke videa preko ffprobe.

Ovaj modul je namerno tolerantan: ako ffprobe nije instaliran ili probe
ne uspe, vraća ``None`` umesto da baca grešku. Time uvoz i pregled rade
i bez spoljnog alata, a tehničke informacije se prikazuju kada su dostupne.
"""

import json
import shutil
import subprocess
from pathlib import Path

from core.domains.filmium.library_import_models import MediaTechnicalInfo

# ==========          OZNAKE KODEKA          ==========

_VIDEO_CODEC_LABELS = {
    "h264": "H.264",
    "avc": "H.264",
    "hevc": "HEVC",
    "h265": "HEVC",
    "av1": "AV1",
    "vp9": "VP9",
    "vp8": "VP8",
    "mpeg4": "MPEG-4",
    "mpeg2video": "MPEG-2",
    "vc1": "VC-1",
}

_AUDIO_CODEC_LABELS = {
    "aac": "AAC",
    "ac3": "AC3",
    "eac3": "E-AC3",
    "dts": "DTS",
    "truehd": "TrueHD",
    "flac": "FLAC",
    "mp3": "MP3",
    "opus": "Opus",
    "vorbis": "Vorbis",
    "pcm_s16le": "PCM",
    "pcm_s24le": "PCM",
}


# ==========          POMOĆNE FUNKCIJE          ==========

def _as_int(value: object) -> int | None:
    try:
        return int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None


def _as_float(value: object) -> float | None:
    try:
        return float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None


def _codec_label(
    table: dict[str, str],
    codec_name: object,
) -> str | None:
    if not isinstance(codec_name, str) or not codec_name:
        return None

    return table.get(codec_name.casefold(), codec_name.upper())


def _parse_frame_rate(value: object) -> float | None:
    """Pretvara ffprobe zapis kadrova ("24000/1001") u float 23.976."""

    if not isinstance(value, str) or not value:
        return None

    if "/" in value:
        numerator, _, denominator = value.partition("/")
        top = _as_float(numerator)
        bottom = _as_float(denominator)

        if top is None or not bottom:
            return None

        return round(top / bottom, 3)

    parsed = _as_float(value)
    return None if parsed is None else round(parsed, 3)


# ==========          PARSIRANJE FFPROBE IZLAZA          ==========

def parse_ffprobe_output(
    data: dict[str, object],
) -> MediaTechnicalInfo | None:
    """Gradi tehničke informacije iz već parsiranog ffprobe JSON-a."""

    streams = data.get("streams")

    if not isinstance(streams, list):
        return None

    video_stream = next(
        (
            stream
            for stream in streams
            if isinstance(stream, dict)
            and stream.get("codec_type") == "video"
        ),
        None,
    )

    if video_stream is None:
        return None

    audio_stream = next(
        (
            stream
            for stream in streams
            if isinstance(stream, dict)
            and stream.get("codec_type") == "audio"
        ),
        None,
    )

    frame_rate = _parse_frame_rate(
        video_stream.get("avg_frame_rate")
        or video_stream.get("r_frame_rate")
    )

    format_section = data.get("format")
    duration = (
        _as_float(format_section.get("duration"))
        if isinstance(format_section, dict)
        else None
    )

    bit_rate = None
    if isinstance(format_section, dict):
        bit_rate = _as_int(format_section.get("bit_rate"))
    if bit_rate is None:
        bit_rate = _as_int(video_stream.get("bit_rate"))

    return MediaTechnicalInfo(
        width=_as_int(video_stream.get("width")),
        height=_as_int(video_stream.get("height")),
        video_codec=_codec_label(
            _VIDEO_CODEC_LABELS,
            video_stream.get("codec_name"),
        ),
        frame_rate=frame_rate,
        audio_codec=(
            _codec_label(
                _AUDIO_CODEC_LABELS,
                audio_stream.get("codec_name"),
            )
            if audio_stream is not None
            else None
        ),
        audio_channels=(
            _as_int(audio_stream.get("channels"))
            if audio_stream is not None
            else None
        ),
        duration_seconds=duration,
        bit_rate=bit_rate,
        is_hdr=_detect_hdr(video_stream),
        audio_language=_stream_language(audio_stream),
    )


def _detect_hdr(video_stream: dict[str, object]) -> bool:
    """Prepoznaje HDR iz color_transfer/color_primaries video stream-a."""

    transfer = video_stream.get("color_transfer")
    if isinstance(transfer, str) and transfer.casefold() in {
        "smpte2084",
        "arib-std-b67",
    }:
        return True

    primaries = video_stream.get("color_primaries")
    return isinstance(primaries, str) and primaries.casefold() == "bt2020"


def _stream_language(stream: dict[str, object] | None) -> str | None:
    """Jezik audio stream-a iz ``tags.language`` (npr. „srp")."""

    if not isinstance(stream, dict):
        return None
    tags = stream.get("tags")
    if not isinstance(tags, dict):
        return None
    language = tags.get("language")
    return language if isinstance(language, str) and language else None


# ==========          POKRETANJE FFPROBE-A          ==========

def is_probe_available() -> bool:
    """Da li je ffprobe dostupan na sistemu."""

    return shutil.which("ffprobe") is not None


def probe_video_file(path: Path) -> MediaTechnicalInfo | None:
    """Vraća tehničke podatke videa ili ``None`` ako probe nije moguć."""

    if shutil.which("ffprobe") is None:
        return None

    try:
        completed = subprocess.run(
            [
                "ffprobe",
                "-v",
                "quiet",
                "-print_format",
                "json",
                "-show_streams",
                "-show_format",
                str(path),
            ],
            capture_output=True,
            text=True,
            timeout=20,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None

    if completed.returncode != 0 or not completed.stdout:
        return None

    try:
        data = json.loads(completed.stdout)
    except (ValueError, TypeError):
        return None

    if not isinstance(data, dict):
        return None

    return parse_ffprobe_output(data)
