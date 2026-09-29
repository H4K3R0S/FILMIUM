# ========== BENCODE ČITAČ ==========
# Namerno mali čitač `.torrent` zapisa, bez nove zavisnosti. Koriste ga
# engine (info hash pri dodavanju) i čitač fajlova (kartice pronađenih
# torrenta, pre nego što ijedan torrent stigne do qBittorrent-a).
from __future__ import annotations

import hashlib
from typing import Any


def bdecode(data: bytes, index: int = 0) -> tuple[Any, int]:
    """Dekodira jednu bencode vrednost; vraća vrednost i sledeću poziciju."""

    marker = data[index : index + 1]

    if marker == b"i":
        end = data.index(b"e", index)
        return int(data[index + 1 : end]), end + 1

    if marker == b"l":
        index += 1
        items: list[Any] = []
        while data[index : index + 1] != b"e":
            value, index = bdecode(data, index)
            items.append(value)
        return items, index + 1

    if marker == b"d":
        index += 1
        mapping: dict[Any, Any] = {}
        while data[index : index + 1] != b"e":
            key, index = bdecode(data, index)
            value, index = bdecode(data, index)
            mapping[key] = value
        return mapping, index + 1

    if marker.isdigit():
        colon = data.index(b":", index)
        length = int(data[index:colon])
        start = colon + 1
        return data[start : start + length], start + length

    raise ValueError(f"Neispravan bencode na poziciji {index}.")


def info_span(raw: bytes) -> tuple[int, int] | None:
    """Raspon bajtova `info` rečnika u `.torrent` zapisu.

    Info hash je SHA-1 baš nad tim rasponom, pa se `info` NE sme ponovo
    kodirati — redosled i oblik moraju ostati tačno kakvi su u fajlu.
    """

    if raw[:1] != b"d":
        return None

    index = 1
    try:
        while index < len(raw) and raw[index : index + 1] != b"e":
            key, index = bdecode(raw, index)
            start = index
            _value, index = bdecode(raw, index)
            if key == b"info":
                return start, index
    except (ValueError, IndexError):
        return None

    return None


def info_hash_of(raw: bytes) -> str | None:
    """Info hash `.torrent` zapisa kao heks niska, ili `None` za neispravan."""

    span = info_span(raw)
    if span is None:
        return None

    start, end = span
    return hashlib.sha1(raw[start:end]).hexdigest()  # nosec B324 -- .torrent info-hash je po protokolu SHA1 (identitet, ne bezbednosni izbor)
