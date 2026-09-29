"""Cell build — statička analiza uvoza ćelije (foreign/forbidden/unresolved) —
izdvojeno iz build.py radi veličine."""

from __future__ import annotations

import ast
from pathlib import Path

from core.cell.build_common import _is_forbidden


def _parse_python(path: Path, text: str) -> ast.Module | None:
    """
    Parsira `text` kao Python; pri neuspehu vraća `None`.

    Fajl koji ne može da se parsira nije "preskočen" — sam taj neuspeh je
    signal da nešto nije u redu (npr. loše kopiranje ili prepisivanje). Ovaj
    poziv sam ne dodaje nalaz; pozivaoci (`find_foreign_domain_imports`,
    `find_forbidden_module_imports`) to rade kad dobiju `None`.
    """
    try:
        return ast.parse(text, filename=str(path))
    except SyntaxError:
        return None


def find_foreign_domain_imports(
    cell_root: Path,
    domain_id: str,
) -> tuple[str, ...]:
    """
    Traži uvoze ka drugim domenima u sklopljenoj ćeliji.

    Parsira svaki `.py` fajl preko `ast` (ne regex-om) — ispravno hvata i
    uvoze razbijene u više redova i uvoze sa `as` aliasom, jer `ast` ionako
    razdvaja modul od imena, bez obzira na formatiranje izvornog teksta.

    Args:
        cell_root: Koren ćelije.
        domain_id: Domen kom ćelija pripada.

    Returns:
        Redovi oblika `putanja:linija: tekst` za svaki nađen strani uvoz, ili
        za svaki fajl koji ne može da se parsira.
    """
    findings: list[str] = []

    for path in sorted(cell_root.rglob("*.py")):
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue

        relpath = path.relative_to(cell_root)
        tree = _parse_python(path, text)
        if tree is None:
            findings.append(f"{relpath}:1: NEČITLJIV FAJL — ne parsira se kao Python")
            continue

        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                if node.module is None:
                    continue  # relativan uvoz (from . import x) ne cilja core.domains

                parts = node.module.split(".")
                if len(parts) >= 3 and parts[:2] == ["core", "domains"]:
                    domain = parts[2]
                    if domain != domain_id:
                        findings.append(
                            f"{relpath}:{node.lineno}: from {node.module} import ..."
                        )
                elif node.module == "core.domains":
                    for alias in node.names:
                        if alias.name != domain_id and alias.name != "*":
                            findings.append(
                                f"{relpath}:{node.lineno}: "
                                f"from core.domains import {alias.name}"
                            )
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    parts = alias.name.split(".")
                    if len(parts) >= 3 and parts[:2] == ["core", "domains"]:
                        domain = parts[2]
                        if domain != domain_id:
                            findings.append(
                                f"{relpath}:{node.lineno}: import {alias.name}"
                            )

    return tuple(findings)


