"""Posao subtitle_script_pair: pravi drugo pismo, preskače postojeće i ne-srpske."""
from __future__ import annotations

import threading

from core.cell.jobs import JobContext
from core.domains.filmium.jobs import subtitle_script_pair as mod
from core.domains.filmium.subtitle_transliterate import is_serbian_subtitle

_LATN = "1\n00:00:01,000 --> 00:00:02,000\n<i>Njuškalo će njuškati.</i>\n"


def test_serbian_filter():
    assert is_serbian_subtitle("Film.sr-Latn.srt")
    assert is_serbian_subtitle("Film.sr.srt")
    assert is_serbian_subtitle("Film.srp.srt")
    assert not is_serbian_subtitle("Film.en.srt")
    assert not is_serbian_subtitle("Film.hr.srt")


def _ctx() -> JobContext:
    return JobContext("subtitle_script_pair", "filmium", threading.Event(), lambda e: None)


def test_job_creates_missing_pairs(tmp_path, monkeypatch):
    latn = tmp_path / "Film.sr-Latn.srt"
    latn.write_text(_LATN, encoding="utf-8")
    paired = tmp_path / "Drugi.sr-Latn.srt"
    paired.write_text(_LATN, encoding="utf-8")
    (tmp_path / "Drugi.sr-Cyrl.srt").write_text("x", encoding="utf-8")  # par već postoji

    monkeypatch.setattr(mod, "_subtitle_paths", lambda: [latn, paired])
    result = mod.SubtitleScriptPairJob().run(_ctx())

    assert result["created"] == 1        # samo Film (Drugi već ima par)
    assert result["skipped"] == 1
    cyr = tmp_path / "Film.sr-Cyrl.srt"
    assert cyr.exists()
    assert "Њушкало" in cyr.read_text(encoding="utf-8")


def test_job_idempotent(tmp_path, monkeypatch):
    latn = tmp_path / "Film.sr-Latn.srt"
    latn.write_text(_LATN, encoding="utf-8")
    monkeypatch.setattr(mod, "_subtitle_paths", lambda: [latn])
    job = mod.SubtitleScriptPairJob()
    job.run(_ctx())
    second = job.run(_ctx())
    assert second["created"] == 0 and second["skipped"] == 1
