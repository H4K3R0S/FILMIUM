"""Detekcija „kolekcije filmova" — folder sa više filmova kao direktnim
fajlovima (npr. „Pirates of the Caribbean", „Twilight Saga").

Fajlovi su oblika „N - Naslov (Godina).ext" ili „N (Godina).ext". Svaki
takav video je zaseban film; sidecar (poster/backdrop/prevod) pripada mu po
istom baznom nazivu (prevod može imati krajnji jezički kod, npr. „….sr.srt").
"""

import re
from dataclasses import dataclass
from pathlib import Path

from core.domains.filmium.library_scanner import VIDEO_EXTENSIONS

# „1 - Curse of the Black Pearl (2003)", „1 (2008)", „4 - Breaking Dawn 1 (2011)"
# Naslov se prihvata SAMO uz separator posle broja („N - Naslov (Godina)"),
# ili bez naslova („N (Godina)"). Time se izbegava lažno okidanje na filmovima
# koji počinju brojem bez separatora (npr. „2 Fast 2 Furious (2003)").
_ENTRY = re.compile(
    r"^\s*(?P<order>\d{1,3})\s*"
    r"(?:[-–.)]\s*(?P<title>.+?)\s*)?"
    r"[\(\[](?P<year>\d{4})[\)\]]"
)


@dataclass(frozen=True)
class CollectionEntry:
    order: int
    title: str | None
    year: int
    video_path: Path


def parse_collection_entry(
    name: str,
) -> tuple[int, str | None, int] | None:
    """
    Iz naziva (bez ekstenzije) vadi (redni_broj, naslov, godina).

    Naslov je ``None`` kad ga nema („1 (2008)"). Vraća ``None`` ako naziv
    ne odgovara šablonu kolekcije (broj + godina).
    """

    match = _ENTRY.match(name)
    if match is None:
        return None

    raw_title = match.group("title")
    title = raw_title.strip(" -–.") if raw_title else None
    return (
        int(match.group("order")),
        title or None,
        int(match.group("year")),
    )


def collection_video_entries(directory: Path) -> list[CollectionEntry]:
    """Direktni video fajlovi koji odgovaraju šablonu kolekcije (sortirani)."""

    if not directory.is_dir():
        return []

    entries: list[CollectionEntry] = []
    for path in directory.iterdir():
        if not path.is_file():
            continue
        if path.suffix.casefold() not in VIDEO_EXTENSIONS:
            continue
        parsed = parse_collection_entry(path.stem)
        if parsed is None:
            continue
        order, title, year = parsed
        entries.append(
            CollectionEntry(
                order=order,
                title=title,
                year=year,
                video_path=path,
            )
        )

    return sorted(entries, key=lambda entry: (entry.order, entry.year))


def _direct_video_count(directory: Path) -> int:
    if not directory.is_dir():
        return 0
    return sum(
        1
        for path in directory.iterdir()
        if path.is_file() and path.suffix.casefold() in VIDEO_EXTENSIONS
    )


def is_movie_collection(directory: Path) -> bool:
    """
    Kolekcija = SVI direktni video fajlovi su numerisani delovi
    („N - Naslov (Godina)" / „N (Godina)"), i ima ih bar jedan.

    I jedan preostali deo franšize (npr. samo „4 - Breaking Dawn 1 (2011)")
    se tretira kao kolekcija. Folder sa običnim filmom + numerisanim sample-om
    NIJE kolekcija (glavni film se ne sme izgubiti).
    """

    entries = collection_video_entries(directory)
    return bool(entries) and len(entries) == _direct_video_count(directory)


def sidecar_matches_video(sidecar: Path, video_stem: str) -> bool:
    """
    Da li sidecar (poster/backdrop/prevod) pripada videu istog baznog naziva.

    Podnosi krajnji jezički kod prevoda: „<baza>.sr.srt" / „<baza>.en.forced.srt"
    (stem = „<baza>.sr" / „<baza>.en.forced") — sve dok počinje baznim nazivom
    videa, a ostatak je kratak kod (slova/cifre/tačke, ≤ 12 znakova).
    """

    stem = sidecar.stem
    if stem == video_stem:
        return True
    if not stem.startswith(f"{video_stem}."):
        return False

    remainder = stem[len(video_stem) + 1:]
    return (
        0 < len(remainder) <= 12
        and all(part.isalnum() for part in remainder.split(".") if part)
    )


_ORDINAL_PREFIX = re.compile(r"^\s*0*(\d+)\b")


def collection_sidecar_matches(
    sidecar: Path,
    video_stem: str,
    folder_name: str,
    order: int,
) -> bool:
    """
    Da li sidecar pripada filmu iz kolekcije (redni broj ``order``).

    Dva pravila:
      1. isti bazni naziv kao video (uklj. krajnji jezički kod prevoda),
      2. redni broj filma: „<Ime foldera> N - backdrop.jpg", „N - poster.jpg"
         — posle (opciono) skinutog imena foldera, naziv počinje brojem N.
    """

    if sidecar_matches_video(sidecar, video_stem):
        return True

    stem = sidecar.stem
    prefix = folder_name.casefold()
    if stem.casefold().startswith(prefix):
        rest = stem[len(folder_name):].lstrip(" -–_.")
    else:
        rest = stem

    match = _ORDINAL_PREFIX.match(rest)
    return match is not None and int(match.group(1)) == order


def collection_title(entry_title: str | None, folder_name: str) -> str:
    """
    Naslov filma iz kolekcije = ime glavnog foldera + naslov stavke
    („Pirates of the Caribbean Curse of the Black Pearl"). Ako stavka nema
    naslov („1 (2008)") → samo ime foldera („Twilight Saga").
    """

    if entry_title:
        return f"{folder_name} {entry_title}".strip()
    return folder_name
