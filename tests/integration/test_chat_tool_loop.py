"""Chat SSE with the agent loop: event order, UI surfaces, approval round trip."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from negotium.adapters.llm.fake_adapter import FakeLlmProvider, ScriptedResponse
from negotium.app.container import Container
from negotium.app.main import create_app
from negotium.app.services import mcp_hub_service
from negotium.app.services.agent_loop_service import approval_id_for, to_wire_name
from negotium.app.settings import Settings
from negotium.archive.access_control import UserRecord
from negotium.domain.ports import ToolCall


def _container(tmp_path: Path) -> Container:
    settings = Settings(
        env="test",
        archive_dir=tmp_path / "archive",
        workspace_dir=tmp_path / "workspaces",
    )
    settings.llm.agent_tools_enabled = True
    return Container.build(settings)


def _auth_headers(container: Container, user_id: str = "owner") -> dict[str, str]:
    container.auth_store.create_user(
        user_id=user_id, display_name="Local Owner", password="password-1234"
    )
    container.access_control.upsert_user(
        UserRecord(id=user_id, display_name="Local Owner", title="대표", role_id="owner")
    )
    token = container.auth_store.authenticate(user_id, "password-1234")
    assert token is not None
    return {"X-NG-User": f"Bearer {token}"}


def _parse_sse(body: str) -> list[tuple[str, dict[str, Any]]]:
    events: list[tuple[str, dict[str, Any]]] = []
    for block in body.split("\n\n"):
        if not block.strip():
            continue
        name = "message"
        data_lines: list[str] = []
        for line in block.split("\n"):
            if line.startswith("event:"):
                name = line[6:].strip()
            elif line.startswith("data:"):
                data_lines.append(line[5:].strip())
        if data_lines:
            events.append((name, json.loads("\n".join(data_lines))))
    return events


def test_read_tool_stream_emits_tool_and_ui_events_in_order(tmp_path: Path) -> None:
    container = _container(tmp_path)
    headers = _auth_headers(container)
    container.llm = FakeLlmProvider(
        supports_tools=True,
        responses=[
            ScriptedResponse(
                text="",
                tool_calls=[
                    ToolCall(
                        id="c1",
                        name=to_wire_name("ui.open_surface"),
                        arguments={"surface": "uploads", "title": "엑셀 업로드"},
                    )
                ],
            ),
            ScriptedResponse(text="업로드 화면을 열었습니다."),
        ],
    )
    app = create_app(container)

    with TestClient(app) as client:
        response = client.post(
            "/api/llm/chat/stream",
            headers=headers,
            json={"message": "엑셀 올리고 싶어", "route": "api", "provider": "fake"},
        )

    assert response.status_code == 200
    names = [name for name, _payload in _parse_sse(response.text)]
    # Tool progress must reach the client before any answer text, otherwise the
    # user watches an empty bubble for the whole tool run.
    assert names.index("tool_call") < names.index("tool_result")
    assert names.index("tool_result") < names.index("ui_component")
    assert names.index("ui_component") < names.index("meta")
    assert names[-1] == "done"

    events = dict(_parse_sse(response.text))
    assert events["tool_call"]["tool"] == "ui.open_surface"
    assert events["ui_component"]["component"] == "uploads"
    assert events["ui_component"]["title"] == "엑셀 업로드"
    done = events["done"]
    assert done["answer"] == "업로드 화면을 열었습니다."
    assert done["ui_components"][0]["component"] == "uploads"
    assert done["conversation_id"]


def test_write_tool_requires_approval_then_executes(tmp_path: Path, monkeypatch) -> None:
    container = _container(tmp_path)
    headers = _auth_headers(container)
    executed: list[str] = []
    monkeypatch.setattr(
        mcp_hub_service,
        "_dispatch_tool",
        lambda _c, name, _args, **_kw: (executed.append(name), {"ok": True})[1],
    )

    arguments = {"skill_id": "office_summarize", "inputs": {}}
    call = ToolCall(id="c1", name=to_wire_name("skills.run"), arguments=arguments)
    container.llm = FakeLlmProvider(
        supports_tools=True,
        responses=[ScriptedResponse(text="", tool_calls=[call])],
    )
    app = create_app(container)

    with TestClient(app) as client:
        first = client.post(
            "/api/llm/chat",
            headers=headers,
            json={"message": "요약 스킬 실행해줘", "route": "api", "provider": "fake"},
        )
        assert first.status_code == 200
        pending = first.json()["pending_approval"]
        conversation_id = first.json()["conversation_id"]

        # Nothing ran: a write tool waits for the user.
        assert executed == []
        assert pending["tool"] == "skills.run"
        assert pending["approval_id"] == approval_id_for(conversation_id, "skills.run", arguments)

        # Resend with the decision attached. The approved call is replayed
        # server-side before the model runs, so the model only has to answer —
        # it is never asked to propose the same call a second time.
        container.llm = FakeLlmProvider(
            supports_tools=True,
            responses=[ScriptedResponse(text="요약을 실행했습니다.")],
        )
        second = client.post(
            "/api/llm/chat",
            headers=headers,
            json={
                "message": "요약 스킬 실행해줘",
                "route": "api",
                "provider": "fake",
                "conversation_id": conversation_id,
                "approvals": [
                    {
                        "approval_id": pending["approval_id"],
                        "tool": "skills.run",
                        "arguments": arguments,
                        "decision": "approve",
                    }
                ],
            },
        )

    assert second.status_code == 200
    assert executed == ["skills.run"]
    assert second.json()["answer"] == "요약을 실행했습니다."
    assert second.json()["pending_approval"] == {}
    # Exactly once: the approved call must not run again if the model happens
    # to propose it a second time.
    assert executed.count("skills.run") == 1


def test_agent_trace_is_persisted_for_the_turn(tmp_path: Path) -> None:
    container = _container(tmp_path)
    headers = _auth_headers(container)
    container.llm = FakeLlmProvider(
        supports_tools=True,
        responses=[
            ScriptedResponse(
                text="",
                tool_calls=[ToolCall(id="c1", name=to_wire_name("org.roster"), arguments={})],
                reasoning="조직 명부를 확인한다.",
            ),
            ScriptedResponse(text="1명입니다."),
        ],
    )
    app = create_app(container)

    with TestClient(app) as client:
        response = client.post(
            "/api/llm/chat",
            headers=headers,
            json={"message": "조직 인원 알려줘", "route": "api", "provider": "fake"},
        )

    assert response.status_code == 200
    assert response.json()["tool_invocations"][0]["tool"] == "org.roster"

    records = container.conversations.list_recent(user_id="owner", limit=10)
    assistant = next(record for record in records if record["role"] == "assistant")
    metadata = assistant["metadata"]
    assert isinstance(metadata, dict)
    # The trace is what lets an approval resume by replay instead of re-running
    # inference, and preserves Solar reasoning for the next turn.
    trace = metadata["agent_trace"]
    assert any(entry.get("tool_call_id") == "c1" for entry in trace)
    assert any(entry.get("reasoning") for entry in trace)


def test_ui_surfaces_endpoint_lists_allowed_screens(tmp_path: Path) -> None:
    container = _container(tmp_path)
    headers = _auth_headers(container)
    app = create_app(container)

    with TestClient(app) as client:
        response = client.get("/api/ui/surfaces", headers=headers)
        anonymous = client.get("/api/ui/surfaces")

    assert anonymous.status_code == 401
    assert response.status_code == 200
    surfaces = {item["id"]: item for item in response.json()["surfaces"]}
    assert "uploads" in surfaces
    assert surfaces["uploads"]["title"] == "업로드"
    # Dense admin screens are deliberately not inline-able.
    assert "personnel" not in surfaces
    assert "access" not in surfaces


def test_tools_stay_off_when_the_kill_switch_is_disabled(tmp_path: Path) -> None:
    """With NG_LLM_AGENT_TOOLS off a chat turn is a single completion."""

    settings = Settings(
        env="test",
        archive_dir=tmp_path / "archive",
        workspace_dir=tmp_path / "workspaces",
    )
    settings.llm.agent_tools_enabled = False
    container = Container.build(settings)
    headers = _auth_headers(container)
    fake = FakeLlmProvider(supports_tools=True, responses=[ScriptedResponse(text="안녕하세요")])
    container.llm = fake
    app = create_app(container)

    with TestClient(app) as client:
        response = client.post(
            "/api/llm/chat",
            headers=headers,
            json={"message": "안녕", "route": "api", "provider": "fake"},
        )

    assert response.status_code == 200
    assert len(fake.calls) == 1
    assert fake.option_calls[0] is None or not fake.option_calls[0].tools
