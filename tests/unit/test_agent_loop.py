"""Agent tool loop: read auto-executes, writes need approval, loop terminates."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from negotium.adapters.llm.fake_adapter import FakeLlmProvider, ScriptedResponse
from negotium.app.container import Container
from negotium.app.services import agent_loop_service, mcp_hub_service
from negotium.app.services.agent_loop_service import (
    MAX_TOOL_ITERATIONS,
    approval_id_for,
    available_tools,
    run_agent_loop,
    tool_name_map,
)
from negotium.app.settings import Settings
from negotium.archive.access_control import UserRecord
from negotium.domain.ports import LlmMessage, ToolCall


def _container(tmp_path: Path) -> Container:
    container = Container.build(
        Settings(
            env="test",
            archive_dir=tmp_path / "archive",
            workspace_dir=tmp_path / "workspaces",
        )
    )
    container.access_control.upsert_user(
        UserRecord(id="owner", display_name="Local Owner", title="대표", role_id="owner")
    )
    return container


def _complete_from(fake: FakeLlmProvider) -> Any:
    """Adapt FakeLlmProvider to the loop's injected ``complete`` signature."""

    async def complete(container: Any, messages: list[LlmMessage], **kwargs: Any) -> Any:
        return await fake.complete(messages, options=kwargs.get("options"))

    return complete


async def _run(container: Container, fake: FakeLlmProvider, **kwargs: Any) -> Any:
    return await run_agent_loop(
        container,
        [LlmMessage("user", "우리 조직 인원 알려줘")],
        complete=_complete_from(fake),
        provider="fake",
        route="cloud",
        model="fake",
        actor="owner",
        task="chat",
        conversation_id="conv-1",
        **kwargs,
    )


async def test_read_tool_executes_without_approval(tmp_path: Path, monkeypatch) -> None:
    container = _container(tmp_path)
    calls: list[tuple[str, dict[str, Any]]] = []

    def fake_dispatch(_c: Any, name: str, args: dict[str, Any], **_kw: Any) -> dict[str, Any]:
        calls.append((name, args))
        return {"skills": []}

    monkeypatch.setattr(mcp_hub_service, "_dispatch_tool", fake_dispatch)

    fake = FakeLlmProvider(
        supports_tools=True,
        responses=[
            ScriptedResponse(
                text="",
                tool_calls=[ToolCall(id="c1", name="skills.list", arguments={})],
            ),
            ScriptedResponse(text="등록된 스킬이 없습니다."),
        ],
    )
    result = await _run(container, fake, tool_names=["skills.list"])

    assert calls == [("skills.list", {})]
    assert result.text == "등록된 스킬이 없습니다."
    assert [item.status for item in result.invocations] == ["executed"]
    assert result.pending_approval is None
    # assistant(tool_calls) + tool result + final assistant were appended.
    roles = [message.role for message in result.messages]
    assert roles == ["user", "assistant", "tool", "assistant"]
    tool_message = result.messages[2]
    assert tool_message.tool_call_id == "c1"
    assert agent_loop_service.UNTRUSTED_RESULT_BANNER in tool_message.content


async def test_write_tool_pauses_for_approval_and_does_not_execute(
    tmp_path: Path, monkeypatch
) -> None:
    container = _container(tmp_path)
    executed: list[str] = []

    def fake_dispatch(_c: Any, name: str, _args: dict[str, Any], **_kw: Any) -> dict[str, Any]:
        executed.append(name)
        return {"ok": True}

    monkeypatch.setattr(mcp_hub_service, "_dispatch_tool", fake_dispatch)

    fake = FakeLlmProvider(
        supports_tools=True,
        responses=[
            ScriptedResponse(
                text="스킬을 실행하겠습니다.",
                tool_calls=[
                    ToolCall(id="c1", name="skills.run", arguments={"skill_id": "office_summarize"})
                ],
            )
        ],
    )
    result = await _run(container, fake, tool_names=["skills.run"])

    assert executed == [], "write tool must not run before approval"
    assert result.pending_approval is not None
    assert result.pending_approval.tool == "skills.run"
    assert [item.status for item in result.invocations] == ["pending_approval"]


