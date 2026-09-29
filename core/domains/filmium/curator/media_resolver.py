# ========== RAZREŠAVANJE NASLOV -> media_id ==========
# Model iz razgovora dobije naslov filma ("pusti Matriks"), ne numerički id
# iz baze. Ovaj resolver mapira slobodan naslov na id najbližeg naslova u
# biblioteci, po preklapanju normalizovanih reči. Kod upisa je oprezan: ako
# dva naslova jednako pogađaju upit, vraća None (ne pogađa nasumično).
from __future__ import annotations

import re
import unicodedata
from collections.abc import Callable, Sequence
from typing import Any

# list_provider() -> sekvenca stavki sa .id i .title (npr. MediaRepository.list_all)
ListProvider = Callable[[], Sequence[Any]]


def _normalizuj(text: str) -> set[str]:
    """Skup normalizovanih reči: mala slova, bez dijakritike, samo alfanumerik."""

    razlozeno = unicodedata.normalize("NFKD", text.lower())
    bez_dijakritike = "".join(c for c in razlozeno if not unicodedata.combining(c))
    return {t for t in re.split(r"[^0-9a-z]+", bez_dijakritike) if t}


def _polje(item: Any, ime: str) -> str:
    vrednost = getattr(item, ime, None)
    return str(vrednost) if vrednost else ""


def _kanon(reci: set[str]) -> str:
    """Kanonski (sortiran) oblik skupa reči — za poređenje na TAČNO poklapanje."""
    return " ".join(sorted(reci))


# Tier-skorovi: tačan naslov > tačan engleski naslov > preklapanje reči (0..N).
_EXACT_TITLE = 1000
_EXACT_ENGLISH = 900


def _skor(upit: set[str], upit_kanon: str, item: Any) -> int:
    """Skor poklapanja upita sa stavkom. Tačan naslov (pa engleski) pobeđuje puko
    preklapanje reči — inače „moana" jednako pogađa „Moana", „Vajana"/eng „Moana"
    i „Moana 2“ (svi skor 1) → dvosmisleno."""
    naslov = _normalizuj(_polje(item, "title"))
    eng = _normalizuj(_polje(item, "english_title"))
    if _kanon(naslov) == upit_kanon:
        return _EXACT_TITLE
    if eng and _kanon(eng) == upit_kanon:
        return _EXACT_ENGLISH
    return len(upit & (naslov | eng))


class MediaResolver:
    """Naslov iz razgovora -> id najbližeg naslova u biblioteci."""

    def __init__(self, list_provider: ListProvider) -> None:
        self._list_provider = list_provider

    def resolve(self, title: str) -> int | None:
        """Id najbližeg naslova, ili None ako nema poklapanja / dvosmisleno je."""

        upit = _normalizuj(title or "")
        if not upit:
            return None
        upit_kanon = _kanon(upit)  # kanonski oblik za TAČNO poklapanje

        najbolji_skor = 0
        najbolji_id: int | None = None
        dvosmisleno = False

        for item in self._list_provider():
            skor = _skor(upit, upit_kanon, item)
            if skor == 0:
                continue
            if skor > najbolji_skor:
                najbolji_skor = skor
                najbolji_id = getattr(item, "id", None)
                dvosmisleno = False
            elif skor == najbolji_skor and getattr(item, "id", None) != najbolji_id:
                dvosmisleno = True

        if najbolji_id is None or dvosmisleno:
            return None
        return najbolji_id

    def candidates(self, title: str, limit: int = 20) -> list[int]:
        """Id-jevi naslova koji NAJBOLJE (jednako) pogađaju upit — grupa sa
        maksimalnim skorom. Jedan → jasan pogodak; više → dvosmisleno (za
        filtriran prikaz „izaberi jedan"). Prazno kad nema poklapanja."""

        upit = _normalizuj(title or "")
        if not upit:
            return []
        upit_kanon = _kanon(upit)

        bodovani: list[tuple[int, int]] = []
        for item in self._list_provider():
            skor = _skor(upit, upit_kanon, item)
            iid = getattr(item, "id", None)
            if skor > 0 and iid is not None:
                bodovani.append((skor, iid))
        if not bodovani:
            return []
        max_skor = max(s for s, _ in bodovani)
        return [iid for s, iid in bodovani if s == max_skor][:limit]
