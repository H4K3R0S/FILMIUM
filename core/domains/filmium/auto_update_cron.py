# ==========          BULK CRON — JEZGRO          ==========
"""Pozadinski masovni auto-update: lista svih filmova/serija u fajl, pa
obrada jedan-po-jedan.

Stanje živi u ``data/filmium_auto_update/{queue,state}.json`` da bi posao
preživeo gašenje aplikacije. Menadžer funkcije (start/stop/status/resume)
zove API i ``core_lifespan``. Sam prolaz radi zaseban proces (scripts/
filmium_auto_update_cron.py) pozivajući ``process_next`` u petlji.
"""

import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from core.domains.filmium.auto_update_service import auto_update_item

_DEFAULT_BASE = (
    Path(__file__).resolve().parents[3] / "data" / "filmium_auto_update"
)


def _dir(base_dir=None) -> Path:
    directory = Path(base_dir) if base_dir else _DEFAULT_BASE
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ==========          QUEUE / STATE FAJLOVI          ==========

def read_queue(base_dir=None) -> list:
    try:
        raw = (_dir(base_dir) / "queue.json").read_text(encoding="utf-8")
        data = json.loads(raw)
        return data if isinstance(data, list) else []
    except (OSError, ValueError):
        return []


def write_queue(queue, base_dir=None) -> None:
    (_dir(base_dir) / "queue.json").write_text(
        json.dumps(queue, ensure_ascii=False, indent=1), encoding="utf-8"
    )


def read_state(base_dir=None) -> dict:
    try:
        raw = (_dir(base_dir) / "state.json").read_text(encoding="utf-8")
        data = json.loads(raw)
        return data if isinstance(data, dict) else {"status": "idle"}
    except (OSError, ValueError):
        return {"status": "idle"}


def write_state(state, base_dir=None) -> None:
    payload = {**state, "updated_at": _now()}
    (_dir(base_dir) / "state.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8"
    )


# ==========          QUEUE GRADNJA / KOMPLETNOST          ==========

def _entry(item) -> dict:
    kind = "series" if item.media_type.value == "series" else "movie"
    return {"id": item.id, "kind": kind, "title": item.title}


def build_queue(items) -> list:
    """Iz liste MediaItem pravi red obrade (filmovi + serije)."""

    return [_entry(item) for item in items]


def build_pending(items, processed_ids) -> list:
    """
    Red obrade: preskoči već obrađene, ALI uvek uključi nekompletne stavke
    (npr. starije koje još nemaju TMDB ID) da bi ih pozadinski posao dopunio.
    """

    done = set(processed_ids or ())
    return [
        _entry(item)
        for item in items
        if item.id not in done or not is_complete(item)
    ]


def is_complete(item) -> bool:
    """Stavka je kompletna ako ima originalni naslov, opis, ključne reči i
    TMDB ID. TMDB ID je uslov da bi lista „za preuzeti" mogla pouzdano da
    prepozna da je naslov ušao u biblioteku (i da se stariji naslovi dopune)."""

    return (
        bool(item.original_title)
        and bool(item.notes)
        and bool(item.keywords)
        and item.tmdb_id is not None
    )


# ==========          PID ŽIVOST (Windows-safe)          ==========

def pid_alive(pid) -> bool:
    """Da li proces sa datim PID-om još radi. Bezbedno na Windows-u."""

    if not pid:
        return False
    try:
        pid = int(pid)
    except (ValueError, TypeError):
        return False

    if os.name == "nt":
        import ctypes

        process_query = 0x1000  # PROCESS_QUERY_LIMITED_INFORMATION
        still_active = 259
        handle = ctypes.windll.kernel32.OpenProcess(process_query, False, pid)
        if not handle:
            return False
        code = ctypes.c_ulong()
        ok = ctypes.windll.kernel32.GetExitCodeProcess(
            handle, ctypes.byref(code)
        )
        ctypes.windll.kernel32.CloseHandle(handle)
        return bool(ok) and code.value == still_active

    try:
        os.kill(pid, 0)
    except (OSError, ProcessLookupError):
        return False
    return True


# ==========          OBRADA JEDNE STAVKE          ==========

def process_next(service, translator, *, runner=auto_update_item,
                 base_dir=None) -> bool:
    """Obradi stavku na kursoru, upiši stanje. Vrati True ako ima još."""

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
    except Exception as error:  # noqa: BLE001 — greška jedne stavke ne ruši posao
        state.setdefault("errors", []).append(
            {"id": entry["id"], "reason": str(error)}
        )
        state["error_count"] = state.get("error_count", 0) + 1

    # Zabeleži da je stavka obrađena (i pri grešci) da je sledeći skan preskoči.
    processed = state.setdefault("processed_ids", [])
    if entry["id"] not in processed:
        processed.append(entry["id"])

    cursor += 1
    state["cursor"] = cursor
    if cursor >= len(queue):
        state["status"] = "done"
        state["current"] = None
    write_state(state, base_dir)
    return cursor < len(queue)


# ==========          MENADŽER PROCESA          ==========

def _hidden_python() -> str:
    """pythonw.exe (bez konzole) pored trenutnog interpretera, ako postoji."""

    exe = Path(sys.executable)
    pythonw = exe.with_name("pythonw.exe")
    return str(pythonw) if pythonw.exists() else sys.executable


def spawn_process() -> None:
    """Pokreće zaseban cron proces u pozadini, BEZ vidljivog terminala."""

    script = (
        Path(__file__).resolve().parents[3]
        / "scripts"
        / "filmium_auto_update_cron.py"
    )

    flags = 0
    startupinfo = None
    if os.name == "nt":
        # CREATE_NO_WINDOW + SW_HIDE = nikakav prozor; pythonw dodatno bez konzole.
        flags = subprocess.CREATE_NO_WINDOW
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startupinfo.wShowWindow = subprocess.SW_HIDE

    subprocess.Popen(
        [_hidden_python(), str(script), "--resume"],
        creationflags=flags,
        startupinfo=startupinfo,
        close_fds=True,
    )


def resume_if_active(*, spawn=spawn_process, base_dir=None) -> bool:
    """Ako je posao „running" a proces mrtav, ponovo ga pokreni. Za startup."""

    state = read_state(base_dir)
    if state.get("status") == "running" and not pid_alive(state.get("pid")):
        spawn()
        return True
    return False


def status(base_dir=None) -> dict:
    return read_state(base_dir)


def stop(base_dir=None) -> dict:
    """Zaustavi posao i ubij proces ako radi."""

    state = read_state(base_dir)
    pid = state.get("pid")
    if pid_alive(pid):
        try:
            os.kill(int(pid), 9)
        except (OSError, ValueError, TypeError):
            pass
    write_state({**state, "status": "stopped", "current": None}, base_dir)
    return read_state(base_dir)


def start(service, *, spawn=spawn_process, base_dir=None) -> dict:
    """Napravi listu svih filmova/serija, snimi je i pokreni pozadinski posao."""

    state = read_state(base_dir)
    if state.get("status") == "running" and pid_alive(state.get("pid")):
        return state

    # Nastavi gde je stao: preskoči već obrađene, dodaj samo nove.
    processed = state.get("processed_ids", [])
    pending = build_pending(service.list_media_items(), processed)
    write_queue(pending, base_dir)
    write_state(
        {
            "status": "running",
            "pid": None,
            "total": len(pending),
            "cursor": 0,
            "current": None,
            "started_at": _now(),
            "done_count": 0,
            "error_count": 0,
            "errors": [],
            "processed_ids": processed,
        },
        base_dir,
    )
    spawn()
    return read_state(base_dir)
