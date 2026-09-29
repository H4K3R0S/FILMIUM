# tests/test_curator_disambiguation.py
# ========== TEST: dvosmislen naslov (više pogodaka) → filtriran prikaz baš tih ==========
import json
from pathlib import Path

from core.domains.filmium.curator.atoms import AtomLoader
from core.domains.filmium.curator.confirm import ConfirmStore
from core.domains.filmium.curator.executors import Executors
from core.domains.filmium.curator.intent_router import CuratorAgent
from core.domains.filmium.curator.interaction_log import InteractionLog
from core.domains.filmium.curator.media_resolver import MediaResolver


class _Item:
    def __init__(self, iid: int, title: str) -> None:
        self.id = iid
        self.title = title
        self.english_title = None


_LIB = [_Item(1, "The Hunger Games 1"), _Item(2, "The Hunger Games 2"), _Item(3, "Matriks")]


def _seed(root: Path) -> None:
    (root / "commands").mkdir(parents=True)
    (root / "persona.md").write_text("---\ntype: persona\n---\nKurator.\n", encoding="utf-8")
    (root / "commands" / "katalog.md").write_text("play|search\n", encoding="utf-8")


def _agent(tmp_path: Path, model_json: dict) -> CuratorAgent:
    root = tmp_path / "kurator"
    _seed(root)
    execs = Executors(
        retriever=None, repository=None,
        launch_vlc=lambda p, s=None: True, resolve_video_path=lambda i: None,
    )
    return CuratorAgent(
        atoms=AtomLoader(root), executors=execs, confirm=ConfirmStore(),
        log=InteractionLog(tmp_path / "log"),
        generate=lambda m, p, *, system=None, fmt=None: json.dumps(model_json),
        model="qwen2.5", resolver=MediaResolver(lambda: _LIB),
    )


def test_dvosmislen_naslov_prikaze_filtrirano(tmp_path):
    # „hunger games" pogađa oba dela → umesto odustajanja, filtriran prikaz [1,2].
    agent = _agent(tmp_path, {"intent": "play", "params": {"title": "hunger games"}, "reply": ""})
    result = agent.handle("pusti hunger games")
    assert result.kind == "navigate"
    assert result.preview["route"] == "/filmium/library"
    assert set(result.preview["filters"]["ids"].split(",")) == {"1", "2"}
    assert "hunger games" in result.reply.lower()


def test_jedan_pogodak_ide_direktno(tmp_path):
    # Jasan pogodak (Matriks) → normalno razrešavanje u media_id (nije filtriran prikaz).
    agent = _agent(tmp_path, {"intent": "play", "params": {"title": "matriks"}, "reply": ""})
    result = agent.handle("pusti matriks")
    assert result.kind == "navigate"
    assert result.params.get("media_id") == 3
