from __future__ import annotations

from apps.api.schemas.filmium_curator import CuratorCommandResponse
from core.domains.filmium.curator.intent_router import AgentResult


def test_command_response_iz_domena():
    result = AgentResult(
        kind="proposal", intent="edit_metadata", params={"media_id": 5},
        reply="Menjam?", preview={"changes": {"rating": 7}},
        confirm_token="tok", sources=[], log_id="L1",
    )
    dto = CuratorCommandResponse.from_domain(result)
    assert dto.kind == "proposal"
    assert dto.confirm_token == "tok"
    assert dto.preview == {"changes": {"rating": 7}}
    assert dto.log_id == "L1"
