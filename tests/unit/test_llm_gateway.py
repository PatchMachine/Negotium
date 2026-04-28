"""LLM gateway routing safety net."""

from __future__ import annotations

import pytest

from patch_machine.adapters.llm.fake_adapter import FakeLlmProvider, ScriptedResponse
from patch_machine.adapters.llm.gateway import LlmGateway
from patch_machine.domain.ports import LlmMessage


async def test_default_route_uses_cloud_provider() -> None:
    cloud = FakeLlmProvider(responses=[ScriptedResponse(text="ok")])
    gateway = LlmGateway(cloud=cloud)
    response = await gateway.complete([LlmMessage("user", "hello")])
    assert response.text == "ok"
    assert response.route == "cloud"


async def test_secret_pattern_forces_local_and_raises_without_local() -> None:
    cloud = FakeLlmProvider(responses=[ScriptedResponse(text="leaked")])
    gateway = LlmGateway(cloud=cloud)
    msg = LlmMessage("user", "please review sk-abcdefghijklmnopqrstuvwxyz123456")
    with pytest.raises(RuntimeError):
        await gateway.complete([msg])


async def test_secret_pattern_routes_to_local_when_available() -> None:
    cloud = FakeLlmProvider(responses=[ScriptedResponse(text="cloud")])
    local = FakeLlmProvider(responses=[ScriptedResponse(text="local")])
    gateway = LlmGateway(cloud=cloud, local=local)
    msg = LlmMessage("user", "sk-aaaaaaaaaaaaaaaaaaaaaaaaa123456")
    response = await gateway.complete([msg])
    assert response.text == "local"
    assert response.route == "local"
