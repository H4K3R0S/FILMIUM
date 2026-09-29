# ========== ATOM FAJLOVI: listanje i uređivanje iz podešavanja ==========
# Kurator persona atomi (persona.md, tools/*.md, commands/*.md) su uređivi iz
# ekrana podešavanja ćelije. Ovaj modul ih nabraja, čita i piše — uz strogu
# zaštitu da putanja iz zahteva ne izađe iz korena atoma.
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

# Relativne putanje smeju samo ove: bez `..`, samo `.md`, unutar korena.
_DOZVOLJENI_PODFOLDERI = ("", "tools", "commands", "consult")


@dataclass(frozen=True)
class AtomFile:
    """Jedan atom fajl: relativna putanja i sadržaj."""

    path: str        # npr. "persona.md", "tools/pretraga.md"
    content: str


def _bezbedna_putanja(root: Path, relpath: str) -> Path:
    """Apsolutna putanja unutar `root`, ili ValueError za izlazak/loš oblik."""

    if not relpath.endswith(".md") or "\\" in relpath:
        raise ValueError(f"Nedozvoljena putanja atoma: {relpath}")
    kandidat = (root / relpath).resolve()
    koren = root.resolve()
    if koren != kandidat and koren not in kandidat.parents:
        raise ValueError(f"Putanja izlazi iz korena atoma: {relpath}")
    return kandidat


def list_atoms(root: Path) -> list[AtomFile]:
    """Svi `.md` atomi ispod korena persone (koren + dozvoljeni podfolderi)."""

    nadjeni: list[AtomFile] = []
    for podfolder in _DOZVOLJENI_PODFOLDERI:
        folder = root / podfolder if podfolder else root
        if not folder.is_dir():
            continue
        for putanja in sorted(folder.glob("*.md")):
            rel = putanja.relative_to(root).as_posix()
            nadjeni.append(AtomFile(path=rel, content=putanja.read_text(encoding="utf-8")))
    return nadjeni


def read_atom(root: Path, relpath: str) -> str:
    """Sadržaj jednog atoma; ValueError za lošu putanju, FileNotFoundError ako nema."""

    putanja = _bezbedna_putanja(root, relpath)
    if not putanja.is_file():
        raise FileNotFoundError(f"Atom ne postoji: {relpath}")
    return putanja.read_text(encoding="utf-8")


def write_atom(root: Path, relpath: str, content: str) -> AtomFile:
    """Upisuje sadržaj atoma. Prazan sadržaj se odbija (ValueError)."""

    if not content.strip():
        raise ValueError("Sadržaj atoma ne sme biti prazan.")
    putanja = _bezbedna_putanja(root, relpath)
    putanja.parent.mkdir(parents=True, exist_ok=True)
    putanja.write_text(content, encoding="utf-8")
    return AtomFile(path=relpath, content=content)
