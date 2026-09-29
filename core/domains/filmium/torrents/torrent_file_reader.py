# ========== ČITAČ .torrent FAJLOVA ==========
# Čita sadržaj .torrent fajla lokalno, bez qBittorrent-a: ime, info hash i
# spisak fajlova. Odatle stranica Torrenti pravi karticu sa štikliranjem i
# pre nego što je torrent uopšte predat klijentu.
from __future__ import annotations

import os

from core.domains.filmium.torrents.torrent_bencode import bdecode, info_hash_of
from core.domains.filmium.torrents.torrent_models import (
    DiscoveredFile,
    DiscoveredTorrent,
)

TORRENT_EXTENSION = ".torrent"


def _text(value: object, fallback: str = "") -> str:
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    if isinstance(value, str):
        return value
    return fallback


def _join_path(parts: object) -> str:
    if not isinstance(parts, list):
        return ""
    return "/".join(_text(part) for part in parts if _text(part))


def _files_of(info: dict[object, object]) -> tuple[DiscoveredFile, ...]:
    """Fajlovi torrenta; jednofajlni torrent daje tačno jedan zapis.

    Redosled je redosled iz `info` rečnika — isti onaj po kome qBittorrent
    dodeljuje indekse fajlova, pa se izbor prenosi jedan na jedan.
    """

    raw_files = info.get(b"files")
    name = _text(info.get(b"name"))

    if not isinstance(raw_files, list):
        length = info.get(b"length")
        size = int(length) if isinstance(length, int) else 0
        return (DiscoveredFile(file_index=0, path=name, size_bytes=size),)

    collected: list[DiscoveredFile] = []
    for index, entry in enumerate(raw_files):
        if not isinstance(entry, dict):
            continue
        length = entry.get(b"length")
        collected.append(
            DiscoveredFile(
                file_index=index,
                path=_join_path(entry.get(b"path")),
                size_bytes=int(length) if isinstance(length, int) else 0,
            )
        )
    return tuple(collected)


def read_torrent_file(path: str) -> DiscoveredTorrent | None:
    """Sadržaj jednog .torrent fajla, ili `None` kada nije čitljiv."""

    try:
        with open(path, "rb") as handle:
            raw = handle.read()
    except OSError:
        return None

    info_hash = info_hash_of(raw)
    if info_hash is None:
        return None

    try:
        decoded, _index = bdecode(raw, 0)
    except (ValueError, IndexError):
        return None

    if not isinstance(decoded, dict):
        return None

    info = decoded.get(b"info")
    if not isinstance(info, dict):
        return None

    files = _files_of(info)
    fallback_name = os.path.splitext(os.path.basename(path))[0]

    return DiscoveredTorrent(
        source_path=os.path.abspath(path),
        info_hash=info_hash,
        name=_text(info.get(b"name"), fallback_name) or fallback_name,
        total_bytes=sum(item.size_bytes for item in files),
        files=files,
    )


def scan_folder(folder: str) -> list[DiscoveredTorrent]:
    """Svi čitljivi .torrent fajlovi iz jednog foldera (bez podfoldera)."""

    try:
        names = sorted(os.listdir(folder))
    except OSError:
        return []

    found: list[DiscoveredTorrent] = []
    for name in names:
        if not name.lower().endswith(TORRENT_EXTENSION):
            continue
        entry = read_torrent_file(os.path.join(folder, name))
        if entry is not None:
            found.append(entry)
    return found


def scan_folders(folders: tuple[str, ...] | list[str]) -> list[DiscoveredTorrent]:
    """Pronađeni torrenti iz svih nadziranih foldera, bez ponavljanja.

    Isti fajl na dve putanje (ili isti torrent u dva foldera) javlja se
    jednom — kartice se razlikuju po info hash-u, ne po putanji.
    """

    by_hash: dict[str, DiscoveredTorrent] = {}
    seen_folders: set[str] = set()

    for folder in folders:
        cleaned = folder.strip()
        if not cleaned:
            continue

        resolved = os.path.abspath(cleaned)
        if resolved in seen_folders:
            continue
        seen_folders.add(resolved)

        for entry in scan_folder(resolved):
            by_hash.setdefault(entry.info_hash, entry)

    return sorted(by_hash.values(), key=lambda item: item.name.lower())
