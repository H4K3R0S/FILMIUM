"""Čitanje dimenzija slike bez spoljnih zavisnosti.

Parsira zaglavlja najčešćih formata (PNG, JPEG, GIF, WebP) da bi se
poster (portret ~2:3) razlikovao od backdropa (pejzaž ~16:9) kada naziv
fajla ne otkriva ulogu.
"""

from pathlib import Path

# SOF markeri koji nose dimenzije (SOF0–SOF15 bez DHT/JPG/DAC).
_JPEG_SOF_MARKERS = {
    0xC0, 0xC1, 0xC2, 0xC3,
    0xC5, 0xC6, 0xC7,
    0xC9, 0xCA, 0xCB,
    0xCD, 0xCE, 0xCF,
}


def read_image_dimensions(path: Path) -> tuple[int, int] | None:
    """Vraća (širina, visina) slike ili ``None`` ako nije prepoznato."""

    try:
        with path.open("rb") as handle:
            header = handle.read(32)

            if header[:8] == b"\x89PNG\r\n\x1a\n":
                if len(header) >= 24:
                    return (
                        int.from_bytes(header[16:20], "big"),
                        int.from_bytes(header[20:24], "big"),
                    )
                return None

            if header[:6] in (b"GIF87a", b"GIF89a"):
                return (
                    int.from_bytes(header[6:8], "little"),
                    int.from_bytes(header[8:10], "little"),
                )

            if header[:4] == b"RIFF" and header[8:12] == b"WEBP":
                return _webp_dimensions(header)

            if header[:2] == b"\xff\xd8":
                return _jpeg_dimensions(path)
    except OSError:
        return None

    return None


def _webp_dimensions(header: bytes) -> tuple[int, int] | None:
    fourcc = header[12:16]

    if fourcc == b"VP8X" and len(header) >= 30:
        return (
            1 + int.from_bytes(header[24:27], "little"),
            1 + int.from_bytes(header[27:30], "little"),
        )

    if fourcc == b"VP8 " and len(header) >= 30:
        return (
            int.from_bytes(header[26:28], "little") & 0x3FFF,
            int.from_bytes(header[28:30], "little") & 0x3FFF,
        )

    return None


def _jpeg_dimensions(path: Path) -> tuple[int, int] | None:
    try:
        with path.open("rb") as handle:
            handle.read(2)  # preskoči SOI

            while True:
                byte = handle.read(1)

                if not byte:
                    return None

                if byte != b"\xff":
                    continue

                marker = handle.read(1)
                while marker == b"\xff":
                    marker = handle.read(1)

                if not marker:
                    return None

                code = marker[0]

                # Markeri bez segmenta (RSTn, SOI, EOI, TEM).
                if 0xD0 <= code <= 0xD9 or code == 0x01:
                    continue

                length_bytes = handle.read(2)
                if len(length_bytes) < 2:
                    return None

                length = int.from_bytes(length_bytes, "big")

                if code in _JPEG_SOF_MARKERS:
                    data = handle.read(5)
                    if len(data) < 5:
                        return None

                    return (
                        int.from_bytes(data[3:5], "big"),
                        int.from_bytes(data[1:3], "big"),
                    )

                handle.seek(length - 2, 1)
    except OSError:
        return None
