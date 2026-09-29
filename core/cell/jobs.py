# ==========          JOBS/CRON SLOJ          ==========
# Cron i skripte kao PRVORAZREDNE funkcije domena — v.
# UNAPREDJENJE/01-ARHITEKTURA/08-cron-i-skripte-sloj.md.
#
# Model: svaki posao je potklasa `Job` (id, opis, `run(ctx)`). `JobRegistry`
# drzi registrovane poslove i njihovo runtime stanje (idle/running/done/
# stopped/error + poslednji run, trajanje, progres). Pokretanje ide u
# zasebnoj niti (thread) sa kooperativnim `stop` (posao sam proverava
# `ctx.should_stop()` u petlji — ovaj sloj ne ubija niti na silu, Python to
# ni ne dozvoljava bezbedno).
#
# VAZNO (brzina boot-a): OVAJ MODUL NE POKRECE NISTA PRI UVOZU. Registracija
# posla (`JobRegistry.register`) samo pravi lagane objekte (Lock/Event) —
# NEMA `Thread.start()`, NEMA mrezhnog poziva, NEMA always-on petlje. Poslovi
# se pokrecu EKSKLUZIVNO na zahtev: `run-once` (sinhrono, blokira pozivaoca
# dok posao ne zavrsi — za brze poslove kao `atom_reindex`) ili `start`
# (asinhrono, u pozadinskoj niti — za duge poslove). Spoljni raspored
# (systemd `--user` timer) samo zove `run-once`/`start` preko HTTP-a; ne
# postoji ugradjeni scheduler ovde (isti duh kao "lenji importi runtime-a").
#
# Best-effort SSE emit ka Second Brain (`POST http://127.0.0.1:4901/api/events`)
# — isti ugovor kao `core/cell/executor.py::_http_emit` (kratak timeout,
# NIKAD ne puca i nikad ne blokira posao ako Second Brain ne radi).
#
# Ovaj fajl je DELJEN — identican u sva 4 domena (core/cell/ konvencija, isto
# kao core/cell/database.py i core/cell/executor.py). Domenska razlika je
# ISKLJUCIVO koji `Job`-ovi se registruju (core/domains/<d>/jobs/registry.py),
# ne ovaj kod.
from __future__ import annotations

import json
import os
import threading
import time
import traceback
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone

# ----------          STATUSI          ----------
STATUS_IDLE = "idle"
STATUS_RUNNING = "running"
STATUS_DONE = "done"
STATUS_STOPPED = "stopped"
STATUS_ERROR = "error"

# Referenca za `uptime_s` u health endpoint-u — postavljena pri PRVOM uvozu
# ovog modula (rano u boot lancu, preko `core/domains/<d>/jobs/registry.py`),
# sto je dovoljno blisko stvarnom pocetku procesa za dijagnostiku.
PROCESS_STARTED_AT = time.time()


def _iso(ts: float | None) -> str | None:
    if ts is None:
        return None
    return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()


def _http_emit(event: dict) -> None:
    """Best-effort SSE emit ka Second Brain (isti ugovor kao
    `core/cell/executor.py::_http_emit`). Nikad ne puca i nikad ne blokira
    posao — kratak timeout (0.3s) da odsustvo Second Brain-a (npr. u
    testovima ili kad GUI ne radi) ne uspori nista primetno."""

    url = os.environ.get(
        "SECOND_BRAIN_EVENTS_URL", "http://127.0.0.1:4901/api/events"
    )
    try:
        data = json.dumps(event, ensure_ascii=False, default=str).encode("utf-8")
        request = urllib.request.Request(
            url, data=data, headers={"content-type": "application/json"},
            method="POST",
        )
        urllib.request.urlopen(request, timeout=0.3).close()
    except Exception:  # noqa: BLE001, S110
        pass


# ----------          KONTEKST PROSLEDJEN U run(ctx)          ----------

