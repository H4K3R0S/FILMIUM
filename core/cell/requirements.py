"""Gradi suženi `requirements.txt` sklopljene ćelije.

Ćelija ne nosi CORE-ov puni `requirements.txt` (koji uz FILMIUM zavisnosti
nosi i `anthropic`, `openai`, `mcp`, `keyring` — CORE-ov AI/tajne sloj koji
ćelija ne koristi). Umesto toga, ovaj modul čita STVARNE uvoze iz kopiranog
Python koda ćelije (`core/`, `apps/`, `integrations/`, `cell_app.py`) i pravi
spisak tačno onoga što ćeliji treba, pinovan na verzije instalirane u CORE
venv-u (`importlib.metadata`) — iste verzije koje CORE stvarno koristi i
testira.
"""

from __future__ import annotations

import ast
import importlib.metadata
import sys
from pathlib import Path

# Mapa uvezenog imena (ono što `import X` ili `from X import ...` stvarno
# stavlja u kod) na ime PyPI distribucije (ono što ide u `requirements.txt`).
# Za `psycopg[binary]` se verzija čita od `psycopg` (`importlib.metadata`
# poznaje samo bazno ime, ne "extra" deo u uglastim zagradama).
IMPORT_TO_DISTRIBUTION: dict[str, str] = {
    "fastapi": "fastapi",
    "starlette": "starlette",
    "pydantic": "pydantic",
    "PIL": "Pillow",
    "watchdog": "watchdog",
    "psutil": "psutil",
    "qbittorrentapi": "qbittorrent-api",
    "deep_translator": "deep-translator",
    "psycopg": "psycopg[binary]",
    "pgvector": "pgvector",
    "yaml": "PyYAML",
}

# Uvozi u `try/except` (opcione zavisnosti) — ne ulaze u `requirements.txt`,
# jer kod već radi bez njih (npr. `win10toast`, samo na Windows-u, samo za
# desktop notifikacije).
OPTIONAL_IMPORTS: frozenset[str] = frozenset({"win10toast"})

# Distribucije koje su ćeliji potrebne u runtime-u, a nijedan `.py` fajl ih
# direktno ne uvozi — `uvicorn` pokreće `cell_app:app` (vidi `start.bat`),
# `python-multipart` FastAPI tiho traži za upload formi.
RUNTIME_DISTRIBUTIONS: tuple[str, ...] = ("uvicorn", "python-multipart")


class UnknownThirdPartyImport(ValueError):
    """
    Uvoz koji nije ni stdlib, ni lokalan, ni u `IMPORT_TO_DISTRIBUTION`.

    Ćelija NIKAD ne sme tiho da izostavi nepoznatu zavisnost iz
    `requirements.txt` — to bi značilo da neki modul u ćeliji pukne tek pri
    pokretanju (`ModuleNotFoundError`), pošto `.venv` te ćelije ne bi imao
    šta da instalira. Ovaj izuzetak nosi ime uvoza — pravac popravke je da se
    doda u `IMPORT_TO_DISTRIBUTION`, sa tačnim imenom PyPI distribucije.
    """


def _local_roots(cell_root: Path) -> frozenset[str]:
    """Python koreni koje sama ćelija nosi — uvoz ka njima nije treći uvoz."""

    _ = cell_root  # rezervisano za buduću proveru; koren je uvek isti skup
    return frozenset({"core", "apps", "integrations", "cell_app"})


