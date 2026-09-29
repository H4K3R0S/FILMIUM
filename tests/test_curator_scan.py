# tests/test_curator_scan.py
# ========== TEST: scan_library intent — AI sam skenira biblioteku (direktorijume) ==========
from core.domains.filmium.curator.executors import Executors
from core.domains.filmium.curator.intents import get_intent


def _exec(scan=None) -> Executors:
    return Executors(
        retriever=None, repository=None,
        launch_vlc=lambda p: True, resolve_video_path=lambda i: None,
        scan_library=scan,
    )


def test_scan_library_calls_injected_with_root_id():
    seen = {}

    def fake(root_id):
        seen["root"] = root_id
        return {"roots": 1, "found": 3, "new": 1}

    out = _exec(fake).scan_library({"root_id": 2})
    assert seen["root"] == 2 and out["found"] == 3 and out["kind"] == "scan"


def test_scan_library_all_roots_when_no_id():
    seen = {}
    _exec(lambda r: seen.setdefault("root", r) or {"roots": 0}).scan_library({})
    assert seen["root"] is None


def test_scan_library_intent_registered():
    spec = get_intent("scan_library")
    assert spec is not None
    assert not spec.is_write and not spec.is_navigate and not spec.needs_media
