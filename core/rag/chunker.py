from __future__ import annotations

import ast
import re
from dataclasses import dataclass

_HEADING = re.compile(r"^#{1,6} ", re.MULTILINE)


@dataclass(frozen=True)
class Chunk:
    ordinal: int
    content: str
    token_count: int


def estimate_tokens(text: str) -> int:
    return max(1, round(len(text) / 4))


def _spakuj(delovi: list[str]) -> list[Chunk]:
    ociscen = [d.strip() for d in delovi if d.strip()]
    return [Chunk(i, d, estimate_tokens(d)) for i, d in enumerate(ociscen)]


def chunk_markdown(text: str, *, target_tokens: int = 300) -> list[Chunk]:
    granice = [m.start() for m in _HEADING.finditer(text)]
    if not granice:
        sekcije = [text]
    else:
        if granice[0] != 0:
            granice = [0, *granice]
        sekcije = [text[a:b] for a, b in zip(granice, [*granice[1:], len(text)])]

    delovi: list[str] = []
    for sekcija in sekcije:
        if estimate_tokens(sekcija) <= target_tokens:
            delovi.append(sekcija)
        else:
            delovi.extend(p for p in sekcija.split("\n\n"))
    return _spakuj(delovi)


def chunk_python(text: str, *, target_tokens: int = 300) -> list[Chunk]:
    try:
        stablo = ast.parse(text)
    except SyntaxError:
        return chunk_lines(text)

    linije = text.splitlines(keepends=True)
    granice: list[tuple[int, int]] = []
    for cvor in stablo.body:
        if isinstance(cvor, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            start = cvor.lineno - 1
            kraj = cvor.end_lineno or cvor.lineno
            granice.append((start, kraj))

    delovi: list[str] = []
    pokriveno = [False] * len(linije)
    for start, kraj in granice:
        delovi.append("".join(linije[start:kraj]))
        for i in range(start, min(kraj, len(linije))):
            pokriveno[i] = True
    uvod = "".join(l for i, l in enumerate(linije) if not pokriveno[i])
    if uvod.strip():
        delovi.insert(0, uvod)
    if not delovi:
        return chunk_lines(text)
    return _spakuj(delovi)


def chunk_lines(text: str, *, window: int = 60) -> list[Chunk]:
    linije = text.splitlines()
    delovi = [
        "\n".join(linije[i:i + window]) for i in range(0, len(linije), window)
    ]
    return _spakuj(delovi or [text])


def chunk_for(path: str, text: str) -> list[Chunk]:
    if path.endswith(".md"):
        return chunk_markdown(text)
    if path.endswith(".py"):
        return chunk_python(text)
    return chunk_lines(text)