async def test_approved_write_tool_executes(tmp_path: Path, monkeypatch) -> None:
    container = _container(tmp_path)
    executed: list[str] = []

    def fake_dispatch(_c: Any, name: str, _args: dict[str, Any], **_kw: Any) -> dict[str, Any]:
        executed.append(name)
        return {"ok": True}

    monkeypatch.setattr(mcp_hub_service, "_dispatch_tool", fake_dispatch)

    arguments = {"skill_id": "office_summarize"}
    approval_id = approval_id_for("conv-1", "skills.run", arguments)
    fake = FakeLlmProvider(
        supports_tools=True,
        responses=[
            ScriptedResponse(
                text="",
                tool_calls=[ToolCall(id="c1", name="skills.run", arguments=arguments)],
            ),
            ScriptedResponse(text="실행했습니다."),
        ],
    )
    result = await _run(
        container,
        fake,
        tool_names=["skills.run"],
        approvals={approval_id: {"decision": "approve"}},
    )

    assert executed == ["skills.run"]
    assert result.text == "실행했습니다."
    assert result.pending_approval is None


async def test_approval_hash_does_not_transfer_to_other_arguments(tmp_path: Path) -> None:
    """Approving one payload must not authorise a different one."""

    approved = approval_id_for("conv-1", "skills.run", {"skill_id": "office_summarize"})
    other = approval_id_for("conv-1", "skills.run", {"skill_id": "delete_everything"})
    assert approved != other
    # Argument order must not change the token.
    assert approval_id_for("c", "t", {"a": 1, "b": 2}) == approval_id_for(
        "c", "t", {"b": 2, "a": 1}
    )


async def test_permission_denial_returns_tool_error_not_exception(
    tmp_path: Path, monkeypatch
) -> None:
    container = _container(tmp_path)
    container.access_control.upsert_user(
        UserRecord(id="viewer", display_name="Viewer", title="사원", role_id="viewer")
    )
    monkeypatch.setattr(
        mcp_hub_service,
        "_dispatch_tool",
        lambda *_a, **_kw: pytest.fail("denied tool must not dispatch"),
    )
    # available_tools filters by permission, so ask the model for a tool the
    # viewer cannot run by naming it explicitly in the scripted response.
    fake = FakeLlmProvider(
        supports_tools=True,
        responses=[
            ScriptedResponse(
                text="",
                tool_calls=[ToolCall(id="c1", name="skills.run", arguments={"skill_id": "x"})],
            ),
            ScriptedResponse(text="권한이 없어 실행하지 못했습니다."),
        ],
    )
    result = await run_agent_loop(
        container,
        [LlmMessage("user", "스킬 실행해줘")],
        complete=_complete_from(fake),
        provider="fake",
        route="cloud",
        model="fake",
        actor="viewer",
        task="chat",
        conversation_id="conv-1",
        tool_names=["skills.run"],
    )

    assert [item.status for item in result.invocations] == ["denied"]
    assert result.invocations[0].result["error"] == "permission_denied"
    assert result.text == "권한이 없어 실행하지 못했습니다."


async def test_unavailable_tools_are_not_advertised(tmp_path: Path) -> None:
    container = _container(tmp_path)
    container.access_control.upsert_user(
        UserRecord(id="viewer", display_name="Viewer", title="사원", role_id="viewer")
    )
    # Specs carry provider-legal (wire) names; tool_name_map translates back.
    owner_tools = set(tool_name_map(container, "owner").values())
    viewer_tools = set(tool_name_map(container, "viewer").values())

    assert "skills.run" in owner_tools
    assert "skills.run" not in viewer_tools, "write tool must not be offered to a viewer"


