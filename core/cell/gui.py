"""Zatvorenje GUI uvoza FILMIUM ćelije.

Polazi od ćelijskog ulaza i prati relativne uvoze kroz TypeScript, TSX i CSS,
primenjujući istu mapu zamena koju koristi Vite (`apps/gui/cell-substitutions.json`).
Rezultat je tačan skup izvornih fajlova koje ćelija nosi i skup npm paketa koje
taj izvor traži. Nerazrešiv relativni uvoz je greška, ne tiho preskakanje —
upravo tako se ranije izgubio `CoreAssistantChat.tsx`.
"""

from __future__ import annotations

import json
import re
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

CELL_GUI_ENTRY = "src/cell/cellMain.tsx"
SUBSTITUTIONS_FILENAME = "cell-substitutions.json"

# Moduli koje ćelija ne sme da nosi (CORE asistent, window sistem, CODIUM i
# CORE podešavanja modela/ključeva, spec §15.2) žive u `forbidden_prefixes`
# ključu `cell-substitutions.json` — isti spisak proverava i Vite `buildEnd`,
# pa Python i Vite ne mogu da se razmimoiđu. Glas namerno nije zabranjen:
# `voiceApi.ts` je potreban jer ga uvozi deljeni `CoreChat`, a van Tauri-ja je
# inertan (svaka funkcija je iza `isTauriRuntime()`, koji ne uvozi window
# manager) — window sistem ostaje zabranjen.
SUBSTITUTIONS_KEY = "substitutions"
FORBIDDEN_PREFIXES_KEY = "forbidden_prefixes"

_SCRIPT_IMPORT = re.compile(
    r"""(?:^|[;\s])(?:import|export)\s+(?:type\s+)?(?:[^'";]*?\s+from\s+)?['"]([^'"]+)['"]"""
    r"""|import\(\s*['"]([^'"]+)['"]\s*\)""",
    re.MULTILINE,
)
_CSS_IMPORT = re.compile(r"""@import\s+(?:url\()?['"]([^'"]+)['"]""")
_CANDIDATE_SUFFIXES = ("", ".ts", ".tsx", ".js", ".jsx", ".css", "/index.ts", "/index.tsx")

# Prepoznaje ili string (dupli/jednostruki navodnici, backtick — sa
# escape-ovanjem), ili komentar (`//` do kraja reda, `/* */` preko više
# redova). `re.DOTALL` je potreban samo da `/\*.*?\*/` pređe preko novog reda;
# `//[^\n]*` i string-klase eksplicitno isključuju `\n` gde treba.
#
# `//` se tumači kao početak linijskog komentara samo na početku reda ili
# posle razmaka (`re.MULTILINE` da `^` hvata svaki red) — regex literal poput
# `/a\/\//` sadrži `//` koje nije komentar, a formatiran kod u ovom repou
# uvek piše `kod // komentar` ili komentar u sopstvenom redu, pa razmak ispred
# pouzdano razlikuje jedno od drugog.
_STRING_OR_COMMENT = re.compile(
    r'"(?:\\.|[^"\\])*"'
    r"|'(?:\\.|[^'\\])*'"
    r"|`(?:\\.|[^`\\])*`"
    r"|(?:^|(?<=\s))//[^\n]*"
    r"|/\*.*?\*/",
    re.DOTALL | re.MULTILINE,
)


def _strip_comments(text: str) -> str:
    """
    Uklanja `//` i `/* */` komentare iz izvora, čuvajući string literale.

    Bez ovoga bi uvoz-nalik tekst u komentaru (npr. dokumentacija koja
    pominje putanju) izazvao lažan `FileNotFoundError` ili tiho uvukao
    nepovezan fajl u zatvorenje — ovaj modul postoji baš da to spreči.
    String se vraća nepromenjen (da se `"http://..."` ne protumači kao
    početak komentara), a komentar se zamenjuje istim brojem novih redova
    koje je sadržao, da brojevi redova u ostatku teksta ostanu tačni.
    """

    def zameni(match: re.Match[str]) -> str:
        token = match.group(0)
        if token.startswith(("//", "/*")):
            return "\n" * token.count("\n")
        return token

    return _STRING_OR_COMMENT.sub(zameni, text)


@dataclass(frozen=True)
class GuiClosure:
    """Izvorni fajlovi (relativni na `apps/gui`) i npm paketi ćelijskog GUI-ja."""

    files: tuple[str, ...]
    npm_packages: tuple[str, ...]


def _load_cell_gui_policy(gui_root: Path) -> dict:
    """
    Čita `cell-substitutions.json`.

    Raises:
        ValueError: Ako fajl nije objekat sa `substitutions` i `forbidden_prefixes`.
    """
    path = gui_root / SUBSTITUTIONS_FILENAME
    data = json.loads(path.read_text(encoding="utf-8"))
    if (
        not isinstance(data, dict)
        or not isinstance(data.get(SUBSTITUTIONS_KEY), dict)
        or not isinstance(data.get(FORBIDDEN_PREFIXES_KEY), list)
    ):
        raise ValueError(  # noqa: TRY004
            f"{path} mora biti objekat sa ključevima "
            f"'{SUBSTITUTIONS_KEY}' (objekat) i '{FORBIDDEN_PREFIXES_KEY}' (lista)"
        )
    return data


