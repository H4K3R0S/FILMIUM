# ========== TESTOVI: razrešavanje naslov -> media_id ==========
from __future__ import annotations

from dataclasses import dataclass

from core.domains.filmium.curator.media_resolver import MediaResolver


@dataclass
class _Item:
    id: int
    title: str
    english_title: str | None = None


def _resolver(*items: _Item) -> MediaResolver:
    return MediaResolver(lambda: list(items))


def test_tacan_naslov_daje_id():
    r = _resolver(_Item(1, "Matriks"), _Item(2, "Incepcija"))
    assert r.resolve("Matriks") == 1


def test_delimicno_poklapanje_daje_najblizi():
    r = _resolver(_Item(1, "Gospodar prstenova: Druzina prstena"), _Item(2, "Matriks"))
    assert r.resolve("gospodar prstenova druzina") == 1


def test_poklapanje_na_engleski_naslov():
    r = _resolver(_Item(1, "Ledeno doba", english_title="Ice Age"), _Item(2, "Matriks"))
    assert r.resolve("ice age") == 1


def test_bez_poklapanja_je_none():
    r = _resolver(_Item(1, "Matriks"), _Item(2, "Incepcija"))
    assert r.resolve("nepostojeci film xyz") is None


def test_prazan_upit_je_none():
    r = _resolver(_Item(1, "Matriks"))
    assert r.resolve("") is None
    assert r.resolve("   ") is None


def test_dvosmislenost_isti_skor_je_none():
    # Dva naslova jednako pogađaju upit -> ne pogađaj nasumično kod upisa.
    r = _resolver(_Item(1, "Rat"), _Item(2, "Rat"))
    assert r.resolve("Rat") is None


def test_dijakritika_se_ignorise():
    r = _resolver(_Item(1, "Žveglja"), _Item(2, "Matriks"))
    assert r.resolve("zveglja") == 1


def test_tacan_naslov_pobedi_delimicne_iste_reci():
    # „Moana" (tačan naslov) pobeđuje „Vajana"/eng „Moana" i „Vajana 2"/eng
    # „Moana 2" — ranije su sva tri skorovala 1 na „moana" → None (bug).
    r = _resolver(
        _Item(1935, "Moana", english_title="Moana"),
        _Item(1689, "Vajana 2", english_title="Moana 2"),
        _Item(1688, "Vajana", english_title="Moana"),
    )
    assert r.resolve("moana") == 1935


def test_broj_u_naslovu_razlikuje_nastavak():
    r = _resolver(
        _Item(1935, "Moana", english_title="Moana"),
        _Item(1689, "Vajana 2", english_title="Moana 2"),
    )
    assert r.resolve("moana 2") == 1689


def test_candidates_vraca_sve_jednake_pogotke():
    # „hunger games" jednako pogađa sve delove → grupa za filtriran prikaz.
    r = _resolver(
        _Item(1, "The Hunger Games 1"),
        _Item(2, "The Hunger Games 2"),
        _Item(3, "Matriks"),
    )
    assert sorted(r.candidates("hunger games")) == [1, 2]


def test_candidates_jedan_jasan_pogodak():
    r = _resolver(_Item(1, "Matriks"), _Item(2, "Incepcija"))
    assert r.candidates("matriks") == [1]


def test_candidates_bez_poklapanja_prazno():
    r = _resolver(_Item(1, "Matriks"))
    assert r.candidates("nepostojece xyz") == []
