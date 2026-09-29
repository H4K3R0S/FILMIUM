# ========== KATEGORIJE BIBLIOTEKE ==========
# Rutiranje uvoza u kategorijske foldere ispod korena biblioteke.
# Šema: Filmovi / Crtani / Serije/{Filmske serije, Crtane serije}.
from __future__ import annotations

from collections.abc import Iterable

# Nazivi foldera (korisnički vidljivi — srpski).
MOVIES_DIR = "Filmovi"
CARTOONS_DIR = "Crtani"
SERIES_DIR = "Serije"
SERIES_LIVE_DIR = "Filmske serije"
SERIES_ANIMATED_DIR = "Crtane serije"

# Oznake žanra koje znače "animirano" (posle normalizacije/casefold).
_ANIMATION_KEYS = frozenset({
    "animacija", "animation", "animated", "anime", "crtani", "cartoon",
})


def is_animated(genres: Iterable[str] | None) -> bool:
    # Da li kolekcija žanrova ukazuje na animirani sadržaj.
    for genre in genres or ():
        if str(genre).strip().casefold() in _ANIMATION_KEYS:
            return True
    return False


def movie_category_parts(genres: Iterable[str] | None) -> tuple[str, ...]:
    # Film → Crtani ako je animiran, inače Filmovi.
    return (CARTOONS_DIR,) if is_animated(genres) else (MOVIES_DIR,)


def series_category_parts(genres: Iterable[str] | None) -> tuple[str, ...]:
    # Serija → Serije/Crtane serije ako je animirana, inače Serije/Filmske serije.
    if is_animated(genres):
        return (SERIES_DIR, SERIES_ANIMATED_DIR)
    return (SERIES_DIR, SERIES_LIVE_DIR)


# ==========          KATEGORIJSKI KORENI (Strano/Domace/Animirano)          ==========

# Mapiranje content_category → korenski folder kategorije.
CATEGORY_ROOT: dict[str, str] = {
    "regular": "Strano",
    "domestic": "Domace",
    "animated": "Animirano",
}


def movie_base_parts(content_mode: str) -> tuple[str, str]:
    # Film → <kategorija>/Filmovi (regular=Strano, domestic=Domace, animated=Animirano).
    return (CATEGORY_ROOT.get(content_mode, "Strano"), MOVIES_DIR)


def series_base_parts(content_mode: str) -> tuple[str, str]:
    # Serija → <kategorija>/Serije (bez žanrovskog pod-splita).
    return (CATEGORY_ROOT.get(content_mode, "Strano"), SERIES_DIR)


def infer_content_mode_from_parts(parts: set[str]) -> str:
    # Kategorija iz skupa segmenata putanje (casefold); novi + stari nazivi.
    if "animirano" in parts:
        return "animated"
    if "domace" in parts or "domaci" in parts or "domaći" in parts:
        return "domestic"
    return "regular"
