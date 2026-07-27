"""Context-window accounting for a chat turn.

The console has to show how much of the model's window a conversation is
using: with memory blocks, replayed turns and tool results all competing for
space, "why did it forget?" is otherwise unanswerable from the UI.

Token counts come from the provider's own usage numbers when available and
fall back to a character-ratio estimate, which is honest about being an
estimate rather than pretending to be exact.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from negotium.adapters.llm.catalog import model_profile
from negotium.domain.ports import LlmMessage, flatten_message_text

# Korean text averages markedly fewer characters per token than English, so a
# single global ratio would understate usage on this product's main language.
_CHARS_PER_TOKEN_KO = 1.6
_CHARS_PER_TOKEN_DEFAULT = 4.0

# Used when the catalog has no context_window for the model. Deliberately
# conservative so the meter warns early rather than late.
DEFAULT_CONTEXT_WINDOW = 32_000


def estimate_tokens(text: str) -> int:
    """Rough token count. Hangul-aware, never exact."""

    if not text:
        return 0
    hangul = sum(1 for char in text if "\uac00" <= char <= "\ud7a3")
    other = len(text) - hangul
    return int(hangul / _CHARS_PER_TOKEN_KO + other / _CHARS_PER_TOKEN_DEFAULT) + 1


def messages_tokens(messages: list[LlmMessage]) -> int:
    return sum(estimate_tokens(flatten_message_text(message.content)) for message in messages)


@dataclass(frozen=True)
class ContextUsage:
    """What one turn consumed, and how much room is left."""

    prompt_tokens: int
    completion_tokens: int
    context_window: int
    used_ratio: float
    history_turns: int
    tool_result_tokens: int
    estimated: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "context_window": self.context_window,
            "used_ratio": round(self.used_ratio, 4),
            "history_turns": self.history_turns,
            "tool_result_tokens": self.tool_result_tokens,
            "estimated": self.estimated,
        }


def context_window_for(provider: str, model: str) -> int:
    window = model_profile(provider, model).context_window
    return window or DEFAULT_CONTEXT_WINDOW


def build_usage(
    *,
    provider: str,
    model: str,
    messages: list[LlmMessage],
    prompt_tokens: int,
    completion_tokens: int,
    history_turns: int,
) -> ContextUsage:
    """Assemble the meter payload for one completed turn."""

    window = context_window_for(provider, model)
    estimated = prompt_tokens <= 0
    if estimated:
        prompt_tokens = messages_tokens(messages)
    tool_tokens = sum(
        estimate_tokens(flatten_message_text(message.content))
        for message in messages
        if message.role == "tool"
    )
    used = prompt_tokens + max(0, completion_tokens)
    return ContextUsage(
        prompt_tokens=prompt_tokens,
        completion_tokens=max(0, completion_tokens),
        context_window=window,
        used_ratio=min(1.0, used / window) if window else 0.0,
        history_turns=history_turns,
        tool_result_tokens=tool_tokens,
        estimated=estimated,
    )