def find_forbidden_module_imports(cell_root: Path) -> tuple[str, ...]:
    """
    Traži uvoze modula koje ćelija ne nosi ni pod jednim domenom.

    Za razliku od `find_foreign_domain_imports` (koji hvata bilo koji
    `core.domains.<domen>` uvoz osim sopstvenog), ovo je poimenična provera
    protiv `_FORBIDDEN_MODULES`. Ćelija ne nosi nijedan od njih; ako se ijedan
    pojavi, kopiran je fajl koji ćeliju vraća na CORE-ovu punu, višedomensku
    infrastrukturu — ili je neki `.replace()` u nekoj `rewrite_*` funkciji
    nemo omanuo (npr. `_strip_cross_domain_dependencies`, ako se anker-tekst u
    repou preformatira).

    Parsira preko `ast`, pa ispravno hvata:
    - višerednu zagradnu formu (`from apps.api import (\\n    core_ai_runtime,\\n)`),
    - `as` alias (`from apps.api import core_ai_runtime as car`) — `ast`
      razdvaja `alias.name` (stvarno uvezeno ime) od `alias.asname`, pa se
      provera radi nad pravim imenom bez obzira na alias.

    Args:
        cell_root: Koren ćelije.

    Returns:
        Redovi oblika `putanja:linija: tekst` za svaki nađen zabranjen uvoz,
        ili za svaki fajl koji ne može da se parsira.
    """
    findings: list[str] = []

    for path in sorted(cell_root.rglob("*.py")):
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue

        relpath = path.relative_to(cell_root)
        tree = _parse_python(path, text)
        if tree is None:
            findings.append(f"{relpath}:1: NEČITLJIV FAJL — ne parsira se kao Python")
            continue

        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                if node.module is None:
                    continue

                candidates = [node.module]
                candidates.extend(
                    f"{node.module}.{alias.name}"
                    for alias in node.names
                    if alias.name != "*"
                )
                if any(_is_forbidden(candidate) for candidate in candidates):
                    names = ", ".join(alias.name for alias in node.names)
                    findings.append(
                        f"{relpath}:{node.lineno}: from {node.module} import {names}"
                    )
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    if _is_forbidden(alias.name):
                        findings.append(f"{relpath}:{node.lineno}: import {alias.name}")

    return tuple(findings)


def _repo_top_level_packages(repo_root: Path) -> frozenset[str]:
    """
    Gornji paketi/moduli repoa: folderi sa `__init__.py` i `.py` fajlovi
    direktno u `repo_root`, bez `tests` (testovi nikad nisu deo ćelije).
    """
    names: set[str] = set()
    for entry in repo_root.iterdir():
        if entry.name == "tests":
            continue
        if entry.is_dir() and (entry / "__init__.py").is_file():
            names.add(entry.name)
        elif entry.is_file() and entry.suffix == ".py":
            names.add(entry.stem)
    return frozenset(names)


def _cell_module_exists(cell_root: Path, dotted: str) -> bool:
    """Da li modul `dotted` (npr. `"core.domains.filmium"`) postoji u ćeliji."""

    relative = Path(*dotted.split("."))
    return (
        (cell_root / relative).with_suffix(".py").is_file()
        or (cell_root / relative / "__init__.py").is_file()
    )


def _is_type_checking_test(test: ast.expr) -> bool:
    """
    Da li je `test` (uslov `if`-a) prepoznatljiv `TYPE_CHECKING` gard —
    `TYPE_CHECKING` (uvezeno ime) ili `<bilo šta>.TYPE_CHECKING` (npr.
    `typing.TYPE_CHECKING`, ili preko aliasa).
    """
    if isinstance(test, ast.Name):
        return test.id == "TYPE_CHECKING"
    if isinstance(test, ast.Attribute):
        return test.attr == "TYPE_CHECKING"
    return False


