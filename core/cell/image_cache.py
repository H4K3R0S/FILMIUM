"""Deljeni image-cache sloj — WebP sličice za 60 FPS canvas (v.
UNAPREDJENJE/01-ARHITEKTURA/07-image-cache-engine.md).

Princip: canvas u UI čita SAMO male WebP keš sličice; originalna slika (4K
poster, backdrop, screenshot) se učitava tek na eksplicitan klik (viewer).
FILMIUM ovo DELIMIČNO već ima (`cache_all_posters.py`,
`_sync_catalog_visual_assets`, asset endpoint sa `Cache-Control`) — OVAJ
MODUL TO NE DIRA. Ovo je nov, opcion, deljen sloj koji buduće funkcije (u
bilo kom domenu) mogu da pozovu; FILMIUM-ovo postojeće keširanje ostaje
netaknuto dok se neko svesno ne odluči da ga poveže na ovo (v. `[FaN]` u
arhitekturi).

Backend: `Pillow` (lenj uvoz UNUTAR funkcije — ovaj modul ne sme biti
"težak" pri uvozu) ako je uvoziv u tekućem venv-u; inače `ImageMagick`
(`convert`/`magick`, sistemski binarni alat) preko `subprocess`. Bez ijedne
obavezne nove pip zavisnosti.

Ovaj fajl je DELJEN — identičan u sva 4 domena (core/cell/ konvencija, isto
kao core/cell/jobs.py i core/cell/database.py). Kopira se u
`~/ai/domains/<domen>/core/cell/image_cache.py`. NAPOMENA: FILMIUM ima i
Windows stranu na disku F (v. memorija „FILMIUM & domains setup") — ova
kopija ide SAMO na Linux stranu (`~/ai/domains/filmium`), F: nije dirana.

Sve funkcije su tolerantne: original koji ne postoji, nepodržan format ili
alat koji padne → `None`, NIKAD izuzetak ka pozivaocu.
"""

from __future__ import annotations

import hashlib
import shutil
import subprocess
from pathlib import Path

from core.foundation.paths import core_paths

# ----------          PODRAZUMEVANE VREDNOSTI          ----------
THUMB_WIDTH = 300
THUMB_QUALITY = 72
BLUR_WIDTH = 100
BLUR_QUALITY = 45
_SUBPROCESS_TIMEOUT_S = 30


def ensure_thumb(
    orig_path: str | Path,
    kind: str = "poster",
    width: int = THUMB_WIDTH,
    quality: int = THUMB_QUALITY,
) -> str | None:
    """
    Napravi (ili vrati postojeću) WebP sličicu širine `width`.

    Keš stoji na `<core_paths.data>/cache/<kind>/<hash>.webp` —
    `core_paths` je već (auto-detekcijom korena) domenski, pa ovde nema
    hardkodovanog imena domena. Idempotentno: ako keš već postoji i
    original nije menjan posle njega, ništa se ne generiše ponovo.

    Args:
        orig_path: Putanja do originalne slike na disku.
        kind: Logička vrsta ("poster", "backdrop", "screenshot", ...) —
            određuje potfolder keša.
        width: Ciljna širina sličice u pikselima (visina se skalira
            srazmerno).
        quality: WebP kvalitet (0-100).

    Returns:
        Putanja do keš fajla (string) ili `None` ako original ne postoji,
        format nije čitljiv, ili su i Pillow i ImageMagick nedostupni/pali.
    """
    return _ensure(orig_path, kind=kind, width=width, quality=quality, blur=False)


def ensure_blur(
    orig_path: str | Path,
    kind: str = "backdrop",
    width: int = BLUR_WIDTH,
) -> str | None:
    """
    Napravi (ili vrati postojeću) jako umanjenu, zamućenu WebP pozadinu
    (LQIP — low quality placeholder dok se original ne učita u UI).

    Args:
        orig_path: Putanja do originalne slike na disku.
        kind: Logička vrsta — određuje potfolder keša (deli folder sa
            `ensure_thumb` istog `kind`-a; hash uključuje širinu i
            oznaku zamućenja pa nema sudara imena).
        width: Ciljna širina (podrazumevano 100 px — namerno sitno).

    Returns:
        Putanja do keš fajla (string) ili `None` na grešku (v.
        `ensure_thumb`).
    """
    return _ensure(orig_path, kind=kind, width=width, quality=BLUR_QUALITY, blur=True)


