# ==========          TRANSLITERACIJA ĆIRILICA → LATINICA          ==========
"""Deterministička srpska transliteracija, bez mreže.

Koristi se u auto-update pipeline-u da domaći naslov i opis budu na srpskoj
latinici — bilo transliteracijom postojeće ćirilice, bilo posle prevoda (koji
Google vraća na ćirilici za jezik ``sr``).
"""

# Mala slova: ćirilica → latinica (digrafi za љ, њ, џ).
_MAP = {
    "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "ђ": "đ", "е": "e",
    "ж": "ž", "з": "z", "и": "i", "ј": "j", "к": "k", "л": "l", "љ": "lj",
    "м": "m", "н": "n", "њ": "nj", "о": "o", "п": "p", "р": "r", "с": "s",
    "т": "t", "ћ": "ć", "у": "u", "ф": "f", "х": "h", "ц": "c", "ч": "č",
    "џ": "dž", "ш": "š",
}


def is_cyrillic(text: str) -> bool:
    """Tačno ako tekst sadrži bar jedan ćirilični znak (U+0400–U+04FF)."""

    return any("Ѐ" <= ch <= "ӿ" for ch in text or "")


def cyrillic_to_latin(text: str) -> str:
    """Pretvara srpsku ćirilicu u latinicu uz pravilne digrafe i velika slova.

    Digraf (Lj/Nj/Dž) piše se velikim slovima u celini samo ako je i sledeći
    znak veliko slovo (npr. ``ЊЕ`` → ``NJE``), inače kao ``Nj``. Ne-ćirilične
    znakove propušta netaknute.
    """

    if not text:
        return text

    result: list[str] = []
    for index, ch in enumerate(text):
        latin = _MAP.get(ch.lower())
        if latin is None:
            result.append(ch)
            continue
        if ch.isupper():
            if len(latin) > 1:
                nxt = text[index + 1] if index + 1 < len(text) else ""
                latin = latin.upper() if nxt.isupper() else latin.capitalize()
            else:
                latin = latin.upper()
        result.append(latin)
    return "".join(result)


# ==========          LATINICA → ĆIRILICA (obrnuti smer)          ==========
# Digrafi (dž, lj, nj) se mapiraju PRE pojedinačnih slova. `c` bez kvačice → ц.
import re as _re

_DIGRAPHS = (("dž", "џ"), ("lj", "љ"), ("nj", "њ"))
_LAT2CYR = {lat: cyr for cyr, lat in _MAP.items()}  # jednoznačna slova (obrni _MAP)


def _cyr_case(cyr: str, first_upper: bool, all_upper: bool) -> str:
    """Vrati ćirilicu u ispravnom padu (za digrafe: Љ vs Љ celom velika)."""
    if all_upper:
        return cyr.upper()
    if first_upper:
        return cyr[:1].upper() + cyr[1:]
    return cyr


def latin_to_cyrillic(text: str) -> str:
    """Srpska latinica → ćirilica (digrafi dž/lj/nj → џ/љ/њ). Ne-slova propušta.

    NAPOMENA: primenjivati na ČIST tekst (bez HTML tagova) — koristi
    `transliterate_srt` za .srt jer preskače tagove i vremensku strukturu.
    """
    if not text:
        return text
    out: list[str] = []
    i = 0
    n = len(text)
    while i < n:
        two = text[i:i + 2].lower()
        digraph = next((cyr for lat, cyr in _DIGRAPHS if lat == two), None)
        if digraph is not None:
            a, b = text[i], text[i + 1]
            out.append(_cyr_case(digraph, a.isupper(), a.isupper() and b.isupper()))
            i += 2
            continue
        ch = text[i]
        cyr = _LAT2CYR.get(ch.lower())
        if cyr is None:
            out.append(ch)
        else:
            out.append(cyr.upper() if ch.isupper() else cyr)
        i += 1
    return "".join(out)


def detect_script(text: str) -> str:
    """'cyrillic' ako ima ijedan ćirilični znak, inače 'latin'."""
    return "cyrillic" if is_cyrillic(text or "") else "latin"


_TAG_SPLIT = _re.compile(r"(<[^>]*>)")


def _apply_outside_tags(line: str, fn) -> str:
    """Primeni `fn` samo van HTML tagova (<...> se ne dira)."""
    return "".join(
        part if part.startswith("<") else fn(part)
        for part in _TAG_SPLIT.split(line)
    )


def transliterate_srt(text: str, *, to_cyrillic: bool) -> str:
    """Transliteruj .srt u drugo pismo, čuvajući indeks/timecode i HTML tagove."""
    fn = latin_to_cyrillic if to_cyrillic else cyrillic_to_latin
    out: list[str] = []
    for line in text.splitlines(keepends=True):
        if line.strip().isdigit() or "-->" in line:
            out.append(line)  # struktura (indeks / vreme) netaknuta
        else:
            out.append(_apply_outside_tags(line, fn))
    return "".join(out)
