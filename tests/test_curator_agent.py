# F:\FILMIUM\tests\test_curator_agent.py
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from core.domains.filmium.curator.atoms import AtomLoader
from core.domains.filmium.curator.confirm import ConfirmStore
from core.domains.filmium.curator.executors import Executors
from core.domains.filmium.curator.intent_router import CuratorAgent
from core.domains.filmium.curator.interaction_log import InteractionLog


def _seed_atoms(root: Path) -> None:
    (root / "tools").mkdir(parents=True)
    (root / "commands").mkdir(parents=True)
    (root / "persona.md").write_text("---\ntype: persona\n---\nKurator.\n", encoding="utf-8")
    for name in ("pretraga", "plejer", "izmena-info"):
        (root / "tools" / f"{name}.md").write_text(f"Uputstvo {name}.\n", encoding="utf-8")
    (root / "commands" / "katalog.md").write_text("search|play|edit_metadata|save\n", encoding="utf-8")


class _Retriever:
    def retrieve(self, query, top_n=10):
        return [{"title": "Matriks"}]


class _Repo:
    def get_by_id(self, item_id):
        from datetime import datetime, timezone

        from core.domains.filmium.models import MediaItem, MediaType, WatchStatus
        now = datetime.now(timezone.utc)
        return MediaItem(
            id=item_id, title="Matriks", media_type=MediaType.MOVIE, original_title=None,
            release_year=1999, watch_status=WatchStatus.COMPLETED, rating=9, notes=None,
            created_at=now, updated_at=now,
            english_title=None, runtime_minutes=136,
            english_description=None, content_category="regular", cast_names=(),
            studio=None, director="W", keywords=(), collection=None,
            is_synchronized=False, editor_settings={}, tmdb_id=None, genres=(),
            is_favorite=False, related_tmdb=(),
        )

    def update(self, item_id, create):
        self.updated = (item_id, create)


def _agent(tmp_path: Path, model_json: dict) -> CuratorAgent:
    atoms_root = tmp_path / "kurator"
    _seed_atoms(atoms_root)
    log_root = tmp_path / "log"
    executors = Executors(
        retriever=_Retriever(), repository=_Repo(),
        launch_vlc=lambda p, s=None: True,
        resolve_video_path=lambda mid: "F:/x.mkv",
    )
    return CuratorAgent(
        atoms=AtomLoader(atoms_root),
        executors=executors,
        confirm=ConfirmStore(),
        log=InteractionLog(log_root),
        generate=lambda model, prompt, *, system=None, fmt=None: json.dumps(model_json),
        model="qwen2.5",
    )


def test_search_izvrsava_odmah_i_loguje(tmp_path):
    agent = _agent(tmp_path, {"intent": "search", "params": {"query": "matriks"}, "reply": "Evo."})
    result = agent.handle("nadji matriks")
    assert result.kind == "answer"
    assert "Matriks" in result.sources
    assert result.log_id is not None


def test_play_vraca_navigate(tmp_path):
    agent = _agent(tmp_path, {"intent": "play", "params": {"media_id": 5}, "reply": "Puštam."})
    result = agent.handle("pusti matriks")
    assert result.kind == "navigate"
    assert result.params["media_id"] == 5


def test_edit_vraca_proposal_bez_upisa(tmp_path):
    agent = _agent(tmp_path, {"intent": "edit_metadata", "params": {"media_id": 5, "changes": {"rating": 7}}, "reply": "Menjam?"})
    result = agent.handle("stavi ocenu 7")
    assert result.kind == "proposal"
    assert result.confirm_token is not None
    assert result.preview["changes"] == {"rating": 7}


def test_confirm_izvrsi_upis(tmp_path):
    agent = _agent(tmp_path, {"intent": "edit_metadata", "params": {"media_id": 5, "changes": {"rating": 7}}, "reply": "Menjam?"})
    result = agent.handle("stavi ocenu 7")
    out = agent.confirm(result.confirm_token)
    assert out["updated"] is True


def test_nepoznat_intent_ne_izvrsava(tmp_path):
    agent = _agent(tmp_path, {"intent": "obrisi_bazu", "params": {}, "reply": "?"})
    result = agent.handle("obriši sve")
    assert result.kind == "answer"
    assert result.intent == "unknown"


def test_los_json_ne_izvrsava(tmp_path):
    agent = _agent(tmp_path, {})
    agent._generate = lambda *a, **k: "ovo nije json"
    result = agent.handle("nešto")
    assert result.kind == "answer"
    assert result.intent == "unknown"


class _PucaExecutors:
    """Izvršioci koji bacaju grešku ako ih neko pozove — media_id validacija
    mora da ih presretne PRE dispatch-a, ne posle."""

    def __getattr__(self, name):
        def _puca(*args, **kwargs):
            raise AssertionError(f"Executors.{name} ne sme biti pozvan za nevalidan media_id")

        return _puca


