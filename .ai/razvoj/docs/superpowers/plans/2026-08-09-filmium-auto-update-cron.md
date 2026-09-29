---
id: filmium-73042bb3-2026-08-09-filmium-auto-update-cron-md
type: plan
domain: filmium
namespace: global
visibility: global
tier: domain
title: FILMIUM Bulk Cron (/update-filmium) Implementation Plan
summary: '> **For agentic workers:** Use superpowers:executing-plans. Steps use checkbox
  (`- [ ]`) syntax.'
keywords:
- filmium
- bulk
- cron
- update
- implementation
- docs
- superpowers
- plans
tags:
- superpowers
- plans
source_path: docs/superpowers/plans/2026-08-09-filmium-auto-update-cron.md
---

# FILMIUM Bulk Cron (/update-filmium) Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Komanda `/update-filmium` iz glavnog searcha pokreće pozadinski proces koji napravi listu svih filmova i serija u fajl, pa ih „polako" jedan-po-jedan provuče kroz `auto_update_item`, preskačući već kompletne; preživljava gašenje (CORE na startu nastavi aktivan posao); status je vidljiv u donjem desnom uglu na CORE nivou.

**Architecture:** Zaseban Python proces (`scripts/filmium_auto_update_cron.py`) čita/piše stanje u `data/filmium_auto_update/{queue,state}.json`. Menadžer (`core/domains/filmium/auto_update_cron.py`) pokreće/gasi/čita proces i nudi `resume_if_active()` koji zove `core_lifespan`. API izlaže start/stop/status; frontend presreće komandu i prikazuje indikator.

**Tech Stack:** Python 3.14 (subprocess, json), FastAPI; React + TS, Vitest.

## Global Constraints

- Bez mreže u testovima: `auto_update_item` i spawn subprocesa se injektuju/monkeypatch-uju.
- Stanje je JSON u `data/filmium_auto_update/`.
- Obim: filmovi + serije (top-level). Epizode su follow-up (ne u ovom planu).
- Git nije init — commit koraci opcioni.
- Test: `.venv/Scripts/python.exe -m pytest tests/<fajl> -v`.

---

### Task 1: Jezgro cron-a — queue, state, process_next, resume

**Files:**
- Create: `core/domains/filmium/auto_update_cron.py`
- Test: `tests/test_filmium_auto_update_cron.py`

**Interfaces:**
- Produces:
  - `build_queue(items) -> list[dict]` — iz `MediaItem` liste pravi `[{"id","kind","title"}]` (kind = "movie"/"series").
  - `is_complete(item) -> bool` — True ako ima `original_title` i neprazan `notes` i `keywords`.
  - `read_state()/write_state(dict)`, `read_queue()/write_queue(list)` (putanje pod `data/filmium_auto_update/`, prima `base_dir` override radi testa).
  - `process_next(service, translator, *, runner=auto_update_item) -> bool` — obradi stavku na kursoru, upiši stanje, vrati True ako ima još.
  - `resume_if_active(*, spawn) -> bool` — ako je state `running` a PID mrtav, pozovi `spawn()` i vrati True.
  - `pid_alive(pid) -> bool`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_filmium_auto_update_cron.py
from core.domains.filmium import auto_update_cron as cron
from core.domains.filmium.models import MediaItem, MediaType, WatchStatus
from datetime import datetime


def _mi(id, title, media_type=MediaType.MOVIE, **kw):
    base = dict(id=id, title=title, media_type=media_type, original_title=None,
                release_year=None, watch_status=WatchStatus.PLANNED, rating=None,
                notes=None, created_at=datetime(2026, 1, 1),
                updated_at=datetime(2026, 1, 1))
    base.update(kw)
    return MediaItem(**base)


def test_build_queue_movies_and_series():
    items = [_mi(1, "A"), _mi(2, "B", media_type=MediaType.SERIES)]
    queue = cron.build_queue(items)
    assert queue == [
        {"id": 1, "kind": "movie", "title": "A"},
        {"id": 2, "kind": "series", "title": "B"},
    ]


def test_is_complete():
    full = _mi(1, "A", original_title="A", notes="opis", keywords=("x",))
    assert cron.is_complete(full) is True
    assert cron.is_complete(_mi(2, "B")) is False


def test_state_roundtrip(tmp_path):
    cron.write_state({"status": "running", "cursor": 3}, base_dir=tmp_path)
    assert cron.read_state(base_dir=tmp_path)["cursor"] == 3


