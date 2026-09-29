"""Ulazna tačka ćelije filmium.

Jedan proces služi ceo API domena i GUI build na istom originu. Putanje se
preusmeravaju i baza inicijalizuje PRE uvoza routera: `apps/api/dependencies.py`
pravi repozitorijume i servise već pri uvozu, pa bi inače gađali CORE putanje.
"""

import importlib
import sys
from pathlib import Path

CELL_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(CELL_ROOT))

from core.cell.database import initialize_cell_database
from core.cell.manifest import load_cell_manifest
from core.cell.paths import apply_cell_paths
from core.cell.rag_bootstrap import ensure_cell_rag_db

MANIFEST = load_cell_manifest(CELL_ROOT)
apply_cell_paths(MANIFEST)
initialize_cell_database(MANIFEST)
# Sopstvena RAG baza celije (opciono, tolerantno).
ensure_cell_rag_db()

# Cross-platform: uskladi korene biblioteke sa stvarnim mountom diska
# (Windows "F:\\" <-> Linux "/run/media/<user>/FILMIUM"). Bez ovoga izvorne
# slike/fajlovi na Linuxu nisu čitljivi jer je u bazi Windows putanja.
try:  # tolerantno — greška ne sme da obori pokretanje ćelije
    from core.domains.filmium.os_library_bridge import (
        sync_library_roots_for_current_os,
    )

    _synced = sync_library_roots_for_current_os(
        CELL_ROOT / "data" / "filmium.db", CELL_ROOT
    )
    if _synced:
        print(f"FILMIUM: koreni biblioteke usklađeni sa OS-om ({_synced} zapisa).")
except Exception as _bridge_error:  # noqa: BLE001
    print(f"FILMIUM: usklađivanje korena biblioteke preskočeno: {_bridge_error}")

# Best-effort: po startu pokreni `tmdb_people_import` (v. core/domains/filmium/
# jobs/tmdb_people_import.py) u SOPSTVENOJ pozadinskoj (daemon) niti — cilj je
# "po startu pokrene preuzimanje" bez ijednog milisekunda usporenja boot-a.
# `JobRegistry.start()` sam kreira nit za posao, ali njeno pokretanje (uvoz
# registra + inicijalni SSE emit ka Second Brain, koji ima svoj mali timeout)
# se ovde DODATNO izmešta iz boot niti da ni to ne dotakne podizanje ćelije.
# Dok je TMDB ključ placeholder u `config/tmdb.json`, posao samo jeftino
# regeneriše atome iz baze (mrežni deo se sam preskače — v. `_tmdb_ready`).
try:  # tolerantno — greška ne sme da obori pokretanje ćelije
    import threading as _threading

    def _start_tmdb_people_import() -> None:
        try:
            from core.domains.filmium.jobs.registry import REGISTRY

            REGISTRY.start("tmdb_people_import")
        except Exception as _job_error:  # noqa: BLE001
            print(f"FILMIUM: tmdb_people_import (startup) preskočen: {_job_error}")

    _threading.Thread(
        target=_start_tmdb_people_import,
        name="tmdb_people_import-startup",
        daemon=True,
    ).start()

    # Best-effort: po startu napravi nedostajuće parove pisma prevoda
    # (latinica↔ćirilica). Idempotentno — postojeći parovi se preskaču.
    def _start_subtitle_script_pair() -> None:
        try:
            from core.domains.filmium.jobs.registry import REGISTRY

            REGISTRY.start("subtitle_script_pair")
        except Exception as _job_error:  # noqa: BLE001
            print(
                f"FILMIUM: subtitle_script_pair (startup) preskočen: {_job_error}"
            )

    _threading.Thread(
        target=_start_subtitle_script_pair,
        name="subtitle_script_pair-startup",
        daemon=True,
    ).start()
except Exception as _startup_thread_error:  # noqa: BLE001
    print(f"FILMIUM: pokretanje tmdb_people_import niti preskočeno: {_startup_thread_error}")

from fastapi import FastAPI
from starlette.middleware.trustedhost import TrustedHostMiddleware
from starlette.staticfiles import StaticFiles

from apps.api.routers import cell as cell_router
from apps.api.routers import cell_brain as cell_brain_router

API_ROUTERS = ('apps.api.routers.system', 'apps.api.routers.player', 'apps.api.routers.solve', 'apps.api.routers.filmium', 'apps.api.routers.filmium_activity', 'apps.api.routers.filmium_auto_import', 'apps.api.routers.filmium_collections', 'apps.api.routers.filmium_cron', 'apps.api.routers.filmium_curator', 'apps.api.routers.filmium_import', 'apps.api.routers.filmium_library', 'apps.api.routers.filmium_library_date', 'apps.api.routers.filmium_localization', 'apps.api.routers.filmium_media_source', 'apps.api.routers.filmium_series', 'apps.api.routers.filmium_share', 'apps.api.routers.filmium_subtitles', 'apps.api.routers.filmium_torrents', 'apps.api.routers.filmium_wishlist', 'apps.api.routers.filmium_approvals', 'apps.api.routers.filmium_jobs', 'apps.api.routers.filmium_health', 'apps.api.routers.filmium_actors', 'apps.api.routers.voice')

# Ćelija NAMERNO nema CORS: GUI se servira sa istog origina, a CORE ćeliju
# zove iz svog Python servera (spec §8), ne iz browsera. Bez nepoznatih
# origina nijedna strana stranica ne sme da vozi ~90 nezaštićenih ruta za
# upis (kopiranje fajlova, torenti, brisanje, pokretanje VLC-a, persone).
ALLOWED_HOSTS = ["127.0.0.1", "localhost"]

app = FastAPI(title=MANIFEST.name, version=MANIFEST.domain_version)

# Provera `Host` zaglavlja zatvara DNS rebinding: stranica sa tuđeg domena
# koji se razreši na 127.0.0.1 i dalje šalje `Host: tudji.domen`, pa dobija 400.
app.add_middleware(TrustedHostMiddleware, allowed_hosts=ALLOWED_HOSTS)

cell_router.bind_manifest(MANIFEST)
app.include_router(cell_router.router)
app.include_router(cell_brain_router.router)

for module_name in API_ROUTERS:
    app.include_router(importlib.import_module(module_name).router)

GUI_DIST = CELL_ROOT / "gui" / "dist"
if (GUI_DIST / "index.html").is_file():
    # Poslednje, da GUI nikad ne zakloni API rutu.
    app.mount("/", StaticFiles(directory=GUI_DIST, html=True), name="gui")
