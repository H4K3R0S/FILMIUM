"""Cell build — sklapanje GUI-ja (dist/package.json/tsconfig/closure) —
izdvojeno iz build.py radi veličine."""

from __future__ import annotations

import json
import subprocess
import sys
from collections.abc import Callable, Iterable
from pathlib import Path

from core.cell.build_common import _copy, _logger
from core.cell.gui import (
    GuiClosure,
    collect_gui_closure,
    find_forbidden_gui_modules,
)

GuiBuilder = Callable[[Path, Path], None]

CELL_GUI_PROJECT_FILES: tuple[str, ...] = (
    "cell.html",
    "vite.cell.config.ts",
    "cell-substitutions.json",
    "tsconfig.json",
    "tsconfig.app.json",
    "tsconfig.node.json",
)

CELL_GUI_DEV_DEPENDENCIES: tuple[str, ...] = (
    "vite",
    "@vitejs/plugin-react",
    "typescript",
    "@types/react",
    "@types/react-dom",
    "@types/node",
)


def build_gui_dist(repo_root: Path, out_dir: Path) -> None:
    """
    Pravi Vite build ćelijskog GUI-ja iz repoa, CORE-ovim `node_modules`.

    Raises:
        RuntimeError: Ako build ne uspe; poruka nosi kraj Vite izlaza.
    """
    gui_root = repo_root / "apps" / "gui"
    result = subprocess.run(
        ["npx", "vite", "build", "--config", "vite.cell.config.ts", "--outDir", str(out_dir)],
        cwd=gui_root,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        shell=sys.platform == "win32",  # nosec B602 — npx zahteva shell SAMO na Windows; args su lista (bez injekcije)
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(f"Vite build ćelije nije uspeo:\n{(result.stdout + result.stderr)[-4000:]}")


def _installed_version(repo_root: Path, name: str, fallback: str) -> str:
    """
    TAČNA verzija paketa instalirana u repou (`apps/gui/node_modules/<paket>`).

    `dist` ćelije se pravi iz repoa baš tim verzijama; opseg iz repo
    `package.json` (`^19.2.7`) bi `npm install` u ćeliji razrešio na neku
    kasniju verziju, pa bi izvor i `dist` mogli da se razmimoiđu. Ako paket
    nije instaliran, vraća se opseg iz repoa uz upozorenje.
    """
    manifest = repo_root / "apps" / "gui" / "node_modules" / Path(*name.split("/")) / "package.json"
    try:
        version = json.loads(manifest.read_text(encoding="utf-8")).get("version")
    except (OSError, ValueError):
        version = None
    if isinstance(version, str) and version:
        return version
    _logger.warning(
        "npm paket %s nije instaliran u %s — package.json ćelije dobija opseg iz repoa (%s)",
        name, manifest.parent, fallback,
    )
    return fallback


def _write_gui_package_json(repo_root: Path, target: Path, npm_packages: Iterable[str]) -> None:
    """Upisuje `package.json` ćelije sa samo onim paketima koje GUI stvarno traži, u tačnim verzijama."""

    source = json.loads((repo_root / "apps" / "gui" / "package.json").read_text(encoding="utf-8"))
    dependencies = source.get("dependencies", {})
    dev_dependencies = source.get("devDependencies", {})

    package = {
        "name": "filmium-cell-gui",
        "private": True,
        "version": "0.0.0",
        "type": "module",
        "scripts": {"build": "vite build --config vite.cell.config.ts --outDir dist"},
        "dependencies": {
            name: _installed_version(repo_root, name, dependencies[name])
            for name in sorted(npm_packages)
            if name in dependencies
        },
        "devDependencies": {
            name: _installed_version(repo_root, name, dev_dependencies[name])
            for name in CELL_GUI_DEV_DEPENDENCIES
            if name in dev_dependencies
        },
    }
    (target / "gui" / "package.json").write_text(
        json.dumps(package, indent=2, ensure_ascii=False) + "\n", encoding="utf-8",
    )


def _trim_gui_tsconfig_references(cell_gui_root: Path) -> None:
    """
    Iz ćelijinog `tsconfig.json` izbacuje reference na tsconfig fajlove koje
    ćelija ne nosi.

    Repo `tsconfig.json` referencira i `tsconfig.test.json` (vitest tipovi),
    koji ćelija nema; Vite-ov transform čita tsconfig lanac i build u ćeliji
    je pucao sa "Tsconfig not found ... tsconfig.test.json".
    """
    path = cell_gui_root / "tsconfig.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    references = data.get("references")
    if not isinstance(references, list):
        return
    data["references"] = [
        reference
        for reference in references
        if (cell_gui_root / str(reference.get("path", ""))).is_file()
    ]
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _verify_copied_gui_closure(cell_gui_root: Path, repo_closure: GuiClosure) -> None:
    """
    Proverava da je kopirani GUI izvor ćelije samodovoljan.

    `dist` se i dalje pravi iz repoa, pa bi ćelijin `gui/src` mogao tiho da
    bude neupotrebljiv (uvoz ka originalu koji u ćeliji ne postoji) — tako je
    `npm run build` u ćeliji ranije pucao. Zato se zatvorenje računa ponovo,
    nad kopijom, i mora da da TAČNO isti skup fajlova kao u repou.

    Raises:
        ValueError: Ako se kopija ne razrešava ili joj se skup fajlova razlikuje.
    """
    try:
        copied = collect_gui_closure(cell_gui_root)
    except FileNotFoundError as error:
        raise ValueError(
            f"GUI izvor ćelije nije samodovoljan — uvoz se ne razrešava u kopiji: {error}"
        ) from error

    repo_files = set(repo_closure.files)
    copied_files = set(copied.files)
    if copied_files != repo_files:
        missing = sorted(repo_files - copied_files)
        extra = sorted(copied_files - repo_files)
        raise ValueError(
            "GUI zatvorenje kopije ćelije se razlikuje od zatvorenja u repou. "
            f"Nedostaje u kopiji: {', '.join(missing) or '-'}; "
            f"višak u kopiji: {', '.join(extra) or '-'}."
        )


def _assemble_gui(repo_root: Path, target: Path, gui_builder: GuiBuilder) -> None:
    """Kopira izvorno zatvorenje GUI-ja, `public/`, projektne fajlove i pravi build."""

    gui_root = repo_root / "apps" / "gui"
    closure = collect_gui_closure(gui_root)

    forbidden = find_forbidden_gui_modules(closure, gui_root)
    if forbidden:
        raise ValueError("GUI ćelije vuče CORE-only module: " + ", ".join(forbidden))

    for relative in closure.files:
        _copy(gui_root / relative, target / "gui" / relative)

    for relative in CELL_GUI_PROJECT_FILES:
        source = gui_root / relative
        if not source.is_file():
            raise FileNotFoundError(f"GUI projekat nema {relative}")
        _copy(source, target / "gui" / relative)

    _trim_gui_tsconfig_references(target / "gui")

    # `public/` je Vite-ov statički koren — fajlovi na koje se referenciše
    # samo preko CSS `url(...)` ili runtime stringa (pozadina, fontovi,
    # zvukovi) su NEVIDLJIVI za `collect_gui_closure` (koji prati samo
    # import/export uvoze), pa se ne mogu pokupiti preko zatvorenja. Bez ovog
    # kopiranja, `npm run build` iz ćelijinog `gui/` bi tiho napravio `dist/`
    # bez pozadine, fontova i zvukova. Obavezan je kao i ostali projektni
    # fajlovi — nedostajući `public/` diže istu grešku.
    public_source = gui_root / "public"
    if not public_source.is_dir():
        raise FileNotFoundError(f"GUI projekat nema public/ direktorijum: {public_source}")
    _copy(public_source, target / "gui" / "public")

    _verify_copied_gui_closure(target / "gui", closure)

    _write_gui_package_json(repo_root, target, closure.npm_packages)

    dist = target / "gui" / "dist"
    gui_builder(repo_root, dist)
    if not (dist / "index.html").is_file():
        raise FileNotFoundError(f"GUI build nije napravio {dist / 'index.html'}")