def load_substitutions(gui_root: Path) -> dict[str, str]:
    """Učitava mapu zamena CORE-only modula."""

    return dict(_load_cell_gui_policy(gui_root)[SUBSTITUTIONS_KEY])


def load_forbidden_prefixes(gui_root: Path) -> tuple[str, ...]:
    """Učitava prefikse modula (relativne na `gui_root`) koje ćelija ne sme da nosi."""

    return tuple(str(prefix) for prefix in _load_cell_gui_policy(gui_root)[FORBIDDEN_PREFIXES_KEY])


def _normalize_key(path: Path) -> str:
    """
    Normalizuje putanju u ključ pogodan za poređenje bez obzira na platformu.

    Isti problem koji rešava Vite plugin za zamene: na Windows-u slovo diska i
    velika/mala slova ne smeju da razdvoje isti fajl u dva različita ključa.
    Zato se `resolve()`-ovana putanja svodi na string sa `/` separatorima i
    malim slovima, umesto da se `Path` objekat koristi direktno kao ključ.
    """

    return str(path.resolve()).replace("\\", "/").lower()


def _relative(gui_root: Path, path: Path) -> str:
    return path.resolve().relative_to(gui_root.resolve()).as_posix()


def _resolve(
    importer: Path,
    specifier: str,
    substitutions: dict[str, Path] | None = None,
) -> Path | None:
    """
    Razrešava relativan uvoz, primenjujući mapu zamena PRE provere postojanja.

    U ćelijinom `gui/` originali zamenjenih modula namerno ne postoje, a
    kopirani fajlovi ih i dalje uvoze. Kad bi se zamena primenila tek posle
    `is_file()`, isti izvor bi se razrešio u repou, a u ćeliji pao.

    Args:
        importer: Fajl koji uvozi.
        specifier: Relativan uvoz, npr. `../chat/CoreAssistantChat`.
        substitutions: Normalizovan ključ originala -> putanja zamene.

    Returns:
        Razrešena putanja (ili njena zamena), ili `None` ako ništa ne odgovara.
    """
    base = importer.parent / specifier
    for suffix in _CANDIDATE_SUFFIXES:
        candidate = Path(f"{base}{suffix}")
        if substitutions:
            replacement = substitutions.get(_normalize_key(candidate))
            if replacement is not None:
                return replacement
        if candidate.is_file():
            return candidate.resolve()
    return None


def _package_name(specifier: str) -> str:
    parts = specifier.split("/")
    return "/".join(parts[:2]) if specifier.startswith("@") else parts[0]


def collect_gui_closure(
    gui_root: Path,
    entries: Iterable[str] = (CELL_GUI_ENTRY,),
) -> GuiClosure:
    """
    Računa zatvorenje uvoza od zadatih ulaza.

    Args:
        gui_root: Koren GUI projekta (`apps/gui`).
        entries: Ulazni fajlovi, relativni na `gui_root`.

    Returns:
        Sortirani fajlovi i npm paketi.

    Raises:
        FileNotFoundError: Ako se relativni uvoz ne može razrešiti.
    """
    raw_substitutions = {
        (gui_root / source).resolve(): (gui_root / target).resolve()
        for source, target in load_substitutions(gui_root).items()
    }
    # Ključ je normalizovana putanja (string, bez obzira na slovo diska i
    # velika/mala slova), ne `Path.resolve()` direktno — na Windows-u bi to
    # promašilo zamenu kad se ista putanja stigne drugim zapisom.
    substitutions = {_normalize_key(source): target for source, target in raw_substitutions.items()}

    def apply_substitution(path: Path) -> Path:
        return substitutions.get(_normalize_key(path), path)

    seen: set[Path] = set()
    seen_keys: set[str] = set()
    packages: set[str] = set()
    stack = [apply_substitution((gui_root / entry).resolve()) for entry in entries]

    while stack:
        current = stack.pop()
        current = apply_substitution(current)
        key = _normalize_key(current)
        if key in seen_keys:
            continue
        seen_keys.add(key)
        seen.add(current)

        text = current.read_text(encoding="utf-8", errors="replace")
        text = _strip_comments(text)
        pattern = _CSS_IMPORT if current.suffix == ".css" else _SCRIPT_IMPORT

        for match in pattern.finditer(text):
            groups = [group for group in match.groups() if group]
            if not groups:
                continue
            specifier = groups[0]

            if specifier.startswith("."):
                resolved = _resolve(current, specifier, substitutions)
                if resolved is None:
                    raise FileNotFoundError(
                        f"{_relative(gui_root, current)}: ne mogu da razrešim uvoz {specifier!r}"
                    )
                stack.append(apply_substitution(resolved))
            elif current.suffix != ".css":
                packages.add(_package_name(specifier))

    return GuiClosure(
        files=tuple(sorted(_relative(gui_root, path) for path in seen)),
        npm_packages=tuple(sorted(packages)),
    )


def find_forbidden_gui_modules(closure: GuiClosure, gui_root: Path) -> tuple[str, ...]:
    """
    Vraća fajlove zatvorenja koje ćelija ne sme da nosi.

    Args:
        closure: Zatvorenje GUI uvoza.
        gui_root: Koren GUI projekta čiji `cell-substitutions.json` nosi
            `forbidden_prefixes`.
    """
    prefixes = load_forbidden_prefixes(gui_root)
    return tuple(
        path
        for path in closure.files
        if any(path.startswith(prefix) for prefix in prefixes)
    )
