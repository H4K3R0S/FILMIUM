"""Transliteracija prevoda (latinica ↔ ćirilica), SRT-svesno + kreiranje fajla."""
from __future__ import annotations

from pathlib import Path

from core.domains.filmium.subtitle_transliterate import transliterate_subtitle_file
from core.domains.filmium.transliteration import (
    detect_script,
    latin_to_cyrillic,
    transliterate_srt,
)

_LATN = (
    "1\n00:00:01,284 --> 00:00:03,284\n"
    "<font color=#FFD2D2><b>Njuškalo će njuškati.</b></font>\n\n"
    "2\n00:00:05,000 --> 00:00:07,000\n<i>Ljubav i džak.</i>\n"
)


def test_detect_and_digraphs():
    assert detect_script("Njuškalo") == "latin"
    assert detect_script("Њушкало") == "cyrillic"
    assert latin_to_cyrillic("Ljubav Njegov džak") == "Љубав Његов џак"
    assert latin_to_cyrillic("LJUBAV") == "ЉУБАВ"


def test_srt_aware_keeps_tags_and_structure():
    cyr = transliterate_srt(_LATN, to_cyrillic=True)
    # HTML tagovi i atributi netaknuti
    assert "<font color=#FFD2D2>" in cyr
    assert "<b>" in cyr and "<i>" in cyr
    # indeks/timecode netaknuti
    assert "00:00:01,284 --> 00:00:03,284" in cyr
    # dijalog transliterisan
    assert "Њушкало ће њушкати." in cyr
    assert "Љубав и џак." in cyr
    # povratno u latinicu vraća originalni dijalog
    back = transliterate_srt(cyr, to_cyrillic=False)
    assert "Njuškalo će njuškati." in back


def test_file_creates_other_script(tmp_path):
    src = tmp_path / "E01 - Nešto.sr-Latn.srt"
    src.write_text(_LATN, encoding="utf-8")
    result = transliterate_subtitle_file(src)
    assert result["from_script"] == "latin"
    assert result["to_script"] == "cyrillic"
    target = Path(result["created"])
    assert target.name == "E01 - Nešto.sr-Cyrl.srt"
    assert target.exists()
    assert "Њушкало" in target.read_text(encoding="utf-8")


def test_file_cyrillic_to_latin(tmp_path):
    src = tmp_path / "film.sr-Cyrl.srt"
    src.write_text(
        "1\n00:00:01,000 --> 00:00:02,000\n<i>Њушкало</i>\n", encoding="utf-8"
    )
    result = transliterate_subtitle_file(src)
    assert result["to_script"] == "latin"
    assert Path(result["created"]).name == "film.sr-Latn.srt"
    assert "Njuškalo" in Path(result["created"]).read_text(encoding="utf-8")
