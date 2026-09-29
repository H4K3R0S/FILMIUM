# tests/test_scan_media_type.py
# ========== TEST: auto film-vs-serija pri skeniranju (>=2 epizode → serija) ==========
from core.domains.filmium.library_scanner import resolve_media_type
from core.domains.filmium.models import MediaType


def test_resolve_series_when_detector_true(tmp_path):
    assert resolve_media_type(tmp_path, detector=lambda d: True) == MediaType.SERIES


def test_resolve_movie_when_detector_false(tmp_path):
    assert resolve_media_type(tmp_path, detector=lambda d: False) == MediaType.MOVIE


def test_resolve_movie_on_detector_error(tmp_path):
    def boom(_d):
        raise RuntimeError("x")

    assert resolve_media_type(tmp_path, detector=boom) == MediaType.MOVIE
