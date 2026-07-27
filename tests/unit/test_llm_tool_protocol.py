"""OpenAI-compatible tool wire format (covers solar, openai and together)."""

from __future__ import annotations

import json
from typing import Any

from negotium.adapters.llm.openai_adapter import OpenAiProvider
from negotium.domain.ports import LlmCallOptions, LlmMessage, ToolCall, ToolSpec

ROSTER_TOOL = ToolSpec(
    name="org.roster",
    description="회사 조직/인원 명부를 조회합니다.",
    parameters={"type": "object", "properties": {"format": {"type": "string"}}},
)


class _Recorder:
    """Minimal stand-in for the AsyncOpenAI client."""

    def __init__(self, message: Any, finish_reason: str = "stop") -> None:
        self.kwargs: dict[str, Any] = {}
        self._message = message
        self._finish_reason = finish_reason
        self.chat = self
        self.completions = self

    async def create(self, **kwargs: Any) -> Any:
        self.kwargs = kwargs
        choice = type(
            "Choice", (), {"message": self._message, "finish_reason": self._finish_reason}
        )
        usage = type("Usage", (), {"prompt_tokens": 11, "completion_tokens": 22})
        return type("Response", (), {"choices": [choice()], "usage": usage()})()


def _message(
    *, content: str | None = None, tool_calls: list[Any] | None = None, reasoning: str = ""
) -> Any:
    attributes: dict[str, Any] = {"content": content, "tool_calls": tool_calls}
    if reasoning:
        attributes["reasoning_content"] = reasoning
    return type("Message", (), attributes)()


def _raw_tool_call(call_id: str, name: str, arguments: str) -> Any:
    function = type("Function", (), {"name": name, "arguments": arguments})()
    return type("RawCall", (), {"id": call_id, "function": function})()


async def test_tools_and_reasoning_effort_reach_the_wire() -> None:
    client = _Recorder(_message(content="네."))
    provider = OpenAiProvider(api_key="k", model="solar-pro3", client=client)

    await provider.complete(
        [LlmMessage("user", "조직 인원 알려줘")],
        options=LlmCallOptions(
            tools=(ROSTER_TOOL,),
            tool_choice="auto",
            reasoning_effort="high",
            parallel_tool_calls=True,
        ),
    )

    # The dotted MCP id must be rewritten: OpenAI/Solar reject a function name
    # containing anything outside [a-zA-Z0-9_-].
    assert client.kwargs["tools"] == [
        {
            "type": "function",
            "function": {
                "name": "org_roster",
                "description": "회사 조직/인원 명부를 조회합니다.",
                "parameters": ROSTER_TOOL.parameters,
            },
        }
    ]
    assert client.kwargs["tool_choice"] == "auto"
    assert client.kwargs["parallel_tool_calls"] is True
    # reasoning_effort is not an OpenAI SDK argument, so it must ride in
    # extra_body or the SDK rejects the call.
    assert client.kwargs["extra_body"]["reasoning_effort"] == "high"


async def test_no_options_keeps_the_legacy_payload() -> None:
    """Plain completions must not grow tool fields."""

    client = _Recorder(_message(content="안녕하세요"))
    provider = OpenAiProvider(api_key="k", model="solar-pro2", client=client)

    await provider.complete([LlmMessage("user", "안녕")], max_tokens=100)

    assert "tools" not in client.kwargs
    assert "tool_choice" not in client.kwargs
    assert "extra_body" not in client.kwargs
    assert client.kwargs["max_tokens"] == 100


async def test_tool_calls_are_parsed_into_the_domain_type() -> None:
    client = _Recorder(
        _message(
            content=None,
            tool_calls=[_raw_tool_call("call_1", "org.roster", '{"format": "json"}')],
            reasoning="명부를 조회해야 한다.",
        ),
        finish_reason="tool_calls",
    )
    provider = OpenAiProvider(api_key="k", model="solar-pro3", client=client)

    response = await provider.complete([LlmMessage("user", "조직 알려줘")])

    assert len(response.tool_calls) == 1
    call = response.tool_calls[0]
    assert (call.id, call.name, call.arguments) == ("call_1", "org.roster", {"format": "json"})
    assert response.stop_reason == "tool_calls"
    assert response.reasoning == "명부를 조회해야 한다."
    # raw_message is replayed verbatim next turn, so it must be captured.
    assert response.raw_message is not None
    assert response.raw_message["tool_calls"][0]["id"] == "call_1"


async def test_malformed_tool_arguments_do_not_raise() -> None:
    """A model emitting invalid JSON must not blow up the whole turn.

    The loop turns the empty arguments into an error tool result the model can
    recover from on the next iteration.
    """

    client = _Recorder(
        _message(content=None, tool_calls=[_raw_tool_call("c1", "org.roster", "{not json")]),
        finish_reason="tool_calls",
    )
    provider = OpenAiProvider(api_key="k", model="solar-pro3", client=client)

    response = await provider.complete([LlmMessage("user", "조직")])

    assert response.tool_calls[0].arguments == {}


async def test_tool_result_messages_use_the_tool_role_shape() -> None:
    client = _Recorder(_message(content="12명입니다."))
    provider = OpenAiProvider(api_key="k", model="solar-pro3", client=client)

    await provider.complete(
        [
            LlmMessage("user", "조직 인원"),
            LlmMessage(
                "assistant",
                "",
                tool_calls=[ToolCall(id="c1", name="org.roster", arguments={"format": "json"})],
            ),
            LlmMessage("tool", '{"count": 12}', tool_call_id="c1", name="org.roster"),
        ]
    )

    messages = client.kwargs["messages"]
    tool_message = messages[2]
    assert tool_message["role"] == "tool"
    assert tool_message["tool_call_id"] == "c1"
    # Tool content must stay a plain string, not a content-part list.
    assert tool_message["content"] == '{"count": 12}'

    assistant = messages[1]
    assert assistant["tool_calls"][0]["id"] == "c1"
    assert json.loads(assistant["tool_calls"][0]["function"]["arguments"]) == {"format": "json"}


async def test_assistant_raw_payload_is_replayed_verbatim() -> None:
    client = _Recorder(_message(content="완료"))
    provider = OpenAiProvider(api_key="k", model="solar-pro3", client=client)
    raw = {
        "role": "assistant",
        "content": None,
        "tool_calls": [
            {
                "id": "c9",
                "type": "function",
                "function": {"name": "org.roster", "arguments": "{}"},
            }
        ],
    }

    await provider.complete([LlmMessage("assistant", "", raw=raw)])

    assert client.kwargs["messages"][0] == raw