def third_party_imports(cell_root: Path) -> frozenset[str]:
    """
    Skuplja gornja imena third-party uvoza u sklopljenoj ćeliji.

    Prolazi kroz `core/**/*.py`, `apps/**/*.py`, `integrations/**/*.py` i
    `cell_app.py` u korenu ćelije, parsira svaki fajl preko `ast` (`ast.walk`,
    pa hvata i uvoze ugnežđene u funkcije, `try/except` blokove i slično — ne
    samo uvoze na vrhu modula). Za svaki APSOLUTNI uvoz (relativni, `from .
    import x`, se ne tiče trećih paketa) uzima gornje ime (deo pre prve tačke)
    i izbacuje standardnu biblioteku (`sys.stdlib_module_names`), `__future__`
    i sopstvene Python korene ćelije.

    Args:
        cell_root: Koren sklopljene ćelije.

    Returns:
        Skup gornjih imena third-party uvoza (npr. `{"fastapi", "PIL"}`) —
        OPCIONI uvozi (`OPTIONAL_IMPORTS`) su i dalje u ovom skupu; njih
        filtrira tek `build_requirements`.
    """
    local_roots = _local_roots(cell_root)
    stdlib = set(sys.stdlib_module_names)
    found: set[str] = set()

    paths: list[Path] = []
    for pattern in ("core/**/*.py", "apps/**/*.py", "integrations/**/*.py"):
        paths.extend(cell_root.glob(pattern))
    cell_app_path = cell_root / "cell_app.py"
    if cell_app_path.is_file():
        paths.append(cell_app_path)

    for path in paths:
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue

        try:
            tree = ast.parse(text, filename=str(path))
        except SyntaxError:
            continue

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    top = alias.name.split(".")[0]
                    if top in stdlib or top == "__future__" or top in local_roots:
                        continue
                    found.add(top)
            elif isinstance(node, ast.ImportFrom):
                if node.level or node.module is None:
                    continue  # relativan uvoz — ne cilja treći paket
                top = node.module.split(".")[0]
                if top in stdlib or top == "__future__" or top in local_roots:
                    continue
                found.add(top)

    return frozenset(found)


def build_requirements(cell_root: Path) -> str:
    """
    Gradi sadržaj `requirements.txt` za sklopljenu ćeliju.

    Za svaki third-party uvoz iz `third_party_imports`: opcioni
    (`OPTIONAL_IMPORTS`) se preskače; nepoznat (nema ga u
    `IMPORT_TO_DISTRIBUTION`) diže `UnknownThirdPartyImport` — nikad se tiho
    ne izostavlja. Preostalim distribucijama se dodaju `RUNTIME_DISTRIBUTIONS`
    (potrebne u runtime-u, a se ne uvoze direktno ni iz jednog `.py` fajla).
    Verzija svake distribucije se čita iz `importlib.metadata` CORE venv-a —
    za ime sa "extra" delom (`psycopg[binary]`) se verzija čita od baznog
    imena (`psycopg`), jer `importlib.metadata` "extra" deo ne poznaje.

    Args:
        cell_root: Koren sklopljene ćelije.

    Returns:
        Tekst `requirements.txt`: jedna linija `ime==verzija` po distribuciji,
        sortirano bez obzira na veličinu slova, sa završnim `\\n`.

    Raises:
        UnknownThirdPartyImport: Ako ćelija uvozi treći paket koji nije u
            `IMPORT_TO_DISTRIBUTION`.
    """
    distributions: set[str] = set()

    for name in third_party_imports(cell_root):
        if name in OPTIONAL_IMPORTS:
            continue
        distribution = IMPORT_TO_DISTRIBUTION.get(name)
        if distribution is None:
            raise UnknownThirdPartyImport(
                f"Nepoznat third-party uvoz '{name}' u ćeliji — dodaj ga u "
                "IMPORT_TO_DISTRIBUTION (core/cell/requirements.py) sa "
                "tačnim imenom PyPI distribucije, umesto da se tiho izostavi "
                "iz requirements.txt."
            )
        distributions.add(distribution)

    distributions.update(RUNTIME_DISTRIBUTIONS)

    lines = [
        f"{distribution}=={importlib.metadata.version(distribution.split('[')[0])}"
        for distribution in distributions
    ]
    lines.sort(key=str.lower)

    return "\n".join(lines) + "\n"
