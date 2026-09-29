"""Regresija: cp1250 .srt sa `<font color=#...><b>` tagovima (npr. WandaVision E09).

Terminator ISPRAVNO javlja `invalid_encoding` (fajl je stvarno Windows-1250: bajt 0x9e = ž),
a reparacija SME samo da re-enkoduje u UTF-8 — bez uklanjanja ijednog cue-a i uz očuvane
`<font>`/`<b>` tagove (nikakvo lažno credit/bracket/watermark brisanje).
"""
from __future__ import annotations

import re

from core.domains.filmium.subtitle_inspector_service import SubtitleInspectorService

# Ispravno dekodiran sadržaj (kakav vidi korisnik). U fajlu je cp1250.
_SRT = """1
00:00:01,284 --> 00:00:03,284
<font color=#D20000><b>Ranije u VandaVižnu...</b></font>

2
00:00:05,890 --> 00:00:08,055
<font color=#FFD2D2><b>Njuškalo će njuškati. </b></font>

3
00:00:08,180 --> 00:00:10,537
<font color=#FFD2D2><b>Gde su mi deca?</b></font>

4
00:00:12,782 --> 00:00:19,147
<font color=#FFD2D2><b>Ovo su rune. Samo veštica koja je
dočarala rune može koristiti magiju.</b></font>

5
00:00:20,317 --> 00:00:25,575
<font color=#FFD2D2><b>Vižn je bio mrtav,
ali ti si ga želela natrag.</b></font>
"""


def _blocks(text: str) -> list[str]:
    return [b for b in re.split(r"\r?\n[ \t]*\r?\n", text) if b.strip()]


def _prepare():
    content = _SRT.encode("cp1250")  # fajl na disku je Windows-1250
    svc = SubtitleInspectorService()
    inspection = svc.inspect(content, "E09 - The Series Finale.sr-Latn.srt")
    preview = svc.create_repair_preview(inspection)
    return inspection, preview


def test_cp1250_flagged_as_encoding():
    inspection, _ = _prepare()
    assert inspection.needs_repair is True
    assert "1250" in inspection.detected_encoding
    kinds = {i.issue_type.value for i in inspection.issues}
    # Samo kodiranje — NE credit/bracket/watermark (font tagovi nisu smeće).
    assert "invalid_encoding" in kinds
    assert {"credit_line", "bracket_cue", "progressive_watermark"} & kinds == set()


def test_repair_preserves_all_blocks_and_font_tags():
    inspection, preview = _prepare()
    before = _blocks(inspection.decoded_text)
    after = _blocks(preview.repaired_text)
    # Nijedan cue se ne sme izgubiti.
    assert len(after) == len(before) == 5
    # `<font>`/`<b>` tagovi očuvani, tekst čitljiv (UTF-8).
    assert "<font color=#FFD2D2>" in preview.repaired_text
    assert "<b>" in preview.repaired_text
    assert "Njuškalo će njuškati." in preview.repaired_text
    assert "VandaVižnu" in preview.repaired_text
    # repaired_text je validan UTF-8 (bez zamenskih znakova).
    assert "�" not in preview.repaired_text
