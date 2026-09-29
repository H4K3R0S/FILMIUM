# tests/test_curator_wishlist_offer.py
# ========== TEST: kad naslov nije nađen (play) → auto-ponuda dodavanja u listu želja ==========
import json
from pathlib import Path

from core.domains.filmium.curator.atoms import AtomLoader
from core.domains.filmium.curator.confirm import ConfirmStore
from core.domains.filmium.curator.executors import Executors
from core.domains.filmium.curator.intent_router import CuratorAgent
from core.domains.filmium.curator.interaction_log import InteractionLog


class _Repo:
    def list_all(self):
        return []  # prazna biblioteka → naslov sigurno nije unutra


def _seed(root: Path) -> None:
    (root / "commands").mkdir(parents=True)
    (root / "persona.md").write_text("---\ntype: persona\n---\nKurator.\n", encoding="utf-8")
    (root / "commands" / "katalog.md").write_text("play|add_to_wishlist\n", encoding="utf-8")


def _agent(tmp_path: Path, model_json: dict) -> CuratorAgent:
    root = tmp_path / "kurator"
    _seed(root)
    executors = Executors(
        retriever=None, repository=_Repo(),
        launch_vlc=lambda p, s=None: True, resolve_video_path=lambda i: None,
        wishlist_titles=list,
    )
    return CuratorAgent(
        atoms=AtomLoader(root), executors=executors, confirm=ConfirmStore(),
        log=InteractionLog(tmp_path / "log"),
        generate=lambda model, prompt, *, system=None, fmt=None: json.dumps(model_json),
        model="qwen2.5",
    )


def test_play_nepostojeci_naslov_nudi_wishlist(tmp_path):
    # Nema resolvera → razrešavanje media_id pada → naslov nije u biblioteci → ponuda.
    agent = _agent(tmp_path, {"intent": "play", "params": {"title": "Blade Runner"}, "reply": ""})
    result = agent.handle("pusti Blade Runner")
    assert result.kind == "proposal" and result.intent == "add_to_wishlist"
    assert result.confirm_token is not None
    assert result.preview["title"] == "Blade Runner"