async def test_iteration_cap_forces_a_prose_answer(tmp_path: Path, monkeypatch) -> None:
    """A model that keeps calling tools must still produce an answer."""

    container = _container(tmp_path)
    monkeypatch.setattr(mcp_hub_service, "_dispatch_tool", lambda *_a, **_kw: {"skills": []})

    # More tool-call responses than the loop allows, then a final answer that
    # the forced tool_choice="none" pass will pick up.
    responses = [
        ScriptedResponse(
            text="",
            tool_calls=[ToolCall(id=f"c{i}", name="skills.list", arguments={})],
        )
        for i in range(MAX_TOOL_ITERATIONS + 3)
    ]
    fake = FakeLlmProvider(supports_tools=True, responses=responses)
    result = await _run(container, fake, tool_names=["skills.list"])

    assert result.iterations == MAX_TOOL_ITERATIONS
    # The final pass must have disabled tools so the loop cannot run forever.
    assert fake.option_calls[-1] is not None
    assert fake.option_calls[-1].tool_choice == "none"


async def test_tool_specs_carry_json_schema(tmp_path: Path) -> None:
    container = _container(tmp_path)
    specs = {spec.name: spec for spec in available_tools(container, "owner", ["skills.run"])}
    # Dots are illegal in an OpenAI/Solar function name; the real API rejects
    # the whole request, so MCP ids are translated on the way out.
    assert "skills_run" in specs
    assert tool_name_map(container, "owner", ["skills.run"]) == {"skills_run": "skills.run"}
    schema = specs["skills_run"].parameters
    assert schema["type"] == "object"
    assert "skill_id" in schema["properties"]


async def test_approved_call_is_replayed_not_re_proposed(tmp_path: Path, monkeypatch) -> None:
    """Approval must not depend on the model re-proposing identical arguments.

    Re-inference is not reproducible: in practice the model comes back with
    slightly different arguments, the content hash stops matching and the user
    is asked to approve the same action twice. The approved call is therefore
    executed server-side before the model runs again.
    """

    container = _container(tmp_path)
    executed: list[dict[str, Any]] = []

    def fake_dispatch(_c: Any, name: str, args: dict[str, Any], **_kw: Any) -> dict[str, Any]:
        executed.append({"tool": name, "args": args})
        return {"ok": True}

    monkeypatch.setattr(mcp_hub_service, "_dispatch_tool", fake_dispatch)

    arguments = {"skill_id": "office_summarize"}
    approval_id = approval_id_for("conv-1", "skills.run", arguments)
    # The model does NOT propose the tool again — it just answers.
    fake = FakeLlmProvider(supports_tools=True, responses=[ScriptedResponse(text="실행했습니다.")])

    result = await _run(
        container,
        fake,
        tool_names=["skills.run"],
        approvals={
            approval_id: {
                "approval_id": approval_id,
                "tool": "skills.run",
                "arguments": arguments,
                "decision": "approve",
            }
        },
    )

    assert [item["tool"] for item in executed] == ["skills.run"]
    # Exactly the approved arguments ran, not something the model re-derived.
    assert executed[0]["args"] == arguments
    assert result.text == "실행했습니다."
    # The model sees the executed call and its result in the transcript.
    roles = [message.role for message in result.messages]
    assert roles[:3] == ["user", "assistant", "tool"]


async def test_a_consumed_approval_does_not_execute_twice(tmp_path: Path, monkeypatch) -> None:
    container = _container(tmp_path)
    executed: list[str] = []
    monkeypatch.setattr(
        mcp_hub_service,
        "_dispatch_tool",
        lambda _c, name, _args, **_kw: (executed.append(name), {"ok": True})[1],
    )

    arguments = {"skill_id": "office_summarize"}
    approval_id = approval_id_for("conv-1", "skills.run", arguments)
    fake = FakeLlmProvider(
        supports_tools=True,
        responses=[
            # The model proposes the same call again after it already ran.
            ScriptedResponse(
                text="",
                tool_calls=[ToolCall(id="c1", name="skills.run", arguments=arguments)],
            ),
            ScriptedResponse(text="이미 실행되었습니다."),
        ],
    )

    result = await _run(
        container,
        fake,
        tool_names=["skills.run"],
        approvals={
            approval_id: {
                "approval_id": approval_id,
                "tool": "skills.run",
                "arguments": arguments,
                "decision": "approve",
            }
        },
    )

    # Ran once, and the user was not asked to confirm a second time.
    assert executed == ["skills.run"]
    assert result.pending_approval is None
    assert any(item.result.get("already_executed") for item in result.invocations)