class JobContext:
    """Prosledjuje se u `Job.run(ctx)`. Nosi kooperativni stop signal i
    callback za prijavu progresa (koji best-effort emituje SSE dogadjaj)."""

    def __init__(
        self,
        job_id: str,
        domain: str,
        stop_event: threading.Event,
        emit: Callable[[dict], None],
    ) -> None:
        self.job_id = job_id
        self.domain = domain
        self._stop_event = stop_event
        self._emit = emit

    def should_stop(self) -> bool:
        """Posao koji radi u petlji treba periodicno da proverava ovo i da
        se sam prekine (kooperativni stop — ova ćelija ne ubija niti)."""

        return self._stop_event.is_set()

    def progress(self, done: int, total: int | None = None, message: str = "") -> None:
        """Prijavi napredak. Best-effort SSE emit ka Second Brain; nikad
        ne puca ako posao pozove ovo van glavne niti ili Second Brain ne
        radi."""

        try:
            self._emit({
                "type": "job_progress",
                "domain": self.domain,
                "job_id": self.job_id,
                "done": done,
                "total": total,
                "message": message,
            })
        except Exception:  # noqa: BLE001, S110
            pass


# ----------          STANJE POSLA          ----------

@dataclass
class JobState:
    status: str = STATUS_IDLE
    started_at: float | None = None
    finished_at: float | None = None
    duration_s: float | None = None
    progress_done: int = 0
    progress_total: int | None = None
    progress_message: str = ""
    result: object = None
    error: str | None = None

    def to_dict(self) -> dict:
        return {
            "status": self.status,
            "started_at": _iso(self.started_at),
            "finished_at": _iso(self.finished_at),
            "duration_s": self.duration_s,
            "progress": {
                "done": self.progress_done,
                "total": self.progress_total,
                "message": self.progress_message,
            },
            "result": self.result,
            "error": self.error,
        }


# ----------          BAZNA KLASA POSLA          ----------

class Job:
    """Bazna klasa jednog posla. Potklase implementiraju `run(ctx)`.

    `id` mora biti jedinstven u registru domena. `opis`/`raspored` su
    informativni (prikazuju se u `GET /jobs`).
    """

    id: str = ""
    opis: str = ""
    raspored: str = "on-demand"

    def run(self, ctx: JobContext) -> dict | None:
        raise NotImplementedError

    def live_status(self) -> dict | None:
        """Opciono: posao koji DELEGIRA na spoljno stanje/proces (npr.
        FILMIUM `auto_update_cron`, koji zivi kao zaseban subprocess sa
        sopstvenim `state.json`-om) moze ovde da vrati SVOJE stvarno stanje
        — ti kljucevi PREGAZE generic stanje wrappera niti u prikazu.
        Podrazumevano `None` (koristi se generic stanje)."""

        return None

    def live_stop(self) -> dict | None:
        """Opciono: posao sa spoljnim procesom treba SAM da ga zaustavi
        (npr. ubije subprocess). Vraca stanje posle zaustavljanja, ili
        `None` da handle uradi generic (kooperativni) `stop`."""

        return None


# ----------          RUNTIME OMOTAC (NIT + STANJE)          ----------