def test_process_next_advances_cursor(tmp_path):
    calls = []

    class Svc:
        def get_media_item(self, i):
            return _mi(i, f"T{i}")

    def runner(item_id, service, translator, **kw):
        calls.append(item_id)
        class R:  # AutoUpdateResult-lik
            matched = True
            changed_fields = ()
            message = "ok"
        return R()

    cron.write_queue([{"id": 10, "kind": "movie", "title": "T10"},
                      {"id": 11, "kind": "movie", "title": "T11"}],
                     base_dir=tmp_path)
    cron.write_state({"status": "running", "cursor": 0, "total": 2,
                      "done_count": 0, "error_count": 0, "errors": []},
                     base_dir=tmp_path)

    more = cron.process_next(Svc(), object(), runner=runner, base_dir=tmp_path)
    assert more is True
    assert calls == [10]
    assert cron.read_state(base_dir=tmp_path)["cursor"] == 1

    cron.process_next(Svc(), object(), runner=runner, base_dir=tmp_path)
    more = cron.process_next(Svc(), object(), runner=runner, base_dir=tmp_path)
    assert more is False
    assert cron.read_state(base_dir=tmp_path)["status"] == "done"


def test_resume_if_active_dead_pid(tmp_path, monkeypatch):
    spawned = []
    cron.write_state({"status": "running", "pid": 999999}, base_dir=tmp_path)
    monkeypatch.setattr(cron, "pid_alive", lambda _pid: False)
    out = cron.resume_if_active(spawn=lambda: spawned.append(True),
                                base_dir=tmp_path)
    assert out is True
    assert spawned == [True]


def test_resume_if_active_idle(tmp_path):
    cron.write_state({"status": "idle"}, base_dir=tmp_path)
    assert cron.resume_if_active(spawn=lambda: None, base_dir=tmp_path) is False
```

- [ ] **Step 2: Run — expect fail** (`ModuleNotFoundError`).
- [ ] **Step 3: Implement `auto_update_cron.py`** (vidi kod ispod, u sekciji Implementacija).
- [ ] **Step 4: Run — expect pass.**
- [ ] **Step 5: Commit.**

---

### Task 2: CLI skripta

**Files:**
- Create: `scripts/filmium_auto_update_cron.py`
- Test: ručna provera (integracioni; bez unit testa mreže).

CLI: `--build` (napravi queue iz `service.list_media_items()` + reset state na `running`), `--run`/`--resume` (petlja `process_next` + `sleep(delay)`), `--delay` (default 3.0). Servis: `from apps.api.dependencies import get_filmium_service`; prevodilac: `TranslatorService()`. Upisuje PID u state na startu.

- [ ] Napisati skriptu; ručno pokrenuti `--build` pa `--run` na malom uzorku (ili sa velikim delay-em i odmah `--stop` preko API-ja).

---

### Task 3: Menadžer spawn + API + resume na startu

**Files:**
- Modify: `core/domains/filmium/auto_update_cron.py` (dodaj `start/stop/status/spawn_process`).
- Create: `apps/api/routers/filmium_cron.py`
- Modify: `apps/api/main.py` (register router + `resume_if_active` u lifespan)
- Test: `tests/test_api_filmium_cron.py`

Endpoints: `POST /api/v1/filmium/auto-update/start`, `POST .../stop`, `GET .../status`.

- [ ] Test: `GET status` vraća `idle` kad nema fajla; `POST start` (sa monkeypatch-ovanim `spawn_process`) postavi `running`.
- [ ] Implementiraj, veži u main lifespan.

---

### Task 4: Frontend — slash komanda + CORE indikator

**Files:**
- Create: `apps/gui/src/services/filmiumCronApi.ts`
- Modify: `apps/gui/src/features/filmium/components/layout/FilmiumTopBar.tsx` (presretni `/update-filmium`, `/update-filmium stop`)
- Create: `apps/gui/src/components/system/CronStatusIndicator.tsx` + CSS
- Modify: `apps/gui/src/components/layout/AppShell.tsx` (montiraj indikator)
- Test: `filmiumCronApi` poziv + `CronStatusIndicator` render (idle skriven / running vidljiv), po uzoru na postojeće testove.

- [ ] Testovi + implementacija; indikator polling `GET status` ~3s, fiksiran donji desni ugao, sakriven kad `idle/done`.

---

## Implementacija — `auto_update_cron.py` (referentni kod)

```python
# core/domains/filmium/auto_update_cron.py
import json, os, sys, subprocess
from datetime import datetime, timezone
from pathlib import Path