def test_leaked_tool_template_tokens_are_stripped() -> None:
    """Solar can emit raw chat-template tokens as answer text.

    Seen on the final ``tool_choice="none"`` pass: the model still wants a tool
    but cannot emit a structured call, so it writes the template inline. The
    user must never see it.
    """

    leaked = (
        "<|tool_call:begin|>b462b4f8<|tool_call:name|>setup_propose_result"
        '<|tool_call:args|>{"result": {"company_name": "청우식품"}}'
    )
    assert "tool_call" not in agent_loop_service.clean_answer_text(leaked)
    # Nothing usable is left, so the user gets a readable message instead of "".
    assert agent_loop_service.clean_answer_text(leaked)

    mixed = f"조직 정보를 확인했습니다.\n{leaked}"
    assert agent_loop_service.clean_answer_text(mixed) == "조직 정보를 확인했습니다."

    normal = "부서는 영업팀, 개발팀입니다."
    assert agent_loop_service.clean_answer_text(normal) == normal
    assert agent_loop_service.clean_answer_text("") == ""


async def test_approval_cannot_escalate_to_a_tool_the_caller_lacks(
    tmp_path: Path, monkeypatch
) -> None:
    """The approvals list is attacker-controlled request data.

    Before this check, any user with `llm:chat` could run an `admin:local_llm`
    tool by POSTing a crafted approvals payload — the replay path executed it
    without the RBAC check every other path applies.
    """

    container = _container(tmp_path)
    container.access_control.upsert_user(
        UserRecord(id="viewer", display_name="Viewer", title="사원", role_id="viewer")
    )
    monkeypatch.setattr(
        mcp_hub_service,
        "_dispatch_tool",
        lambda *_a, **_kw: pytest.fail("privileged tool must not run"),
    )

    arguments = {"model_id": "evil/model"}
    fake = FakeLlmProvider(supports_tools=True, responses=[ScriptedResponse(text="안 됩니다.")])
    result = await run_agent_loop(
        container,
        [LlmMessage("user", "무엇이든")],
        complete=_complete_from(fake),
        provider="fake",
        route="cloud",
        model="fake",
        actor="viewer",
        task="chat",
        conversation_id="conv-1",
        approvals={
            approval_id_for("conv-1", "hf.set_local_model", arguments): {
                "tool": "hf.set_local_model",
                "arguments": arguments,
                "decision": "approve",
            }
        },
    )

    assert result.invocations == []


async def test_approval_id_must_match_the_arguments(tmp_path: Path, monkeypatch) -> None:
    """A forged id must not authorise arbitrary arguments."""

    container = _container(tmp_path)
    monkeypatch.setattr(
        mcp_hub_service,
        "_dispatch_tool",
        lambda *_a, **_kw: pytest.fail("unverified approval must not run"),
    )

    fake = FakeLlmProvider(supports_tools=True, responses=[ScriptedResponse(text="확인했습니다.")])
    result = await _run(
        container,
        fake,
        tool_names=["skills.run"],
        approvals={
            "not-a-real-hash": {
                "tool": "skills.run",
                "arguments": {"skill_id": "office_summarize"},
                "decision": "approve",
            }
        },
    )

    assert result.invocations == []


async def test_approval_outside_the_scoped_tool_set_is_refused(tmp_path: Path, monkeypatch) -> None:
    """A scoped conversation (e.g. setup) must stay inside its tool list."""

    container = _container(tmp_path)
    monkeypatch.setattr(
        mcp_hub_service,
        "_dispatch_tool",
        lambda *_a, **_kw: pytest.fail("out-of-scope tool must not run"),
    )

    arguments = {"model_id": "x"}
    fake = FakeLlmProvider(supports_tools=True, responses=[ScriptedResponse(text="네.")])
    result = await _run(
        container,
        fake,
        tool_names=["skills.list"],
        approvals={
            approval_id_for("conv-1", "hf.set_local_model", arguments): {
                "tool": "hf.set_local_model",
                "arguments": arguments,
                "decision": "approve",
            }
        },
    )

    assert result.invocations == []