class _JobHandle:
    """Runtime omotac oko `Job`: stanje + nit + stop event. Nije namenjen
    direktnoj upotrebi van `JobRegistry`."""

    def __init__(self, job: Job, *, domain: str, emit: Callable[[dict], None]) -> None:
        self.job = job
        self.domain = domain
        self.emit = emit
        self.state = JobState()
        self.lock = threading.Lock()
        self.thread: threading.Thread | None = None
        self.stop_event = threading.Event()

    def is_running(self) -> bool:
        return self.thread is not None and self.thread.is_alive()

    def _run_body(self) -> None:
        ctx = JobContext(self.job.id, self.domain, self.stop_event, self.emit)
        try:
            result = self.job.run(ctx)
            with self.lock:
                if self.stop_event.is_set():
                    self.state.status = STATUS_STOPPED
                else:
                    self.state.status = STATUS_DONE
                    self.state.result = result
        except Exception as error:  # noqa: BLE001 — posao koji padne ne sme da obori celiju
            with self.lock:
                self.state.status = STATUS_ERROR
                self.state.error = f"{error}\n{traceback.format_exc()[-2000:]}"
        finally:
            finished = time.time()
            with self.lock:
                self.state.finished_at = finished
                if self.state.started_at is not None:
                    self.state.duration_s = finished - self.state.started_at
            try:
                self.emit({
                    "type": "job_done",
                    "domain": self.domain,
                    "job_id": self.job.id,
                    "status": self.state.status,
                })
            except Exception:  # noqa: BLE001, S110
                pass

    def _display_state(self) -> dict:
        """Generic stanje spojeno sa `job.live_status()` (ako posao to
        implementira) — koristi ga i `status()` i svaki poziv koji vraca
        stanje posle akcije (`start`/`run_once`)."""

        live: dict | None = None
        try:
            live = self.job.live_status()
        except Exception:  # noqa: BLE001 — live status nikad ne sme da puca
            live = None
        with self.lock:
            base = self.state.to_dict()
        if live:
            return {**base, **live}
        return base

    def start(self) -> dict:
        with self.lock:
            if self.is_running():
                return self._display_state()
            self.stop_event = threading.Event()
            self.state = JobState(status=STATUS_RUNNING, started_at=time.time())
            self.thread = threading.Thread(
                target=self._run_body, name=f"job-{self.job.id}", daemon=True,
            )
            thread = self.thread
        try:
            self.emit({"type": "job_start", "domain": self.domain, "job_id": self.job.id})
        except Exception:  # noqa: BLE001, S110
            pass
        thread.start()
        return self._display_state()

    def run_once_sync(self) -> dict:
        """Pokrece posao SINHRONO (blokira pozivaoca dok posao ne zavrsi) —
        za `run-once` kad pozivalac zeli konacan rezultat odmah (npr. test,
        mali posao poput `atom_reindex`)."""

        with self.lock:
            if self.is_running():
                return self._display_state()
            self.stop_event = threading.Event()
            self.state = JobState(status=STATUS_RUNNING, started_at=time.time())
        try:
            self.emit({"type": "job_start", "domain": self.domain, "job_id": self.job.id})
        except Exception:  # noqa: BLE001, S110
            pass
        self._run_body()
        return self._display_state()

    def stop(self) -> dict:
        try:
            live = self.job.live_stop()
        except Exception:  # noqa: BLE001
            live = None
        if live is not None:
            return live

        with self.lock:
            self.stop_event.set()
            running = self.is_running()
            if not running and self.state.status == STATUS_RUNNING:
                self.state.status = STATUS_STOPPED
            thread = self.thread
        if running and thread is not None:
            # Kratko sacekaj da nit primeti signal (kooperativno — ne
            # blokira dugo; posao koji ne proverava `should_stop()` ostaje
            # `running` dok sam ne zavrsi, sto je ocekivano ponasanje).
            thread.join(timeout=2.0)
        with self.lock:
            if self.state.status == STATUS_RUNNING and not self.is_running():
                self.state.status = STATUS_STOPPED
        return self._display_state()

    def status(self) -> dict:
        return self._display_state()


# ----------          REGISTAR POSLOVA DOMENA          ----------

class JobRegistry:
    """Registar poslova jednog domena. Pravi se PO CELIJI (modulski
    singleton u `core/domains/<d>/jobs/registry.py`), ali NE pokrece nista
    sam pri pravljenju/registraciji — samo drzi definicije + stanje."""

    def __init__(self, *, domain: str, emit: Callable[[dict], None] | None = None) -> None:
        self._domain = domain
        self._emit = emit or _http_emit
        self._handles: dict[str, _JobHandle] = {}

    def register(self, job: Job) -> None:
        if not job.id:
            raise ValueError("Job.id je obavezan")
        self._handles[job.id] = _JobHandle(job, domain=self._domain, emit=self._emit)

    def list(self) -> list[dict]:
        out: list[dict] = []
        for handle in self._handles.values():
            state = handle.status()
            out.append({
                "id": handle.job.id,
                "opis": handle.job.opis,
                "raspored": handle.job.raspored,
                "status": state["status"],
                "poslednji_run": state["finished_at"],
            })
        return out

    def get(self, job_id: str) -> _JobHandle | None:
        return self._handles.get(job_id)

    def status(self, job_id: str) -> dict | None:
        handle = self.get(job_id)
        return handle.status() if handle else None

    def start(self, job_id: str) -> dict | None:
        handle = self.get(job_id)
        return handle.start() if handle else None

    def run_once(self, job_id: str) -> dict | None:
        handle = self.get(job_id)
        return handle.run_once_sync() if handle else None

    def stop(self, job_id: str) -> dict | None:
        handle = self.get(job_id)
        return handle.stop() if handle else None

    def __len__(self) -> int:
        return len(self._handles)