# ----------          INTERNO          ----------


def _ensure(
    orig_path: str | Path,
    *,
    kind: str,
    width: int,
    quality: int,
    blur: bool,
) -> str | None:
    try:
        if width <= 0:
            return None
        orig = Path(orig_path)
        if not orig.is_file():
            return None

        cache_path = _cache_path(orig, kind, width, blur)
        if _is_fresh(cache_path, orig):
            return str(cache_path)

        safe_quality = max(1, min(100, quality))
        ok = _resize_pillow(orig, cache_path, width, safe_quality, blur)
        if not ok:
            ok = _resize_imagemagick(orig, cache_path, width, safe_quality, blur)
        if not ok or not cache_path.is_file() or cache_path.stat().st_size == 0:
            return None
        return str(cache_path)
    except Exception:  # noqa: BLE001
        return None


def _cache_path(orig: Path, kind: str, width: int, blur: bool) -> Path:
    """`<core_paths.data>/cache/<kind>/<hash>.webp` — hash od (apsolutna
    putanja originala + širina + oznaka zamućenja) da isti original na
    dve različite širine/varijante ne deli isti keš fajl."""
    try:
        resolved = str(orig.resolve())
    except OSError:
        resolved = str(orig)
    digest_src = f"{resolved}|{width}|{'blur' if blur else 'sharp'}"
    digest = hashlib.sha256(digest_src.encode("utf-8")).hexdigest()[:24]
    return core_paths.data / "cache" / kind / f"{digest}.webp"


def _is_fresh(cache_path: Path, orig: Path) -> bool:
    """Idempotencija: keš je „svež" ako postoji i original mu nije noviji."""
    if not cache_path.is_file():
        return False
    try:
        return cache_path.stat().st_mtime >= orig.stat().st_mtime
    except OSError:
        return False


def _resize_pillow(
    orig: Path,
    out_path: Path,
    width: int,
    quality: int,
    blur: bool,
) -> bool:
    """Pillow backend. Lenj uvoz — ako Pillow nije instaliran u ovom
    venv-u, samo vrati `False` (poziva se `_resize_imagemagick`)."""
    try:
        from PIL import Image, ImageFilter
    except ImportError:
        return False

    try:
        with Image.open(orig) as img:
            if img.mode in ("RGB", "RGBA"):
                src = img
            elif img.mode in ("P", "LA") or "transparency" in img.info:
                src = img.convert("RGBA")
            else:
                src = img.convert("RGB")

            ratio = width / float(src.width)
            height = max(1, round(src.height * ratio))
            resized = src.resize((width, height), Image.LANCZOS)
            if blur:
                resized = resized.filter(ImageFilter.GaussianBlur(radius=2))

            out_path.parent.mkdir(parents=True, exist_ok=True)
            resized.save(out_path, format="WEBP", quality=quality)
        return True
    except Exception:  # noqa: BLE001
        return False


def _resize_imagemagick(
    orig: Path,
    out_path: Path,
    width: int,
    quality: int,
    blur: bool,
) -> bool:
    """`ImageMagick` fallback (`convert` ili `magick`, sistemski binarni
    alat) — koristi se kad Pillow nije uvoziv u tekućem venv-u."""
    binary = shutil.which("convert") or shutil.which("magick")
    if not binary:
        return False

    out_path.parent.mkdir(parents=True, exist_ok=True)
    args = [binary, str(orig), "-resize", f"{width}x", "-quality", str(quality)]
    if blur:
        args += ["-blur", "0x8"]
    args.append(str(out_path))

    try:
        result = subprocess.run(
            args,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
            timeout=_SUBPROCESS_TIMEOUT_S,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    return result.returncode == 0
