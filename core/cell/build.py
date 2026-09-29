"""Sklapanje foldera ćelije iz živog repoa.

Ništa se ne briše iz repoa — ovo je kopiranje. Brisanje FILMIUM koda iz CORE-a
je zaseban, kasniji korak, tek kad ćelija dokaže rad.

Ćelija zadržava Python korene `core` i `apps`, pa se nijedan uvoz u kopiranom
kodu ne prepisuje — osim jednog: auto-uvoz prelazi sa KALIMA skenera na
`import_guard` domena.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import urllib.error
import urllib.request
from collections.abc import Callable
from datetime import datetime
from pathlib import Path

from core.cell.build_common import (
    _copy,
    _ignore_kernel_extras,
    _logger,
    _remove_path,
)
from core.cell.build_gui import (
    CELL_GUI_PROJECT_FILES,
    _assemble_gui,
    build_gui_dist,
)
from core.cell.build_import_checks import (
    find_unresolved_local_imports,
)
from core.cell.manifest import CELL_MANIFEST_FILENAME, CellManifest, load_cell_manifest
from core.cell.requirements import build_requirements

GuiBuilder = Callable[[Path, Path], None]


KERNEL_VERSION = "0.1.0"

# Prozor aplikacije ćelije (Rust ljuska, Task 3): putanja relativna na koren
# repoa. `build_cell` ga kopira u koren ćelije pod imenom domena (`<IME>.exe`),
# a `start.bat` ga pokreće. Ako ne postoji, sklapanje staje sa uputstvom da se
# napravi `cargo build --release`.
CELL_SHELL_EXE: str = "apps/cell-shell/target/release/cell-shell.exe"


def cell_exe_name(manifest_name: str) -> str:
    """
    Ime `.exe` fajla ćelije iz imena domena — npr. `"FILMIUM"` -> `"FILMIUM.exe"`.

    Ime zadržava samo slova, cifre, `-` i `_`; sve ostalo (razmaci, tačke,
    kose crte) se izbacuje, pa se dobija bezbedno ime fajla za koren ćelije.
    """

    cleaned = re.sub(r"[^A-Za-z0-9_-]", "", manifest_name)
    return f"{cleaned}.exe"

# Šablon za `config/tmdb.json` u sklopljenoj ćeliji — SAMO rezervisane
# vrednosti, nikad prava CORE tajna niti kopija CORE-ovog `config/tmdb.json`
# (koji na ovoj mašini nosi pravu vrednost — vidi docs/CELIJA_TAJNE.md).
# `core.domains.filmium.tmdb_client` čita baš ovu putanju i baš ovaj oblik;
# ćelija dobija isti "podesi ručno" korak kao svež klon CORE repoa.
_TMDB_CONFIG_TEMPLATE = (
    "{\n"
    '  "access_token": "[ Here put access token for TMDB ]",\n'
    '  "api_key": "[Here put api_key]"\n'
    "}\n"
)

# Kernel ćelije: putanje relativne na koren repoa.
KERNEL_PYTHON_MODULES: tuple[str, ...] = (
    "core/__init__.py",
    "core/foundation",
    "core/database",
    "core/cell",
    "core/rag",
    "core/system/__init__.py",
    "core/system/file_monitor",
    "core/ai/__init__.py",
    "core/ai/ollama_client.py",
    "core/ai/model_registry.py",
    "core/ai/core_router.py",
    "core/ai/personas.py",
    "core/ai/persona_store.py",
    "core/models",
    "core/domains/__init__.py",
    "apps/__init__.py",
    "apps/api/__init__.py",
    "apps/api/streaming.py",
    "apps/api/routers/__init__.py",
    "apps/api/routers/cell.py",
    "apps/api/schemas/cell.py",
)

# Paketi/moduli izvan KERNEL_PYTHON_MODULES koje ćelija ipak mora da nosi u
# celini — svaki je otkriven preko `find_unresolved_local_imports` (ovaj
# modul, niže) kao STVARAN nalaz, ne pretpostavka:
# - `integrations/__init__.py` + `integrations/translator`: `apps/api/routers/
#   filmium.py` (auto-update, TMDB) i `apps/api/routers/filmium_wishlist.py`
#   lenjo uvoze `integrations.translator` unutar funkcija; top-level
#   `integrations` paket nikad nije bio na `KERNEL_PYTHON_MODULES`.
# - `core/media_player.py`: `apps/api/routers/filmium_series.py` (kopira se
#   preko domenskog routera-globa, vidi `_domain_router_paths`) lenjo uvozi
#   `core.media_player.mpv_player` za "Pušta video u ugradjenom mpv-u"; modul
#   uvozi samo `core.foundation.paths` (već u kernelu) i stdlib.
# Svaki od ova dva bi bez ovog spiska pukao sa `ModuleNotFoundError` tek pri
# pokretanju ćelije — nijedan test koji samo uvozi module na vrhu fajla to ne
# bi video. Kopira se, ne premešta — repo izvor ostaje netaknut (ista sadržina,
# samo dupla kopija u ćeliji).
CELL_EXTRA_PACKAGES: tuple[str, ...] = (
    "integrations/__init__.py",
    "integrations/translator",
    "core/media_player.py",
)

# `apps/api/schemas/__init__.py` namerno NIJE na listi: taj fajl ne postoji
# ni u repou (apps.api.schemas radi kao implicitni namespace paket, bez
# __init__.py) — bio je naveden u ranijoj verziji ove liste kao greška, ne
# kao opcioni modul. Otkriveno kad je uveden `skipped`; uklonjeno umesto
# tiho zaobiđeno.

# `core/ai/persona_store.py` ulazi u kernel — ćelijin AI sloj je "lokalna
# Ollama plus podešavanja persone" (core/cell/ai.py, Task 6), a personu čuva
# baš ovaj modul. Njegov lenji uvoz CODIUM personi se u ćeliji prepisuje na
# uklanjanje (vidi `rewrite_persona_store`), jer CODIUM domen ne postoji u
# jednodomenskoj ćeliji.
#
# `core/foundation/context.py`, `core/foundation/runtime.py` i
# `core/database/runtime.py` se ne kopiraju iz istog razloga (vidi
# `_EXCLUDED_KERNEL_FILES` i `_ignore_kernel_extras`): uvoze `core.domains.registry`
# (registar SVIH CORE domena) ili `core.integrations.migrations`. Ćelija je
# jednodomenska pa ništa od toga ne kopira.

# Runtime moduli koje FILMIUM routeri traže.
#
# `apps/api/dependencies.py` je OVDE, ne u `KERNEL_PYTHON_MODULES`, iako živi
# na istoj putanji za svaku ćeliju: sadržaj mu je domenska žica (konstruiše
# svih ~35 FILMIUM repozitorijuma/servisa na nivou modula), ne zamrznut
# kernel — spec §5 kaže da kernel ne nosi domene. Kad se izvuče sledeći domen,
# ovaj fajl treba SVOJU domensku verziju, ne bukvalnu kopiju FILMIUM žice; u
# `KERNEL_PYTHON_MODULES` bi ga `build_cell` kopirao nepromenjeno za svaki
# domen, a `find_foreign_domain_imports` bi prijavio ~35 nalaza sa putanjom
# za prepravku koje nema. U ćeliji se i dalje prepisuje da ne traži
# `ContextService` (vidi `_strip_cross_domain_dependencies`), isto kao pre.
# Iako živi na ovoj listi (a ne u `KERNEL_PYTHON_MODULES`), `apps/api/dependencies.py`
# je JEDINI unos ovde koji NIJE opcion: nedostajući fajl diže `FileNotFoundError`,
# isto kao `KERNEL_PYTHON_MODULES` — bez njega FILMIUM repozitorijumi/servisi
# se ne konstruišu i nijedan FILMIUM router ne radi. Ostatak liste ostaje
# legitimno opcion (vidi `build_cell`, parametar `skipped`).
DOMAIN_RUNTIME_MODULES: tuple[str, ...] = (
    "apps/api/auto_import_runtime.py",
    "apps/api/torrent_runtime.py",
    "apps/api/curator_runtime.py",
    "apps/api/disk_runtime.py",
    "apps/api/dependencies.py",
)

# GUI fajlovi ćelije se od Task 6 više NE nabrajaju ručno (bivši
# `KERNEL_GUI_MODULES`) — `_assemble_gui` računa tačno zatvorenje uvoza od
# `src/cell/cellMain.tsx` preko `collect_gui_closure` (Task 4), primenjujući
# `cell-substitutions.json` (Task 3). To zatvorenje samo od sebe pokupi
# `httpClient.ts`, `sound.ts`, `useCoreSetting.ts` i `CoreChat.tsx` (jer ih
# FILMIUM fajlovi stvarno uvoze), a `CoreAssistantChat.tsx` NIKAD ne uđe —
# zamenjuje ga `src/cell/CellAssistantChat.tsx` pre razrešavanja uvoza.

# Fajlovi GUI projekta koje ćelija nosi pored izvornog zatvorenja.

# Generisane putanje (relativne na koren ćelije) koje `--update` zamenjuje.
# JEDINI izvor politike ažuriranja — zamena, rollback i oporavak rade samo nad
# ovom listom. Sve što NIJE na njoj ostaje tačno gde jeste: `data/`,
# `config/`, ostatak `.ai/` (§9.4 beleške u `.ai/nadogradnje/`, §10 atomi u
# `.ai/atomi/`, dev-log), `.git` ćelije, `gui/node_modules`, korisnikovi
# fajlovi u korenu. `gui/src` JESTE na listi: generiše se iz repoa, pa se
# korisnikove izmene u njemu pri ažuriranju NAMERNO zamenjuju — trajna izmena
# GUI-ja ide u CORE repo.
def generated_on_update(exe_name: str) -> tuple[str, ...]:
    """
    Generisane putanje (relativne na koren ćelije) koje `--update` zamenjuje,
    uključujući `<IME>.exe` (prozor aplikacije) — ime se izračuna iz imena
    domena pri sklapanju (`cell_exe_name`), pa se prosleđuje ovde.

    Ovo je JEDINI izvor politike ažuriranja — zamena, rollback i oporavak rade
    samo nad ovom listom. Sve što NIJE na njoj ostaje tačno gde jeste: `data/`,
    `config/`, `.venv` (korisnički prostor, vidi core/cell/venv.py), ostatak
    `.ai/` (§9.4 beleške u `.ai/nadogradnje/`, §10 atomi u `.ai/atomi/`,
    dev-log), `.git` ćelije, `gui/node_modules`, korisnikovi fajlovi u korenu.
    `gui/src` JESTE na listi: generiše se iz repoa, pa se korisnikove izmene u
    njemu pri ažuriranju NAMERNO zamenjuju — trajna izmena GUI-ja ide u CORE repo.

    Args:
        exe_name: Ime `.exe` fajla ćelije (npr. `"FILMIUM.exe"`), iz `cell_exe_name`.
    """

    base = (
        "core",
        "apps",
        "cell_app.py",
        "start.bat",
        "requirements.txt",
        exe_name,
        CELL_MANIFEST_FILENAME,
        ".ai/CLAUDE.md",
        "gui/src",
        "gui/dist",
        "gui/public",
        "gui/package.json",
        *(f"gui/{name}" for name in CELL_GUI_PROJECT_FILES),
    )
    # Gornji koren svakog `CELL_EXTRA_PACKAGES` unosa (npr. `integrations` iz
    # `integrations/translator`) MORA biti u politici: sklapanje ga stavi u
    # staging, a `--update` prenosi samo ono što je ovde — bez ovoga bi ćelija
    # koja se ažurira ostala bez `integrations/` i pukla sa ModuleNotFoundError.
    # `core` (iz `core/media_player.py`) je već gore; dodajemo samo nove korene.
    extra_roots = tuple(
        root
        for root in dict.fromkeys(module.split("/", 1)[0] for module in CELL_EXTRA_PACKAGES)
        if root not in base
    )
    return base + extra_roots

# Direktorijumi ćelije koje ažuriranje pravi samo ako nedostaju.
CELL_AI_DIRECTORIES: tuple[str, ...] = (".ai/atomi", ".ai/nadogradnje", ".ai/dev-log/entries")

# Marker u backup folderu: zamena je u potpunosti završena, backup je višak.
SWAP_COMPLETE_MARKER = ".swap-complete"

# Alati za ponovni build u ćeliji; verzije se čitaju iz repoa.


# Pojedinačni fajlovi koji se izostavljaju iz inače kopiranih kernel
# direktorijuma, po imenu direktorijuma (ne globalno po imenu fajla — `core/rag`
# i `core/cell` imaju sopstvene, nezavisne `runtime.py` fajlove koji ćeliji
# trebaju). `core/foundation/context.py` i `core/foundation/runtime.py` uvoze
# `core.domains.registry` (registar SVIH CORE domena); `core/database/runtime.py`
# uvozi `core.integrations.migrations` (CORE-ova migracija za konektore, ne
# domenska). Ćeliji ne treba nijedno od ovoga — nijedan kopiran fajl ih ne zove.




# Modul-putanje koje odgovaraju `_EXCLUDED_KERNEL_FILES` (npr. "database" +
# "runtime.py" -> "core.database.runtime"). Izvedeno iz iste mape da ta dva
# spiska ne mogu da se razminu: svaki fajl koji `_ignore_kernel_extras`
# izbaci iz kopije MORA imati odgovarajući unos u `_FORBIDDEN_MODULES`, jer
# fajl koji ga uvozi bi inače prošao i `_ignore_kernel_extras` (fajl
# nedostaje) i `find_forbidden_module_imports` (uvoz nije na crnoj listi) —
# i pao tek na `ModuleNotFoundError` pri pokretanju ćelije.

# Moduli koje ćelija ni pod kojim uslovom ne nosi — svaki od njih vodi ka
# CORE-ovim višedomenskim slojevima (konektori, tajne, registar domena, punog
# AI runtime-a) ili ka fajlovima koje `build_cell` namerno ne kopira
# (`_EXCLUDED_KERNEL_FILE_MODULES`, izvedeno iznad). Za razliku od
# `find_foreign_domain_imports` (koji hvata `core.domains.<bilo koji>`), ovo
# je poimenična crna lista — brana za slučaj da neki budući kopiran fajl
# ponovo uveze nešto što je namerno izbačeno iz kernela, ili da neka buduća
# izmena `_strip_cross_domain_dependencies`/`.replace()` teksta nemo omane
# (npr. jer se tekst iznad nje preformatirao pa se ankerski string više ne
# poklapa) — u tom slučaju `ContextService`-ov uvoz bi ostao u kopiranom
# `dependencies.py`, a `context.py` mu ne bi postojao u ćeliji.










def _guard_not_data(relative: str) -> None:
    """
    Poslednja linija odbrane: nijedno premeštanje pri ažuriranju ne sme da
    dirne `data/` ili `config/` (ni njihov podfajl).

    Pozivajuće petlje (`_swap_staged_cell`, `_recover_backup_before_update`)
    ionako rade samo nad `generated_on_update(...)` — ovo postoji da BUDUĆA
    izmena te liste ili petlji odmah pukne glasno, umesto da tiho premesti
    korisnikovu FILMIUM bazu ili pravu TMDB tajnu.

    Raises:
        ValueError: Ako putanja počinje sa `data` ili `config`.
    """
    parts = Path(relative).parts
    if parts and parts[0] in ("data", "config"):
        raise ValueError(
            f"Pokušaj da se dirne '{relative}' (data/ ili config/) pri zameni/oporavku ćelije — uvek greška."
        )


def _try_move_child(src, relative, dst) -> str | None:
    """Premesti jedno dete src->dst; greška se vraća kao repr (skuplja se, ne guta)."""

    try:
        _move_child(src, relative, dst)
        return None
    except Exception as error:  # noqa: BLE001 — skuplja se, ne guta
        return repr(error)


def _move_child(source_root: Path, relative: str, dest_root: Path) -> None:
    """
    Premešta `source_root/relative` u `dest_root/relative`, uz `_guard_not_data`.

    Odredište NE sme da postoji: `shutil.move` bi postojeći direktorijum
    tiho iskoristio kao roditelja i ugnezdio izvor u njega.

    Raises:
        FileExistsError: Ako odredište već postoji.
    """
    _guard_not_data(relative)
    destination = dest_root / relative
    if os.path.lexists(destination):
        raise FileExistsError(f"Odredište već postoji, premeštanje odbijeno: {destination}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(source_root / relative), str(destination))


def _prune_empty_dirs(root: Path) -> None:
    """Uklanja PRAZNE direktorijume ispod `root` (i sam `root` ako ostane prazan)."""

    if not root.is_dir():
        return
    for directory, _dirs, _files in os.walk(root, topdown=False):
        path = Path(directory)
        try:
            if not any(path.iterdir()):
                path.rmdir()
        except OSError:
            pass  # neprazan ili zaključan — ostaje, ništa se ne gubi


def _strip_cross_domain_dependencies(text: str) -> str:
    """
    Uklanja CORE Context servis iz `apps/api/dependencies.py` u ćeliji.

    `ContextService` prati aktivni domen među SVIM CORE domenima; ćelija ima
    samo jedan domen, pa joj ta zavisnost ne treba, a njen uvoz bi povukao
    `core.domains.registry` (koji ne ulazi u ćeliju — vidi
    `_ignore_kernel_extras`). `get_runtime_lifecycle` ostaje: on koristi
    `core/foundation/lifecycle.py`, koji nema uvoze ka domenima.

    Args:
        text: Sadržaj `apps/api/dependencies.py` iz repoa.

    Returns:
        Izmenjen sadržaj, bez pomena `ContextService`.
    """
    text = text.replace(
        "from core.foundation.context import ContextService, context_service\n",
        "",
    )
    return text.replace(
        'def get_context_service() -> ContextService:\n'
        '    """Vraca CORE Context servis (trenutno stanje sesije)."""\n'
        "\n"
        "    return context_service\n"
        "\n"
        "\n",
        "",
    )


def _domain_router_paths(repo_root: Path, domain_id: str) -> tuple[Path, ...]:
    """Putanje `apps/api/routers/{domain_id}*.py` fajlova, sortirane.

    Jedino mesto koje zna za taj glob — i kopiranje routera u `build_cell` i
    `_api_router_modules` (imena modula za `cell_app.py`) ga pozivaju, da se
    dva spiska nikad ne razmimoiđu.
    """

    routers = repo_root / "apps" / "api" / "routers"
    return tuple(sorted(routers.glob(f"{domain_id}*.py")))


def _api_router_modules(repo_root: Path, domain_id: str) -> tuple[str, ...]:
    """Imena modula `apps.api.routers.{domain_id}*` koje ćelija montira."""

    return tuple(
        f"apps.api.routers.{router.stem}"
        for router in _domain_router_paths(repo_root, domain_id)
    )


def _render_api_routers(modules: tuple[str, ...]) -> str:
    """
    `API_ROUTERS` kao Python literal spreman za ubacivanje u šablon.

    `repr(tuple(...))` je ispravan Python i za prazan tuple (`()`), i za
    tuple sa jednim elementom (`('a',)`), i za više — za razliku od ručnog
    spajanja zarezima (`", ".join(...) + ","`), koje za praznu listu daje
    `(,)`, sintaksnu grešku. Dormant za FILMIUM (16 routera), ali spisak se
    izvodi iz globa baš zato da radi i za budući domen sa 0 ili 1 routerom.
    """

    return repr(tuple(modules))


def _render_template(repo_root: Path, name: str, values: dict[str, str]) -> str:
    """Učitava šablon iz `scripts/cell/templates` i popunjava ga."""

    text = (repo_root / "scripts" / "cell" / "templates" / name).read_text(
        encoding="utf-8"
    )

    for key, value in values.items():
        text = text.replace("{{" + key + "}}", value)

    return text


def rewrite_import_guard(text: str, domain_id: str) -> str:
    """
    Prevodi auto-uvoz sa KALIMA skenera na `import_guard` domena.

    Args:
        text: Sadržaj `auto_import_runtime.py` iz repoa.
        domain_id: Domen ćelije.

    Returns:
        Izmenjen sadržaj, bez ijednog pomena KALIMA-e.
    """
    text = text.replace(
        "from core.domains.kalima.security import FileScanner",
        f"from core.domains.{domain_id}.import_guard import ImportGuard",
    )
    text = text.replace("_scanner = FileScanner()", "_guard = ImportGuard()")
    text = text.replace("_scanner.status_for", "_guard.status_for")
    text = text.replace(
        "KALIMA sigurnosnim skenerom kao adapterom",
        "sopstvenim import_guard-om kao adapterom",
    )
    return text.replace(
        "Adapter: KALIMA SecurityStatus -> FILMIUM SecurityStatus",
        "Adapter: import_guard SecurityStatus -> FILMIUM SecurityStatus",
    )


def rewrite_persona_store(text: str, domain_id: str) -> str:
    """
    Uklanja CODIUM personu iz `core/ai/persona_store.py` u ćeliji.

    Repo verzija nudi CORE, CODIUM i domenske persone iz jednog modula, pa
    lenjo (unutar `_defaults()`) uvozi `core.domains.codium.assistant.personas`.
    Ćelija je jednodomenska i taj uvoz ne sme da postoji. Uklanja se ceo
    "codium" opseg iz `_defaults()` — ne samo uvoz — jer bi inače
    `PersonaStore.scopes()` i dalje prijavljivao opseg koji ne radi
    (`_CODIUM_GLOBAL` postoji, ali `CODIUM_PERSONAS`/`codium_persona_ids` ne
    bi bili definisani).

    Args:
        text: Sadržaj `core/ai/persona_store.py` iz repoa.
        domain_id: Domen ćelije (trenutno se ne koristi za filtriranje jer je
            CODIUM jedini strani opseg u fajlu; zadržan radi simetrije sa
            ostalim `rewrite_*` funkcijama).

    Returns:
        Izmenjen sadržaj, bez ijednog pomena CODIUM-a.
    """
    _ = domain_id  # simetrija potpisa sa ostalim rewrite_* funkcijama

    text = text.replace(
        "    from core.domains.codium.assistant.personas import (  # noqa: PLC0415\n"
        "        PERSONAS as CODIUM_PERSONAS,\n"
        "        persona_ids as codium_persona_ids,\n"
        "    )\n"
        "\n",
        "",
    )
    return text.replace(
        '        "codium": {\n'
        "            GLOBAL_PERSONA: _CODIUM_GLOBAL,\n"
        "            **{pid: CODIUM_PERSONAS[pid] for pid in codium_persona_ids()},\n"
        "        },\n",
        "",
    )


def rewrite_curator_runtime(domain_id: str) -> str:
    """
    Gradi ćelijinu verziju `apps/api/curator_runtime.py`.

    Repo verzija gradi `CuratorService` preko `core_ai_runtime.get_registry()`
    — CORE-ovog punog registra modela sa provajderima, koji dalje uvozi
    `core.integrations` i `core.security.secrets`. Ćelija ne nosi nijedno od
    to dvoje. Umesto prepravke pojedinačnih redova (kao u
    `rewrite_import_guard`), ovde se ceo fajl piše iznova: strategija gradnje
    Kuratora se menja u korenu, ne samo imena — ćelija gradi Kuratora preko
    `core.cell.ai.build_cell_curator`, koji čita samo `cell.json` i govori
    lokalnoj Ollami (Task 6).

    Args:
        domain_id: Domen ćelije, npr. `filmium`.

    Returns:
        Ceo sadržaj ćelijinog `curator_runtime.py`, bez ijednog pomena
        `core_ai_runtime`-a.
    """
    return (
        "# ========== KURATOR RUNTIME (RAG za API, ćelija) ==========\n"
        "# CuratorService se gradi preko core.cell.ai.build_cell_curator\n"
        "# (lokalna Ollama iz cell.json), a ne preko CORE-ovog punog AI\n"
        "# runtime-a — ćelija ne nosi core.integrations ni core.security.\n"
        "from __future__ import annotations\n"
        "\n"
        "from pathlib import Path\n"
        "\n"
        "from core.cell.ai import build_cell_curator\n"
        "from core.cell.manifest import load_cell_manifest\n"
        f"from core.domains.{domain_id}.curator import CuratorService, MediaRetriever\n"
        f"from core.domains.{domain_id}.repository import MediaRepository\n"
        "\n"
        "# Koren ćelije: ovaj fajl živi na `<koren>/apps/api/curator_runtime.py`.\n"
        "_MANIFEST = load_cell_manifest(Path(__file__).resolve().parents[2])\n"
        "_repository = MediaRepository()\n"
        "_retriever = MediaRetriever(_repository.list_all)\n"
        "_service = build_cell_curator(_MANIFEST, _retriever)\n"
        "\n"
        "\n"
        "def get_service() -> CuratorService:\n"
        "    return _service\n"
    )














def _ensure_cell_user_space(root: Path) -> None:
    """
    Pravi korisnički prostor ćelije SAMO ako nedostaje; postojeće ne dira.

    - `.ai/atomi/`, `.ai/nadogradnje/`, `.ai/dev-log/entries/` — sadržaj im je
      korisnikov (§9.4, §10), pa ih ažuriranje nikad ne zamenjuje.
    - `config/tmdb.json` — samo šablon sa rezervisanim vrednostima (vidi
      `_TMDB_CONFIG_TEMPLATE`). Bez njega `tmdb_client.load_credentials` ne bi
      imao šta da pročita i ćelija bi tiho izgubila TMDB metapodatke. Nikad se
      ne prepisuje ako postoji: može da nosi korisnikovu pravu TMDB tajnu,
      koju build_cell nikad ne sme da vidi ni prepiše.
    """
    for relative in CELL_AI_DIRECTORIES:
        (root / relative).mkdir(parents=True, exist_ok=True)

    config_dir = root / "config"
    config_dir.mkdir(parents=True, exist_ok=True)
    tmdb_config_path = config_dir / "tmdb.json"
    if not tmdb_config_path.exists():
        tmdb_config_path.write_text(_TMDB_CONFIG_TEMPLATE, encoding="utf-8")


def _assemble_cell_contents(
    domain_id: str,
    target: Path,
    *,
    repo_root: Path,
    port: int,
    detached_from: str,
    skipped: list[str] | None,
    gui_builder: GuiBuilder,
    existing_manifest_data: dict | None,
    shell_exe: Path,
    exe_name: str,
) -> None:
    """
    Puni `target` kompletnim sadržajem ćelije: Python deo, GUI, `.ai/`,
    pokretanje i manifest.

    Ne proverava da li je `target` prazan niti da li već postoji ćelija — to
    je posao pozivaoca (`build_cell`), koji ovu funkciju zove ili DIREKTNO na
    ciljni folder (prvo sklapanje), ili na privremeni STAGING folder
    (ažuriranje) — tako da neuspešno ažuriranje NIKAD ne ostavi pravi `target`
    u polu-sklopljenom stanju (vidi `build_cell`).

    Args:
        domain_id: Identifikator domena, npr. `filmium`.
        target: Folder u koji se sklapa (ciljni folder ili staging).
        repo_root: Koren CORE repoa iz kog se kopira.
        port: Port koji ide u renderovan `cell.json` PRE eventualnog spajanja
            sa `existing_manifest_data`.
        detached_from: Kratak hash commita iz kog je ćelija izvučena/ažurirana.
        skipped: Opciona lista u koju se upisuje svaki modul iz
            `DOMAIN_RUNTIME_MODULES` koji ne postoji u repou (osim
            `apps/api/dependencies.py`, koji je obavezan — vidi komentar iznad
            `DOMAIN_RUNTIME_MODULES`).
        gui_builder: Pravi `gui/dist` iz sklopljenog `gui/` foldera.
        existing_manifest_data: Manifest postojeće ćelije (pri ažuriranju), iz
            kog se `port`, `core_url`, `ai` i `rag` prenose u novi manifest;
            `None` pri prvom sklapanju (ništa se ne prenosi).

    Raises:
        FileNotFoundError: Ako neki modul iz `KERNEL_PYTHON_MODULES` ne
            postoji u repou; ako `apps/api/dependencies.py` ne postoji u
            repou; ako `apps/gui/public` ne postoji u repou; ili ako GUI build
            ne napravi `gui/dist/index.html`.
        ValueError: Ako GUI zatvorenje (Task 4) vuče CORE-only module.
    """
    target.mkdir(parents=True, exist_ok=True)

    # Kernel — isti raspored kao u repou, pa uvozi rade nepromenjeni. Svaki
    # unos ovde je obavezan; ako ga nema u repou, neko je pogrešno otkucao
    # putanju (ili ga je repo u međuvremenu preimenovao/uklonio) — to se
    # prijavljuje odmah, ne tiho preskače.
    for module in KERNEL_PYTHON_MODULES:
        source = repo_root / module
        if not source.exists():
            raise FileNotFoundError(
                f"Modul iz KERNEL_PYTHON_MODULES ne postoji u repou: "
                f"{module} (očekivano na {source}). Ako je modul stvarno "
                "opcion, izbaci ga iz liste — 'naveden ali odsutan' ovde "
                "znači pogrešno otkucanu putanju, ne opcioni modul."
            )

        if module == "core/ai/persona_store.py":
            destination = target / module
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_text(
                rewrite_persona_store(source.read_text(encoding="utf-8"), domain_id),
                encoding="utf-8",
            )
        elif module in ("core/foundation", "core/database"):
            _copy(source, target / module, ignore=_ignore_kernel_extras)
        else:
            _copy(source, target / module)

    # Paketi izvan core/apps (vidi CELL_EXTRA_PACKAGES) — isti obavezan
    # ugovor kao KERNEL_PYTHON_MODULES: nedostajuća putanja u repou znači
    # pogrešno otkucanu putanju, ne opcioni paket.
    for module in CELL_EXTRA_PACKAGES:
        source = repo_root / module
        if not source.exists():
            raise FileNotFoundError(
                f"Modul iz CELL_EXTRA_PACKAGES ne postoji u repou: "
                f"{module} (očekivano na {source})."
            )
        _copy(source, target / module)

    # Domen.
    _copy(
        repo_root / "core" / "domains" / domain_id,
        target / "core" / "domains" / domain_id,
    )

    # Routeri i sheme domena.
    router_paths = _domain_router_paths(repo_root, domain_id)
    for router in router_paths:
        _copy(router, target / "apps" / "api" / "routers" / router.name)

    schemas = repo_root / "apps" / "api" / "schemas"
    for schema in sorted(schemas.glob(f"{domain_id}*.py")):
        _copy(schema, target / "apps" / "api" / "schemas" / schema.name)

    # Runtime moduli; auto-uvoz se prepisuje na import_guard, a Kurator runtime
    # u potpunosti na core.cell.ai (vidi rewrite_curator_runtime).
    for module in DOMAIN_RUNTIME_MODULES:
        source = repo_root / module
        if not source.exists():
            if module == "apps/api/dependencies.py":
                raise FileNotFoundError(
                    "Modul apps/api/dependencies.py ne postoji u repou "
                    f"(očekivano na {source}). Ovaj modul je ponovo obavezan: "
                    "sadrži domensku žicu FILMIUM repozitorijuma i servisa "
                    "bez koje nijedan FILMIUM router ne radi."
                )
            if skipped is not None:
                skipped.append(module)
            continue
        destination = target / module
        destination.parent.mkdir(parents=True, exist_ok=True)
        if module == "apps/api/curator_runtime.py":
            destination.write_text(rewrite_curator_runtime(domain_id), encoding="utf-8")
        elif module == "apps/api/dependencies.py":
            destination.write_text(
                _strip_cross_domain_dependencies(
                    source.read_text(encoding="utf-8")
                ),
                encoding="utf-8",
            )
        else:
            destination.write_text(
                rewrite_import_guard(source.read_text(encoding="utf-8"), domain_id),
                encoding="utf-8",
            )

    # GUI — izvorno zatvorenje, projektni fajlovi i Vite build (posle Python
    # dela, pre upisa manifesta, vidi docstring gore).
    _assemble_gui(repo_root, target, gui_builder)

    # `.ai` direktorijum ćelije: `CLAUDE.md` je generisan, ostalo je korisnikovo
    # (vidi `_ensure_cell_user_space`).
    _ensure_cell_user_space(target)
    (target / ".ai" / "CLAUDE.md").write_text(
        _render_template(
            repo_root,
            "CLAUDE.md.tpl",
            {"DOMAIN_ID": domain_id, "DOMAIN_NAME": domain_id.upper()},
        ),
        encoding="utf-8",
    )

    # Pokretanje i zavisnosti.
    api_routers = _api_router_modules(repo_root, domain_id)
    (target / "cell_app.py").write_text(
        _render_template(
            repo_root,
            "cell_app.py.tpl",
            {
                "DOMAIN_ID": domain_id,
                "API_ROUTERS": _render_api_routers(api_routers),
            },
        ),
        encoding="utf-8",
    )
    # Prozor aplikacije (Rust ljuska): kopira se u koren ćelije pod imenom
    # domena; `start.bat` ga pokreće. Deo je `generated_on_update`, pa ga
    # `--update` osvežava (izvor exe-a je proveren u `build_cell`).
    _copy(shell_exe, target / exe_name)
    (target / "start.bat").write_text(
        _render_template(
            repo_root,
            "start.bat.tpl",
            {
                "DOMAIN_NAME": domain_id.upper(),
                "DOMAIN_ID": domain_id,
                "PORT": str(port),
                "EXE_NAME": exe_name,
            },
        ),
        encoding="utf-8",
    )
    # Suženi requirements.txt — samo ono što kod ćelije stvarno uvozi (vidi
    # core/cell/requirements.py), ne CORE-ov puni requirements.txt (koji nosi
    # i anthropic/openai/mcp/keyring, CORE-ov AI/tajne sloj). Piše se OVDE,
    # posle kopiranja svih Python modula (core/apps/integrations, cell_app.py
    # iznad) — build_requirements skenira baš njih.
    (target / "requirements.txt").write_text(build_requirements(target), encoding="utf-8")

    # Manifest. `detached_from`, `kernel_version` i `created_at` su uvek novi;
    # pri ažuriranju se `port`, `core_url`, `ai` i `rag` zadržavaju iz
    # postojećeg manifesta (pročitanog PRE brisanja, na vrhu funkcije), a novi
    # `port` argument se ignoriše — CORE ne sme da premesti ćeliju na drugi
    # port samim ažuriranjem koda.
    manifest_data = json.loads(
        _render_template(
            repo_root,
            "cell.json.tpl",
            {
                "DOMAIN_ID": domain_id,
                "DOMAIN_NAME": domain_id.upper(),
                "KERNEL_VERSION": KERNEL_VERSION,
                "PORT": str(port),
                "CREATED_AT": datetime.now().isoformat(timespec="seconds"),  # noqa: DTZ005
                "DETACHED_FROM": detached_from,
            },
        )
    )
    if existing_manifest_data is not None:
        manifest_data["port"] = existing_manifest_data.get("port", manifest_data["port"])
        manifest_data["core_url"] = existing_manifest_data.get("core_url")
        manifest_data["ai"] = existing_manifest_data.get("ai")
        manifest_data["rag"] = existing_manifest_data.get("rag")

    (target / CELL_MANIFEST_FILENAME).write_text(
        json.dumps(manifest_data, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def _backup_dir_for(target: Path) -> Path:
    """Susedni folder u koji `_swap_staged_cell` premešta stari sadržaj `target`-a."""

    return target.parent / f".{target.name}.old"


def _remove_completed_backup(backup: Path) -> None:
    """
    Uklanja backup ZAVRŠENE zamene, marker `SWAP_COMPLETE_MARKER` poslednji.

    Kad bi marker nestao prvi a brisanje ostatka puklo (zaključan fajl),
    sledeće ažuriranje bi video backup bez markera, sa imenima koja se sudaraju
    sa `target`-om, i odbijalo bi zauvek. Ovako marker preživi svaki
    delimičan neuspeh.

    Raises:
        OSError: Ako nešto ne može da se ukloni (marker tad ostaje).
    """
    for child in list(backup.iterdir()):
        if child.name != SWAP_COMPLETE_MARKER:
            _remove_path(child)
    (backup / SWAP_COMPLETE_MARKER).unlink(missing_ok=True)
    backup.rmdir()


def _swap_staged_cell(target: Path, staging: Path, exe_name: str) -> None:
    """
    Menja GENERISANE putanje `target`-a (`generated_on_update`) sadržajem iz
    `staging`-a — PREMEŠTANJEM, nikad brisanjem, dok se ne zna da je zamena
    uspela. Sve što nije na listi ostaje netaknuto na svom mestu.

    - FAZA A: svaka generisana putanja koja postoji u `target`-u se premesti u
      susedni BACKUP folder (`_backup_dir_for(target)`), na istu relativnu
      putanju (npr. `gui/src`, `.ai/CLAUDE.md`). Svako premeštanje se beleži.
    - FAZA B: svaka generisana putanja iz `staging`-a se premesti u `target`.
      Zatim se prave `.ai/` direktorijumi i `config/tmdb.json` šablon SAMO ako
      nedostaju (`_ensure_cell_user_space`).
    - Ako BILO ŠTA u A ili B pukne: ono što je faza B prebacila se vrati u
      `staging`, a ono što je faza A prebacila se vrati u `target`. Svaki
      korak vraćanja je u sopstvenom `try` — pokušavaju se SVI, neuspesi se
      skupljaju i dodaju kao beleške (`add_note`) na ORIGINALNI izuzetak, koji
      se prosleđuje dalje. Ništa se ne briše: što ne može da se vrati ostaje u
      backup-u (sledeće ažuriranje ga oporavlja).
    - Na uspeh: u backup se upisuje `SWAP_COMPLETE_MARKER`, pa se backup i
      staging uklanjaju. Ako čišćenje padne (zaključan fajl), samo upozorenje —
      živa ćelija je kompletna, a marker govori sledećem pokretanju da je
      backup višak (vidi `_recover_backup_before_update`).

    Raises:
        RuntimeError: Ako backup folder već postoji (oporavak ga nije uklonio).
    """
    backup = _backup_dir_for(target)
    if os.path.lexists(backup):
        raise RuntimeError(
            f"Backup folder {backup} i dalje postoji (verovatno zaključan fajl iz "
            "prethodnog ažuriranja). Zatvori program koji ga drži i pokušaj ponovo."
        )
    backup.mkdir(parents=True)

    moved_to_backup: list[str] = []
    moved_to_target: list[str] = []

    generated = generated_on_update(exe_name)
    try:
        for relative in generated:
            if os.path.lexists(target / relative):
                _move_child(target, relative, backup)
                moved_to_backup.append(relative)

        for relative in generated:
            if os.path.lexists(staging / relative):
                _move_child(staging, relative, target)
                moved_to_target.append(relative)

        _ensure_cell_user_space(target)
    except BaseException as error:
        rollback_failures: list[str] = []

        for relative in reversed(moved_to_target):
            move_error = _try_move_child(target, relative, staging)
            if move_error:
                rollback_failures.append(
                    f"vraćanje novog '{relative}' iz {target} u {staging}: {move_error}"
                )

        for relative in reversed(moved_to_backup):
            move_error = _try_move_child(backup, relative, target)
            if move_error:
                rollback_failures.append(
                    f"vraćanje starog '{relative}' iz {backup} u {target}: {move_error}"
                )

        _prune_empty_dirs(backup)

        for failure in rollback_failures:
            error.add_note(
                f"Rollback ažuriranja ćelije NIJE uspeo za {failure}. Ništa nije "
                "obrisano — stara verzija ostaje u backup folderu i sledeće "
                "ažuriranje je prvo oporavlja."
            )
        raise

    try:
        (backup / SWAP_COMPLETE_MARKER).write_text(
            datetime.now().isoformat(timespec="seconds") + "\n", encoding="utf-8"  # noqa: DTZ005
        )
        _remove_completed_backup(backup)
    except OSError as error:
        _logger.warning(
            "Ažuriranje ćelije je uspelo, ali uklanjanje backup-a %s nije: %s", backup, error,
        )

    try:
        _remove_path(staging)
    except OSError as error:
        _logger.warning(
            "Ažuriranje ćelije je uspelo, ali uklanjanje staging-a %s nije: %s", staging, error,
        )


def _recover_backup_before_update(target: Path, exe_name: str) -> None:
    """
    Oporavak od backup foldera koji je ostao iza prethodnog ažuriranja.

    - Backup SA `SWAP_COMPLETE_MARKER`: zamena je bila završena, samo čišćenje
      nije (zaključan fajl, pad procesa) — backup se ukloni, a neuspeh je samo
      upozorenje.
    - Backup BEZ markera: proces je ugašen NASRED zamene, pa `target` možda
      NEMA `cell.json` (u backup-u je). "Sve ili ništa" provera: ako ijedna
      generisana putanja postoji i u `target`-u i u backup-u, ništa se ne
      dira i diže se jasna greška. Inače se svaka generisana putanja vraća u
      `target`, svaka u sopstvenom `try`; neuspesi se skupljaju kao beleške.

    Args:
        target: Koren ćelije koji `--update` cilja.

    Raises:
        RuntimeError: Ako `target` i backup imaju istu generisanu putanju; ili
            ako vraćanje nije potpuno (backup posle njega nije prazan) — beleške
            izuzetka nabrajaju svaki neuspeo korak.
    """
    backup = _backup_dir_for(target)
    if not backup.is_dir():
        return

    if (backup / SWAP_COMPLETE_MARKER).is_file():
        try:
            _remove_completed_backup(backup)
        except OSError as error:
            _logger.warning(
                "Backup završenog ažuriranja %s nije mogao da se ukloni: %s", backup, error,
            )
        return

    target.mkdir(parents=True, exist_ok=True)
    present = [
        relative
        for relative in generated_on_update(exe_name)
        if os.path.lexists(backup / relative)
    ]

    conflicts = [relative for relative in present if os.path.lexists(target / relative)]
    if conflicts:
        raise RuntimeError(
            "Oporavak posle prekinutog ažuriranja nije bezbedan: i "
            f"{target} i {backup} imaju {', '.join(conflicts)}. Uporedi ih "
            "ručno (koja verzija treba da ostane) i obriši stariju pre novog "
            "pokušaja ažuriranja — ništa nije obrisano ni premešteno."
        )

    failures: list[str] = []
    for relative in present:
        error = _try_move_child(backup, relative, target)
        if error:
            failures.append(f"vraćanje '{relative}' iz {backup} u {target}: {error}")

    _prune_empty_dirs(backup)

    if failures or backup.exists():
        error = RuntimeError(
            f"Oporavak posle prekinutog ažuriranja nije potpun: {backup} i dalje "
            "postoji. Ništa nije obrisano — premesti ostatak ručno u ćeliju pa "
            "pokušaj ažuriranje ponovo."
        )
        for failure in failures:
            error.add_note(f"Neuspeo korak oporavka: {failure}")
        raise error


def _validate_target(target: Path) -> None:
    """
    Odbija cilj bez imena ili koren diska (npr. `F:\\`).

    Staging i backup su SUSEDI cilja (`<roditelj>/.<ime>.staging`), pa koren
    diska ili prazno ime daju besmislene putanje (`..staging` u samom korenu),
    a ažuriranje korena diska bi premeštalo tuđe fajlove.

    Raises:
        ValueError: Ako `target` nema ime ili mu je roditelj on sam.
    """
    absolute = Path(os.path.abspath(target))
    if not absolute.name or absolute.parent == absolute:
        raise ValueError(
            f"Ciljni folder ćelije mora biti imenovan podfolder, ne koren diska: {target}"
        )


def _port_from_manifest(candidate: Path) -> int | None:
    """Pročitaj port iz cell.json kandidata; None za neispravan/nedostajući."""

    try:
        return int(json.loads(candidate.read_text(encoding="utf-8"))["port"])
    except (OSError, ValueError, KeyError, TypeError):
        return None


def _existing_cell_port(target: Path) -> int | None:
    """Port iz `cell.json` postojeće ćelije (ili iz backup-a prekinute zamene)."""

    for candidate in (target / CELL_MANIFEST_FILENAME, _backup_dir_for(target) / CELL_MANIFEST_FILENAME):
        port = _port_from_manifest(candidate)
        if port is not None:
            return port
    return None


def _cell_is_running(port: int) -> bool:
    """
    Da li na `127.0.0.1:<port>` nešto odgovara na `/cell/status` (1 s rok).

    Svaki HTTP odgovor (i 503) znači da proces sluša na tom portu. Proxy se
    zaobilazi — lokalna provera ne sme da ode kroz sistemski proxy.
    """
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        with opener.open(f"http://127.0.0.1:{port}/cell/status", timeout=1.0):
            return True
    except urllib.error.HTTPError:
        return True
    except (OSError, ValueError):
        return False


def build_cell(
    domain_id: str,
    target: Path,
    *,
    repo_root: Path,
    port: int,
    detached_from: str,
    skipped: list[str] | None = None,
    gui_builder: GuiBuilder = build_gui_dist,
    shell_exe: Path | None = None,
    update: bool = False,
) -> CellManifest:
    """
    Sklapa folder ćelije za zadati domen.

    Args:
        domain_id: Identifikator domena, npr. `filmium`.
        target: Ciljni folder ćelije. Kad `update=False`, mora biti prazan ili
            nepostojeći. Kad `update=True`, mora već sadržati `cell.json`.
        repo_root: Koren CORE repoa iz kog se kopira.
        port: Port koji CORE dodeljuje ćeliji. Pri `update=True` se ignoriše —
            zadržava se port iz postojećeg manifesta (vidi `update` niže).
        detached_from: Kratak hash commita iz kog je ćelija izvučena/ažurirana.
        skipped: Opciona lista u koju se upisuje svaki modul iz
            `DOMAIN_RUNTIME_MODULES` koji ne postoji u repou — taj spisak je
            legitimno opcion (neki budući domen možda nema svoj Kurator
            runtime, na primer), OSIM `apps/api/dependencies.py`, koji je
            ponovo obavezan (vidi komentar iznad `DOMAIN_RUNTIME_MODULES`).
            `KERNEL_PYTHON_MODULES` NIJE opcion: "naveden ali odsutan" tu
            znači pogrešno otkucanu putanju, pa nedostatak diže
            `FileNotFoundError` umesto da se tiho upiše u ovu listu.
        gui_builder: Pravi `gui/dist` iz sklopljenog `gui/` foldera; podrazumevano
            `build_gui_dist` (pravi Vite build). Testovi prosleđuju lažni builder
            da izbegnu pravi build u svakom pokretanju.
        update: Kad je `True`, ćelija se ponovo sklapa u PRIVREMENI folder
            (`<target roditelj>/.{target ime}.staging`, na istom disku kao
            `target`), a `target` se menja tim sadržajem TEK kad je sklapanje
            u potpunosti uspelo (Python deo, GUI zatvorenje, `public/`, Vite
            build — vidi `_assemble_cell_contents`). Sama zamena
            (`_swap_staged_cell`) ide PREMEŠTANJEM u susedni backup folder
            (`<target roditelj>/.{target ime}.old`), nikad brisanjem, dok se
            ne zna da je uspela — ako bilo šta u zameni pukne (npr. zaključan
            fajl), sve što je već premešteno se vrati nazad i `target` ostaje
            BAJT-ZA-BAJT onakav kakav je bio pre poziva; `staging` ostaje za
            sledeći pokušaj. Ako proces bude ugašen NASRED zamene (posle
            backup-a, pre nego što sama zamena stigne da se vrati), sledeći
            poziv sa `update=True` prvo oporavlja iz backup foldera (vidi
            `_recover_backup_before_update`) pre bilo čega drugog. Menjaju se
            SAMO putanje iz `generated_on_update(...)`; `data`, `config`, ostatak
            `.ai/`, `.git`, `gui/node_modules` i sve ostalo ostaje na mestu.
            `port`, `core_url`, `ai` i `rag` se zadržavaju iz postojećeg
            `cell.json`; `detached_from`, `kernel_version` i `created_at`
            postaju novi. `config/tmdb.json` se NIKAD ne prepisuje ako već
            postoji — korisnikova prava TMDB tajna se ne sme izgubiti.
            Ostatak staging foldera iz prethodnog prekinutog pokušaja
            ažuriranja se ukloni pre novog pokušaja. Ažuriranje se odbija dok
            ćelija radi (odgovara na `/cell/status` na svom portu).

    Returns:
        Manifest sklopljene ćelije.

    Raises:
        FileExistsError: Ako `update=False` i ciljni folder postoji i nije prazan.
        FileNotFoundError: Ako `update=True` a folder nema `cell.json` (folder
            ostaje netaknut); ako neki modul iz `KERNEL_PYTHON_MODULES` ne
            postoji u repou; ako `apps/api/dependencies.py` ili
            `apps/gui/public` ne postoje u repou; ili ako GUI build ne napravi
            `gui/dist/index.html`. Pri `update=True`, `target` ostaje netaknut
            u svim ovim slučajevima.
        ValueError: Ako `target` nema ime ili je koren diska; ako GUI zatvorenje
            vuče CORE-only module ili kopija GUI izvora nije samodovoljna
            (isto, `target` ostaje netaknut pri `update=True`).
        RuntimeError: Ako ćelija radi dok se ažurira; ili ako oporavak od
            prekinute zamene (`_recover_backup_before_update`) nailazi na istu
            putanju i u `target`-u i u backup folderu — ništa se ne dira,
            korisnik mora ručno da odluči koja verzija ostaje.
    """
    _validate_target(target)

    # Prozor aplikacije: podrazumevano iz repoa (`repo_root / CELL_SHELL_EXE`).
    # Proverava se PRE diranja diska — nedostajući exe ne sme da obori radnu
    # ćeliju pri `--update`, ni da ostavi polu-sklopljen `target` pri sklapanju.
    if shell_exe is None:
        shell_exe = repo_root / CELL_SHELL_EXE
    if not shell_exe.is_file():
        raise FileNotFoundError(
            f"Prozor aplikacije ćelije ne postoji: {shell_exe}. "
            "Napravi ga u apps/cell-shell: `cargo build --release`."
        )
    exe_name = cell_exe_name(domain_id.upper())

    if update:
        # Pre bilo kakvog diranja diska: pokrenuta ćelija drži fajlove
        # zaključane i menjala bi kod ispod sebe.
        running_port = _existing_cell_port(target)
        if running_port is not None and _cell_is_running(running_port):
            raise RuntimeError(
                f"Ćelija u {target} radi (odgovara na http://127.0.0.1:{running_port}/cell/status). "
                "Zaustavi je (zatvori prozor start.bat) pa pokreni ažuriranje ponovo."
            )

        # Zatim, pre svega ostalog: ako je proces prošli put ugašen NASRED
        # zamene, `target` možda NEMA `cell.json` (već je u backup folderu).
        _recover_backup_before_update(target, exe_name)

        manifest_path = target / CELL_MANIFEST_FILENAME
        if not manifest_path.is_file():
            raise FileNotFoundError(
                f"Ažuriranje traži postojeću ćeliju: nema {CELL_MANIFEST_FILENAME} u {target}"
            )
        existing_manifest_data = json.loads(manifest_path.read_text(encoding="utf-8"))

        # Staging je UVEK sused `target`-a (isti disk, isti roditeljski
        # folder) — premeštanja u `_swap_staged_cell` su onda preimenovanja,
        # ne kopiranja preko particija.
        staging = target.parent / f".{target.name}.staging"
        if staging.exists():
            # Ostatak iz prethodnog prekinutog pokušaja ažuriranja.
            _remove_path(staging)

        try:
            _assemble_cell_contents(
                domain_id,
                staging,
                repo_root=repo_root,
                port=port,
                detached_from=detached_from,
                skipped=skipped,
                gui_builder=gui_builder,
                existing_manifest_data=existing_manifest_data,
                shell_exe=shell_exe,
                exe_name=exe_name,
            )
            # Poslednja provera PRE zamene: ako sklopljeni staging ima uvoz
            # ka paketu koji postoji u repou a ne u samoj ćeliji (npr. neki
            # budući router lenjo uveze novi top-level paket koji niko nije
            # dodao u CELL_EXTRA_PACKAGES), ažuriranje nikad ne sme da tim
            # kodom zameni radnu ćeliju.
            unresolved = find_unresolved_local_imports(staging, repo_root)
            if unresolved:
                raise ValueError(
                    "Sklopljena ćelija (staging) ima nerazrešene lokalne "
                    "uvoze — ažuriranje je zaustavljeno PRE zamene, target "
                    "ostaje netaknut:\n" + "\n".join(unresolved)
                )
        except BaseException:
            if staging.exists():
                _remove_path(staging)
            raise

        # `_swap_staged_cell` sam uklanja i backup i `staging` na uspeh (i
        # ostavlja `staging` netaknut da bi se izuzetak ispod mogao prosledi-
        # ti dalje ako zamena sama pukne — vidi njen docstring).
        _swap_staged_cell(target, staging, exe_name)
    else:
        if target.exists() and any(target.iterdir()):
            raise FileExistsError(f"Ciljni folder nije prazan: {target}")

        _assemble_cell_contents(
            domain_id,
            target,
            repo_root=repo_root,
            port=port,
            detached_from=detached_from,
            skipped=skipped,
            gui_builder=gui_builder,
            existing_manifest_data=None,
            shell_exe=shell_exe,
            exe_name=exe_name,
        )

    return load_cell_manifest(target)
















