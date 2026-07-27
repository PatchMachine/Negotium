"""Port interfaces (Hexagonal architecture).

Downstream ports are driven by the application to reach external systems —
today that means the LLM providers. All adapters in ``negotium.adapters``
implement one of these protocols.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

from negotium.domain.entities import LlmRoute


class ToolCall:
    """One tool invocation requested by the model."""

    __slots__ = ("arguments", "id", "name")

    def __init__(self, *, id: str, name: str, arguments: dict[str, Any]) -> None:
        self.id = id
        self.name = name
        self.arguments = arguments

    def to_dict(self) -> dict[str, Any]:
        return {"id": self.id, "name": self.name, "arguments": self.arguments}


@dataclass(frozen=True)
class ToolSpec:
    """A tool offered to the model. ``parameters`` is a JSON Schema object."""

    name: str
    description: str
    parameters: dict[str, Any]


@dataclass(frozen=True)
class LlmCallOptions:
    """Per-call knobs that only some providers/models understand.

    Passed as an optional keyword to :meth:`LlmProvider.complete` so the single
    shared completion path (context firewall, token budgets, metrics, secret
    force-local) keeps applying to tool calls without being duplicated.
    """

    tools: tuple[ToolSpec, ...] = ()
    tool_choice: str = "auto"  # auto | none | required
    # Model-specific vocabulary; see ``catalog.solar_reasoning_effort``.
    reasoning_effort: str = ""
    parallel_tool_calls: bool | None = None
    extra_body: Mapping[str, Any] = field(default_factory=dict)


class LlmResponse:
    """Value object for an LLM completion. Kept simple to avoid coupling to any SDK."""

    __slots__ = (
        "completion_tokens",
        "model",
        "prompt_tokens",
        "raw_message",
        "reasoning",
        "route",
        "stop_reason",
        "text",
        "tool_calls",
    )

    def __init__(
        self,
        *,
        text: str,
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
        route: LlmRoute = "cloud",
        model: str = "",
        tool_calls: Sequence[ToolCall] | None = None,
        stop_reason: str = "",
        reasoning: str = "",
        raw_message: Mapping[str, Any] | None = None,
    ) -> None:
        self.text = text
        self.prompt_tokens = prompt_tokens
        self.completion_tokens = completion_tokens
        self.route = route
        self.model = model
        self.tool_calls: list[ToolCall] = list(tool_calls or [])
        self.stop_reason = stop_reason
        # Solar/OpenAI reasoning trace. Preserved verbatim across turns: the
        # Solar model card warns against stripping reasoning from earlier turns
        # when building follow-up requests.
        self.reasoning = reasoning
        # The provider-native assistant message, replayed as-is on the next
        # turn so tool_call ids and reasoning survive a round trip.
        self.raw_message = dict(raw_message) if raw_message else None


# A multimodal content part is a small normalized dict that adapters translate
# into provider-native payloads. Three shapes are supported:
#   {"type": "text", "text": "..."}
#   {"type": "image", "mime": "image/png", "data": "<base64>"}
#   {"type": "audio", "mime": "audio/mpeg", "data": "<base64>", "format": "mp3"}
ContentPart = dict[str, Any]


class LlmMessage:
    """Minimal chat message structure usable across providers.

    ``content`` is either a plain string (the common case) or a list of
    normalized :data:`ContentPart` dicts for multimodal (text + image) input.
    Text-only adapters flatten image parts away via :func:`flatten_message_text`.

    Tool-calling fields are all optional keywords so the ~100 existing
    positional ``LlmMessage(role, content)`` constructions stay valid:

    * an assistant message that requested tools carries ``tool_calls``;
    * a ``role="tool"`` result message carries ``tool_call_id`` and ``name``;
    * ``reasoning`` preserves a Solar/OpenAI reasoning trace across turns.
    """

    __slots__ = ("content", "name", "raw", "reasoning", "role", "tool_call_id", "tool_calls")

    def __init__(
        self,
        role: str,
        content: str | list[ContentPart],
        *,
        tool_calls: Sequence[ToolCall] | None = None,
        tool_call_id: str = "",
        name: str = "",
        reasoning: str = "",
        raw: Mapping[str, Any] | None = None,
    ) -> None:
        self.role = role
        self.content = content
        self.tool_calls: list[ToolCall] = list(tool_calls or [])
        self.tool_call_id = tool_call_id
        self.name = name
        self.reasoning = reasoning
        # Provider-native assistant payload, replayed verbatim when present.
        self.raw = dict(raw) if raw else None


def text_part(text: str) -> ContentPart:
    return {"type": "text", "text": text}


def image_part(*, mime: str, data: str) -> ContentPart:
    return {"type": "image", "mime": mime, "data": data}


def audio_part(*, mime: str, data: str, fmt: str = "") -> ContentPart:
    return {"type": "audio", "mime": mime, "data": data, "format": fmt or _audio_format(mime)}


def _audio_format(mime: str) -> str:
    mapping = {
        "audio/mpeg": "mp3",
        "audio/mp3": "mp3",
        "audio/wav": "wav",
        "audio/x-wav": "wav",
        "audio/webm": "webm",
        "audio/ogg": "ogg",
        "audio/flac": "flac",
        "audio/mp4": "mp4",
        "audio/m4a": "m4a",
        "audio/x-m4a": "m4a",
    }
    return mapping.get(mime.lower(), "mp3")


def is_multimodal_content(content: str | list[ContentPart]) -> bool:
    return isinstance(content, list)


def flatten_message_text(content: str | list[ContentPart]) -> str:
    """Collapse multimodal content to plain text for text-only providers.

    Image parts are replaced with a short placeholder so the model is at least
    aware an image was attached but omitted.
    """

    if isinstance(content, str):
        return content
    rendered: list[str] = []
    for part in content:
        if part.get("type") == "text":
            rendered.append(str(part.get("text") or ""))
        elif part.get("type") == "image":
            rendered.append("[image omitted: text-only model]")
        elif part.get("type") == "audio":
            rendered.append("[audio omitted: text/vision-only model]")
    return "\n".join(chunk for chunk in rendered if chunk)


@runtime_checkable
class LlmProvider(Protocol):
    """Downstream port: unified chat-completion interface.

    ``options`` is optional and ignored by adapters that cannot use tools, so a
    single completion path keeps serving both plain chat and tool loops.
    """

    async def complete(
        self,
        messages: Sequence[LlmMessage],
        *,
        route: LlmRoute = "cloud",
        temperature: float = 0.0,
        max_tokens: int | None = None,
        options: LlmCallOptions | None = None,
    ) -> LlmResponse: ...