def _agent_sa_pucajucim_executors(tmp_path: Path, model_json: dict) -> CuratorAgent:
    atoms_root = tmp_path / "kurator"
    _seed_atoms(atoms_root)
    log_root = tmp_path / "log"
    return CuratorAgent(
        atoms=AtomLoader(atoms_root),
        executors=_PucaExecutors(),
        confirm=ConfirmStore(),
        log=InteractionLog(log_root),
        generate=lambda model, prompt, *, system=None, fmt=None: json.dumps(model_json),
        model="qwen2.5",
    )


def test_play_sa_nenumerickim_media_id_ne_izvrsava(tmp_path):
    agent = _agent_sa_pucajucim_executors(
        tmp_path, {"intent": "play", "params": {"media_id": "abc"}, "reply": "Puštam."}
    )
    result = agent.handle("pusti taj film")
    assert result.kind == "answer"
    assert result.intent == "unknown"


def test_edit_metadata_bez_media_id_ne_izvrsava(tmp_path):
    agent = _agent_sa_pucajucim_executors(
        tmp_path,
        {"intent": "edit_metadata", "params": {"changes": {"rating": 7}}, "reply": "Menjam?"},
    )
    result = agent.handle("stavi ocenu 7")
    assert result.kind == "answer"
    assert result.intent == "unknown"


@dataclass
class _Naslov:
    id: int
    title: str
    english_title: str | None = None


def _agent_sa_resolverom(tmp_path: Path, model_json: dict, *items: _Naslov) -> CuratorAgent:
    from core.domains.filmium.curator.media_resolver import MediaResolver

    atoms_root = tmp_path / "kurator"
    _seed_atoms(atoms_root)
    executors = Executors(
        retriever=_Retriever(), repository=_Repo(),
        launch_vlc=lambda p, s=None: True,
        resolve_video_path=lambda mid: "F:/x.mkv",
    )
    return CuratorAgent(
        atoms=AtomLoader(atoms_root),
        executors=executors,
        confirm=ConfirmStore(),
        log=InteractionLog(tmp_path / "log"),
        generate=lambda model, prompt, *, system=None, fmt=None: json.dumps(model_json),
        model="qwen2.5",
        resolver=MediaResolver(lambda: list(items)),
    )


def test_play_sa_naslovom_razresava_media_id(tmp_path):
    agent = _agent_sa_resolverom(
        tmp_path,
        {"intent": "play", "params": {"title": "Matriks"}, "reply": "Puštam."},
        _Naslov(7, "Matriks"),
    )
    result = agent.handle("pusti Matriks")
    assert result.kind == "navigate"
    assert result.params["media_id"] == 7


def test_play_naslov_bez_poklapanja_ne_izvrsava(tmp_path):
    agent = _agent_sa_resolverom(
        tmp_path,
        {"intent": "play", "params": {"title": "nepostojeci film xyz"}, "reply": "?"},
        _Naslov(7, "Matriks"),
    )
    result = agent.handle("pusti nesto")
    assert result.kind == "proposal"
    assert result.intent == "add_to_wishlist"


def _agent_sa_snimanjem_sistema(tmp_path: Path, model_json: dict, *, retrieve=None):
    """Agent čiji `generate` snima poslednji `system` prompt (za proveru RAG konteksta)."""

    atoms_root = tmp_path / "kurator"
    _seed_atoms(atoms_root)
    executors = Executors(
        retriever=_Retriever(), repository=_Repo(),
        launch_vlc=lambda p, s=None: True,
        resolve_video_path=lambda mid: "F:/x.mkv",
    )
    snimljeno: dict = {}

    def _generate(model, prompt, *, system=None, fmt=None):
        snimljeno["system"] = system
        return json.dumps(model_json)

    agent = CuratorAgent(
        atoms=AtomLoader(atoms_root),
        executors=executors,
        confirm=ConfirmStore(),
        log=InteractionLog(tmp_path / "log"),
        generate=_generate,
        model="qwen2.5",
        retrieve=retrieve,
    )
    return agent, snimljeno


def test_retrieve_ubacuje_kontekst_u_system(tmp_path):
    agent, snimljeno = _agent_sa_snimanjem_sistema(
        tmp_path,
        {"intent": "search", "params": {"query": "matriks"}, "reply": "Evo."},
        retrieve=lambda q: ["X"],
    )
    agent.handle("nadji matriks")
    assert "X" in snimljeno["system"]


def test_bez_retrieve_system_ostaje_nepromenjen(tmp_path):
    agent, snimljeno = _agent_sa_snimanjem_sistema(
        tmp_path,
        {"intent": "search", "params": {"query": "matriks"}, "reply": "Evo."},
        retrieve=None,
    )
    agent.handle("nadji matriks")
    assert "Relevantan kontekst iz memorije" not in snimljeno["system"]
