# tests/test_curator_search_navigate.py
# ========== TEST: search sa jasnim top-pogotkom → navigacija na stranicu filma ==========
# „Nadji mi film X" u chatu treba VIZUALNO da otvori stranicu filma (kao ručni
# klik), ne da vrati samo listu naslova.
import json
from pathlib import Path

from core.domains.filmium.curator.atoms import AtomLoader
from core.domains.filmium.curator.confirm import ConfirmStore
from core.domains.filmium.curator.executors import Executors
from core.domains.filmium.curator.intent_router import CuratorAgent
from core.domains.filmium.curator.interaction_log import InteractionLog


class _RetrieverID:
    def retrieve(self, query, top_n=10):
        return [{"title": "Mutiny", "media_id": 42}]


def _seed(root: Path) -> None:
    (root / "commands").mkdir(parents=True)
    (root / "persona.md").write_text("---\ntype: persona\n---\nKurator.\n", encoding="utf-8")
    (root / "commands" / "katalog.md").write_text("search|play\n", encoding="utf-8")


def _agent(tmp_path: Path, model_json: dict) -> CuratorAgent:
    root = tmp_path / "kurator"
    _seed(root)
    executors = Executors(
        retriever=_RetrieverID(), repository=None,
        launch_vlc=lambda p, s=None: True, resolve_video_path=lambda i: None,
    )
    return CuratorAgent(
        atoms=AtomLoader(root), executors=executors, confirm=ConfirmStore(),
        log=InteractionLog(tmp_path / "log"),
        generate=lambda model, prompt, *, system=None, fmt=None: json.dumps(model_json),
        model="qwen2.5",
    )


def test_search_sa_top_pogotkom_navigira_na_film(tmp_path):
    # Model vrati glupu „pretražujem..." narativu; kod je zameni potvrdom sa
    # naslovom stварно nađenog filma (jer search je zapravo OTVORIO stranicu).
    agent = _agent(
        tmp_path,
        {"intent": "search", "params": {"query": "munity"},
         "reply": "Pretražujem filmove sa 'munity' u nazivu..."},
    )
    result = agent.handle("nadji mi film munity")
    assert result.kind == "navigate"
    assert result.preview["route"] == "/filmium/media/42"
    assert "Mutiny" in result.sources
    assert "Pretražujem" not in result.reply  # nema glupe narative
    assert "Mutiny" in result.reply           # potvrda imenuje film
    assert result.log_id is not None
