# tests/test_agent_retriever_http.py
# ========== TEST: LocalRetriever (RAG je opcion; nikad ne ruši Agenta) ==========
# Bez mreže/baze — RAG lanac se lažira preko sys.modules; graciozni put je stvaran.
import contextlib
import sys
import types

from apps.api.agent_retriever import LocalRetriever


def test_retrieve_bez_rag_vraca_prazno():
    # U test okruženju RAG/baza nije dostupna -> retrieve mora vratiti [] (ne sme da pukne).
    assert LocalRetriever("filmium", k=3).retrieve("bilo šta") == []


def _fake_rag(monkeypatch, nodes, docs):
    cfg = types.SimpleNamespace(dsn="x", embedding_model="m", embedding_endpoint="e")

    @contextlib.contextmanager
    def fake_conn(dsn):
        yield object()

    def _mod(name, **attrs):
        m = types.ModuleType(name)
        for k, v in attrs.items():
            setattr(m, k, v)
        monkeypatch.setitem(sys.modules, name, m)

    _mod("core.rag.config", load_rag_config=lambda: cfg)
    _mod("core.rag.connection", rag_connection=fake_conn)
    _mod("core.rag.embedder", Embedder=lambda *a, **k: object())
    _mod("core.rag.retrieve", search_domain=lambda *a, **k: nodes)
    _mod("core.rag.mcp_api", memory_get=lambda conn, nid: docs.get(nid))


def test_retrieve_vraca_snippete(monkeypatch):
    n1 = types.SimpleNamespace(node_id="n1", title="T1")
    n2 = types.SimpleNamespace(node_id="n2", title="T2")
    _fake_rag(monkeypatch, [n1, n2], {"n1": {"chunks": ["A"]}, "n2": {"chunks": ["B"]}})
    assert LocalRetriever("filmium", k=3).retrieve("x") == ["A", "B"]


def test_retrieve_greska_vraca_prazno(monkeypatch):
    def puca():
        raise RuntimeError("dole")
    _mod = types.ModuleType("core.rag.config")
    _mod.load_rag_config = lambda: (_ for _ in ()).throw(RuntimeError("dole"))
    monkeypatch.setitem(sys.modules, "core.rag.config", _mod)
    assert LocalRetriever("filmium", k=3).retrieve("x") == []