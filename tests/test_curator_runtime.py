from __future__ import annotations

from apps.api import curator_runtime
from core.domains.filmium.curator.intent_router import CuratorAgent


def test_get_agent_vraca_curator_agenta():
    agent = curator_runtime.get_agent()
    assert isinstance(agent, CuratorAgent)
