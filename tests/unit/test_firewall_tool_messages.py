"""The context firewall must not strip tool-calling identity fields.

``sanitize_llm_messages``/``sanitize_llm_response`` used to rebuild messages
from ``{role, content}`` alone. With tool calling that silently drops
``tool_call_id`` and ``tool_calls``, and the provider rejects the request
("messages with role 'tool' must be a response to a preceding tool_calls")
on the second loop iteration — a failure that only shows up in production
once a model actually asks for a tool.
"""

from __future__ import annotations

from negotium.app.services.context_firewall_service import (
    sanitize_llm_messages,
    sanitize_llm_response,
)
from negotium.domain.ports import LlmMessage, LlmResponse, ToolCall


def _tool_conversation() -> list[LlmMessage]:
    call = ToolCall(id="call_abc123", name="org.roster", arguments={"format": "json"})
    return [
        LlmMessage("system", "너는 네고티움 오피스 어시스턴트다."),
        LlmMessage("user", "우리 조직 인원 알려줘"),
        LlmMessage(
            "assistant",
            "",
            tool_calls=[call],
            reasoning="조직 명부를 조회해야 한다.",
            raw={
                "role": "assistant",
                "content": None,
                "tool_calls": [
                    {
                        "id": "call_abc123",
                        "type": "function",
                        "function": {"name": "org.roster", "arguments": '{"format": "json"}'},
                    }
                ],
            },
        ),
        LlmMessage(
            "tool",
            '{"users": [{"display_name": "김민수"}]}',
            tool_call_id="call_abc123",
            name="org.roster",
        ),
    ]


def test_tool_call_id_survives_sanitization() -> None:
    messages = _tool_conversation()
    sanitized, _result = sanitize_llm_messages(
        messages, destination="local_storage", task_type="chat"
    )
    by_role = {message.role: message for message in sanitized}

    assert by_role["tool"].tool_call_id == "call_abc123"
    assert by_role["tool"].name == "org.roster"

    assistant = by_role["assistant"]
    assert [call.id for call in assistant.tool_calls] == ["call_abc123"]
    assert assistant.tool_calls[0].name == "org.roster"
    assert assistant.tool_calls[0].arguments == {"format": "json"}
    # The provider-native payload is replayed verbatim, so it must come back too.
    assert assistant.raw is not None
    assert assistant.raw["tool_calls"][0]["id"] == "call_abc123"


def test_reasoning_is_carried_and_sanitized_consistently() -> None:
    """Reasoning must be redacted in both the field and the replayed raw payload.

    ``raw`` is sent to the provider verbatim; if only the field were sanitized
    the redaction would be undone on replay.
    """

    secret = "sk-abcdefghijklmnopqrstuvwxyz012345"
    messages = [
        LlmMessage(
            "assistant",
            "확인했습니다.",
            reasoning=f"키는 {secret} 이다.",
            raw={
                "role": "assistant",
                "content": "확인했습니다.",
                "reasoning": f"키는 {secret} 이다.",
            },
        )
    ]
    sanitized, _result = sanitize_llm_messages(
        messages, destination="frontier_api", task_type="chat"
    )
    assistant = next(message for message in sanitized if message.role == "assistant")
    assert secret not in assistant.reasoning
    assert assistant.raw is not None
    assert secret not in str(assistant.raw)
    # Both copies agree.
    assert assistant.raw["reasoning"] == assistant.reasoning


def test_response_keeps_tool_calls_and_stop_reason() -> None:
    response = LlmResponse(
        text="조회하겠습니다.",
        route="cloud",
        model="solar-pro3",
        tool_calls=[ToolCall(id="call_1", name="sheets.describe", arguments={"upload_id": "u1"})],
        stop_reason="tool_calls",
        reasoning="엑셀을 먼저 살펴본다.",
        raw_message={"role": "assistant", "content": None, "tool_calls": []},
    )
    sanitized = sanitize_llm_response(response, destination="frontier_api", task_type="chat")

    assert [call.name for call in sanitized.tool_calls] == ["sheets.describe"]
    assert sanitized.tool_calls[0].arguments == {"upload_id": "u1"}
    assert sanitized.stop_reason == "tool_calls"
    assert sanitized.raw_message is not None


def test_multimodal_content_still_round_trips() -> None:
    """The pre-existing image-part behaviour must not regress."""

    messages = [
        LlmMessage(
            "user",
            [
                {"type": "text", "text": "이 이미지 설명해줘"},
                {"type": "image", "mime": "image/png", "data": "AAAABBBB"},
            ],
        )
    ]
    sanitized, _result = sanitize_llm_messages(
        messages, destination="frontier_api", task_type="chat"
    )
    user = next(message for message in sanitized if message.role == "user")
    assert isinstance(user.content, list)
    image = next(part for part in user.content if part.get("type") == "image")
    assert image["data"] == "AAAABBBB"


def test_raw_message_content_is_redacted_not_just_reasoning() -> None:
    """`raw` is replayed verbatim, so its content must carry the redaction.

    Sanitizing only the `text`/`reasoning` fields meant the pre-redaction
    assistant content went back to the provider on the next loop iteration.
    """

    secret = "sk-abcdefghijklmnopqrstuvwxyz012345"
    messages = [
        LlmMessage(
            "assistant",
            f"키는 {secret} 입니다.",
            tool_calls=[ToolCall(id="c1", name="org.roster", arguments={})],
            raw={
                "role": "assistant",
                "content": f"키는 {secret} 입니다.",
                "tool_calls": [
                    {
                        "id": "c1",
                        "type": "function",
                        "function": {"name": "org_roster", "arguments": f'{{"q": "{secret}"}}'},
                    }
                ],
            },
        )
    ]
    sanitized, _result = sanitize_llm_messages(
        messages, destination="frontier_api", task_type="chat"
    )
    assistant = next(message for message in sanitized if message.role == "assistant")

    assert assistant.raw is not None
    assert secret not in str(assistant.raw)
    # tool_call ids still survive — the redaction must not break the sequence.
    assert assistant.raw["tool_calls"][0]["id"] == "c1"


def test_response_raw_message_content_is_redacted() -> None:
    secret = "ghp_abcdefghijklmnopqrstuvwxyz012345"
    response = LlmResponse(
        text=f"토큰은 {secret}",
        route="cloud",
        model="solar-pro3",
        tool_calls=[ToolCall(id="c1", name="org.roster", arguments={})],
        raw_message={"role": "assistant", "content": f"토큰은 {secret}", "tool_calls": []},
    )
    sanitized = sanitize_llm_response(response, destination="frontier_api", task_type="chat")

    assert secret not in sanitized.text
    assert sanitized.raw_message is not None
    assert secret not in str(sanitized.raw_message)


def test_uuids_are_not_mistaken_for_card_numbers() -> None:
    """A bare digit-run regex flagged ~0.1% of UUIDs as cards.

    The affected upload id got rewritten to [REDACTED_CARD_NUMBER] inside the
    tool arguments, so that one file became permanently unreadable by the AI.
    """

    from negotium.app.services.context_firewall_service import sanitize_text

    uuid_like = "d4a07fed-2c33-4b3a-9302-481001957711"
    assert sanitize_text(uuid_like, destination="frontier_api") == uuid_like

    # A real (Luhn-valid) card number is still redacted.
    assert "4111111111111111" not in sanitize_text(
        "카드 4111111111111111", destination="frontier_api"
    )
