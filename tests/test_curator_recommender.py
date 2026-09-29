# tests/test_curator_recommender.py
# ========== TEST: Recommender — taste (favoriti/istorija) → kandidati → AI curira ==========
from types import SimpleNamespace

from core.domains.filmium.curator.recommender import Recommender


def _film(fid, title, genres=(), *, fav=False, watched=False, director="", mt="movie", year=2020):
    return SimpleNamespace(
        id=fid, title=title, genres=tuple(genres), is_favorite=fav,
        watch_status="completed" if watched else "planned",
        director=director, media_type=SimpleNamespace(value=mt), release_year=year,
    )


# Biblioteka: 1 favorit (SF), 1 odgledan (SF), + kandidati raznih žanrova.
def _lib():
    return [
        _film(1, "Blade Runner", ["SF"], fav=True),
        _film(2, "Matrix", ["SF"], watched=True),
        _film(3, "Dune", ["SF"], year=2021),            # SF, nije gledan → jak kandidat
        _film(4, "Arrival", ["SF", "Drama"], year=2016),  # SF → kandidat
        _film(5, "Notebook", ["Romansa"], year=2004),     # van ukusa → slab
        _film(6, "Interstellar", ["SF"], year=2014),      # SF → kandidat
    ]


def test_bez_curate_vrati_top_po_ukusu_bez_gledanih():
    rec = Recommender(_lib)
    ids = rec.recommend(limit=3)
    # Favorit(1) i odgledan(2) su ISKLJUČENI; SF naslovi (ukus) su ispred Romanse.
    assert 1 not in ids and 2 not in ids
    assert set(ids) <= {3, 4, 6}          # samo SF kandidati u top-3
    assert 5 not in ids                    # Romansa (van ukusa) nije u top-3
    assert len(ids) == 3


def test_zanr_filter_suzi_kandidate():
    rec = Recommender(_lib)
    ids = rec.recommend(genre="Romansa", limit=5)
    assert ids == [5]                      # samo Romansa kandidat


def test_media_type_filter():
    lib = [_film(10, "Serija A", ["SF"], mt="series", year=2022),
           _film(11, "Film A", ["SF"], mt="movie", year=2022)]
    rec = Recommender(lambda: lib)
    assert rec.recommend(media_type="series", limit=5) == [10]


def test_curate_bira_podskup_iz_poola():
    # curate dobije pool (kandidati) i vrati svoj izbor id-jeva; Recommender ga poštuje.
    seen = {}

    def curate(pool, req):
        seen["pool_ids"] = [m.id for m in pool]
        seen["req"] = req
        return [4, 6]  # AI bira baš ova dva

    rec = Recommender(_lib, curate=curate)
    ids = rec.recommend(limit=20, mood="mračno")
    assert ids == [4, 6]
    assert 1 not in seen["pool_ids"] and 2 not in seen["pool_ids"]  # gledani nisu u poolu
    assert seen["req"]["mood"] == "mračno"


def test_curate_vrati_prazno_fallback_na_skor():
    rec = Recommender(_lib, curate=lambda pool, req: [])
    ids = rec.recommend(limit=3)
    assert len(ids) == 3 and 1 not in ids and 2 not in ids


def test_prazna_biblioteka():
    assert Recommender(list).recommend() == []