from core.domains.filmium.auto_update_service import auto_update_item

_DEFAULT_BASE = Path(__file__).resolve().parents[3] / "data" / "filmium_auto_update"


def _dir(base_dir=None) -> Path:
    d = Path(base_dir) if base_dir else _DEFAULT_BASE
    d.mkdir(parents=True, exist_ok=True)
    return d


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def read_queue(base_dir=None):
    path = _dir(base_dir) / "queue.json"
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []


def write_queue(queue, base_dir=None):
    (_dir(base_dir) / "queue.json").write_text(
        json.dumps(queue, ensure_ascii=False, indent=1), encoding="utf-8")


def read_state(base_dir=None):
    path = _dir(base_dir) / "state.json"
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"status": "idle"}


def write_state(state, base_dir=None):
    state = {**state, "updated_at": _now()}
    (_dir(base_dir) / "state.json").write_text(
        json.dumps(state, ensure_ascii=False, indent=1), encoding="utf-8")


def build_queue(items):
    out = []
    for item in items:
        kind = "series" if item.media_type.value == "series" else "movie"
        out.append({"id": item.id, "kind": kind, "title": item.title})
    return out


def is_complete(item) -> bool:
    return bool(item.original_title) and bool(item.notes) and bool(item.keywords)


def pid_alive(pid) -> bool:
    if not pid:
        return False
    try:
        os.kill(int(pid), 0)
    except (OSError, ValueError, TypeError):
        return False
    return True


def process_next(service, translator, *, runner=auto_update_item, base_dir=None):
    queue = read_queue(base_dir)
    state = read_state(base_dir)
    cursor = state.get("cursor", 0)

    if cursor >= len(queue):
        write_state({**state, "status": "done", "current": None}, base_dir)
        return False

    entry = queue[cursor]
    state = {**state, "current": entry}
    try:
        item = service.get_media_item(entry["id"])
        if not is_complete(item):
            runner(entry["id"], service, translator)
        state["done_count"] = state.get("done_count", 0) + 1
    except Exception as error:  # noqa: BLE001 — pojedinačna greška ne ruši posao
        state.setdefault("errors", []).append(
            {"id": entry["id"], "reason": str(error)})
        state["error_count"] = state.get("error_count", 0) + 1

    cursor += 1
    state["cursor"] = cursor
    if cursor >= len(queue):
        state["status"] = "done"
        state["current"] = None
    write_state(state, base_dir)
    return cursor < len(queue)


def spawn_process():
    script = Path(__file__).resolve().parents[3] / "scripts" \
        / "filmium_auto_update_cron.py"
    flags = 0
    if os.name == "nt":
        flags = subprocess.CREATE_NO_WINDOW | subprocess.DETACHED_PROCESS
    subprocess.Popen([sys.executable, str(script), "--resume"],
                     creationflags=flags, close_fds=True)


def resume_if_active(*, spawn=spawn_process, base_dir=None) -> bool:
    state = read_state(base_dir)
    if state.get("status") == "running" and not pid_alive(state.get("pid")):
        spawn()
        return True
    return False


def status(base_dir=None):
    return read_state(base_dir)


def stop(base_dir=None):
    state = read_state(base_dir)
    pid = state.get("pid")
    if pid_alive(pid):
        try:
            os.kill(int(pid), 9)
        except (OSError, ValueError, TypeError):
            pass
    write_state({**state, "status": "stopped"}, base_dir)


def start(service, *, spawn=spawn_process, base_dir=None):
    state = read_state(base_dir)
    if state.get("status") == "running" and pid_alive(state.get("pid")):
        return state
    queue = build_queue(service.list_media_items())
    write_queue(queue, base_dir)
    write_state({"status": "running", "pid": None, "total": len(queue),
                 "cursor": 0, "current": None, "started_at": _now(),
                 "done_count": 0, "error_count": 0, "errors": []}, base_dir)
    spawn()
    return read_state(base_dir)
```

Napomena: `os.kill(pid, 0)` na Windows-u za tuđ PID može baciti `PermissionError`
(znači „živ je"). Ako testovi pokažu problem, u `pid_alive` tretiraj
`PermissionError` kao „živ" (`return True`).