class _ImportCollector(ast.NodeVisitor):
    """
    Skuplja `Import`/`ImportFrom` čvorove iz CELOG stabla, ali PRESKAČE telo
    `if TYPE_CHECKING:` (ili `if typing.TYPE_CHECKING:`) grane — uvozi tamo
    postoje SAMO za type checker (mypy/pyright), nikad se stvarno ne izvršavaju
    u ćeliji, pa njihov nedostatak ne sme da blokira build/update lažnom
    pozitivom (review taska 1, Important 2). `else` grana ISTOG `if`-a (i sve
    ostalo van tela) se i dalje obilazi normalno — samo `node.body` konkretnog
    TYPE_CHECKING `if`-a se preskače.
    """

    def __init__(self) -> None:
        self.imports: list[ast.Import | ast.ImportFrom] = []

    def visit_If(self, node: ast.If) -> None:
        if _is_type_checking_test(node.test):
            for child in node.orelse:
                self.visit(child)
        else:
            self.generic_visit(node)

    def visit_Import(self, node: ast.Import) -> None:
        self.imports.append(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        self.imports.append(node)


def find_unresolved_local_imports(cell_root: Path, repo_root: Path) -> tuple[str, ...]:
    """
    Traži apsolutne uvoze u ćeliji čiji GORNJI paket postoji u korenu repoa
    (kao folder sa `__init__.py` ili kao `.py` fajl), a MODUL koji uvoze ne
    postoji u samoj ćeliji.

    Ovo hvata ono što `find_foreign_domain_imports` (samo `core.domains.*`) i
    `find_forbidden_module_imports` (poimenična crna lista) ne vide: uvoz ka
    paketu koji NIJE zabranjen, ali ga `build_cell` prosto ne kopira (npr.
    top-level `integrations` pre `CELL_EXTRA_PACKAGES`) — takav uvoz bi pao na
    `ModuleNotFoundError` tek pri pokretanju ćelije, van svakog testa koji
    samo parsira module na vrhu fajla.

    Za `from a.b import c`: `c` može biti PODMODUL (`a/b/c.py`) ili obično
    ime (atribut) modula `a.b` — dovoljno je da postoji BILO KOJE od to dvoje
    (`a/b/c.py` ili `a/b/c/__init__.py`, ILI `a/b.py` ili `a/b/__init__.py`).
    Za `from a.b import *` se `c` ne zna unapred — proverava se da SAM `a.b`
    postoji u ćeliji.

    Uvozi unutar `if TYPE_CHECKING:` (ili `if typing.TYPE_CHECKING:`) tela se
    NE proveravaju — postoje samo za type checker, nikad se ne izvršavaju
    (vidi `_ImportCollector`); `else` grana istog `if`-a se i dalje proverava.

    Args:
        cell_root: Koren sklopljene ćelije.
        repo_root: Koren CORE repoa — referenca za "gornji paket postoji".

    Returns:
        Redovi oblika `putanja:linija: uvoz`, sortirano po putanji pa liniji;
        fajl koji ne parsira se prijavljuje kao nalaz, isto kao
        `find_forbidden_module_imports`.
    """
    top_level_packages = _repo_top_level_packages(repo_root)
    findings: list[tuple[str, int, str]] = []

    for path in sorted(cell_root.rglob("*.py")):
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue

        relpath = str(path.relative_to(cell_root))
        tree = _parse_python(path, text)
        if tree is None:
            findings.append(
                (relpath, 1, "NEČITLJIV FAJL — ne parsira se kao Python")
            )
            continue

        collector = _ImportCollector()
        collector.visit(tree)

        for node in collector.imports:
            if isinstance(node, ast.Import):
                for alias in node.names:
                    top = alias.name.split(".")[0]
                    if top not in top_level_packages:
                        continue
                    if not _cell_module_exists(cell_root, alias.name):
                        findings.append(
                            (relpath, node.lineno, f"import {alias.name}")
                        )
            else:  # ast.ImportFrom
                if node.level or node.module is None:
                    continue  # relativan uvoz — ne cilja koren repoa
                top = node.module.split(".")[0]
                if top not in top_level_packages:
                    continue
                for alias in node.names:
                    if alias.name == "*":
                        # `c` se ne zna unapred za wildcard — proverava se
                        # SAM `a.b` (review taska 1, Important 1: pre ove
                        # izmene se ovde samo preskakalo, BEZ ijedne provere).
                        if not _cell_module_exists(cell_root, node.module):
                            findings.append(
                                (relpath, node.lineno, f"from {node.module} import *")
                            )
                        continue
                    submodule = f"{node.module}.{alias.name}"
                    if _cell_module_exists(cell_root, submodule) or _cell_module_exists(
                        cell_root, node.module
                    ):
                        continue
                    findings.append(
                        (
                            relpath,
                            node.lineno,
                            f"from {node.module} import {alias.name}",
                        )
                    )

    findings.sort(key=lambda item: (item[0], item[1]))
    return tuple(f"{relpath}:{lineno}: {text}" for relpath, lineno, text in findings)
