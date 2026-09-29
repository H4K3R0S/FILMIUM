from __future__ import annotations

from pathlib import Path

from core.domains.filmium.curator.interaction_log import InteractionLog


def _log(tmp_path: Path, clock: dict) -> InteractionLog:
    return InteractionLog(tmp_path, silence_seconds=180.0, now=lambda: clock["t"])


def test_record_pravi_pending_unos(tmp_path):
    clock = {"t": 100.0}
    log = _log(tmp_path, clock)
    log_id = log.record("pusti Matriks", "play", {"media_id": 5}, "plejer", "Puštam.")
    entries = log.entries()
    assert len(entries) == 1
    assert entries[0]["log_id"] == log_id
    assert entries[0]["status"] == "pending"
    assert entries[0]["heard"] == "pusti Matriks"


def test_refute_oznaci_poslednji_pending_kao_wrong(tmp_path):
    clock = {"t": 100.0}
    log = _log(tmp_path, clock)
    log.record("izmeni ocenu", "edit_metadata", {"media_id": 1}, "izmena-info", "Ok.")
    assert log.refute() is True
    assert log.entries()[-1]["status"] == "wrong"
    assert log.entries()[-1]["resolved_by"] == "user"


def test_settle_silent_prebaci_stare_pending_u_correct(tmp_path):
    clock = {"t": 100.0}
    log = _log(tmp_path, clock)
    log.record("nadji komedije", "search", {}, "pretraga", "Evo.")
    clock["t"] = 100.0 + 181.0
    assert log.settle_silent() == 1
    assert log.entries()[-1]["status"] == "correct"
    assert log.entries()[-1]["resolved_by"] == "silence"


def test_settle_silent_ne_dira_svez_pending(tmp_path):
    clock = {"t": 100.0}
    log = _log(tmp_path, clock)
    log.record("nadji komedije", "search", {}, "pretraga", "Evo.")
    clock["t"] = 100.0 + 10.0
    assert log.settle_silent() == 0
    assert log.entries()[-1]["status"] == "pending"