async def test_loop_always_returns_prose_even_if_tool_choice_is_ignored(
    tmp_path: Path, monkeypatch
) -> None:
    """Solar/vLLM sometimes keep requesting tools on the tool_choice="none" pass.

    Falling out of the loop with empty text made the caller raise "빈 응답" and
    the user got a 500 instead of an answer.
    """

    container = _container(tmp_path)
    monkeypatch.setattr(mcp_hub_service, "_dispatch_tool", lambda *_a, **_kw: {"skills": []})

    fake = FakeLlmProvider(
        supports_tools=True,
        responses=[
            ScriptedResponse(
                text="",
                tool_calls=[ToolCall(id=f"c{index}", name="skills.list", arguments={})],
            )
            for index in range(MAX_TOOL_ITERATIONS + 2)
        ],
    )
    result = await _run(container, fake, tool_names=["skills.list"])

    assert result.text
    assert result.notes


async def test_approved_call_message_has_no_dotted_name_field(tmp_path: Path, monkeypatch) -> None:
    """`name` on a chat message only accepts [a-zA-Z0-9_-]; dots 400 the request."""

    container = _container(tmp_path)
    monkeypatch.setattr(
        mcp_hub_service,
        "_dispatch_tool",
        lambda *_a, **_kw: {"ok": True},
    )

    arguments = {"skill_id": "office_summarize"}
    fake = FakeLlmProvider(supports_tools=True, responses=[ScriptedResponse(text="완료")])
    result = await _run(
        container,
        fake,
        tool_names=["skills.run"],
        approvals={
            approval_id_for("conv-1", "skills.run", arguments): {
                "tool": "skills.run",
                "arguments": arguments,
                "decision": "approve",
            }
        },
    )

    assistant = next(m for m in result.messages if m.role == "assistant" and m.tool_calls)
    assert assistant.name == ""


async def test_missing_actor_gets_no_tools(tmp_path: Path) -> None:
    """A falsy actor must be treated as unauthenticated, not as unrestricted."""

    container = _container(tmp_path)
    assert available_tools(container, "") == []
    assert tool_name_map(container, "") == {}


async def test_tool_call_denied_for_missing_actor(tmp_path: Path, monkeypatch) -> None:
    container = _container(tmp_path)
    monkeypatch.setattr(
        mcp_hub_service,
        "_dispatch_tool",
        lambda *_a, **_kw: pytest.fail("tool must not run without an actor"),
    )

    fake = FakeLlmProvider(
        supports_tools=True,
        responses=[
            ScriptedResponse(
                text="",
                tool_calls=[ToolCall(id="c1", name="skills.list", arguments={})],
            ),
            ScriptedResponse(text="로그인이 필요합니다."),
        ],
    )
    result = await run_agent_loop(
        container,
        [LlmMessage("user", "스킬 목록 알려줘")],
        complete=_complete_from(fake),
        provider="fake",
        route="cloud",
        model="fake",
        actor="",
        task="chat",
        conversation_id="conv-1",
        tool_names=["skills.list"],
    )

    assert [item.status for item in result.invocations] == ["denied"]
    assert result.invocations[0].result["error"] == "permission_denied"


async def test_approval_replay_denied_for_missing_actor(tmp_path: Path, monkeypatch) -> None:
    container = _container(tmp_path)
    monkeypatch.setattr(
        mcp_hub_service,
        "_dispatch_tool",
        lambda *_a, **_kw: pytest.fail("approved call must not run without an actor"),
    )

    arguments = {"skill_id": "office_summarize"}
    fake = FakeLlmProvider(supports_tools=True, responses=[ScriptedResponse(text="안 됩니다.")])
    result = await run_agent_loop(
        container,
        [LlmMessage("user", "실행해줘")],
        complete=_complete_from(fake),
        provider="fake",
        route="cloud",
        model="fake",
        actor="",
        task="chat",
        conversation_id="conv-1",
        tool_names=["skills.run"],
        approvals={
            approval_id_for("conv-1", "skills.run", arguments): {
                "tool": "skills.run",
                "arguments": arguments,
                "decision": "approve",
            }
        },
    )

    assert result.invocations == []
