"""OpenAI chat completion adapter."""

from __future__ import annotations

import json
import re
import time
from collections.abc import Sequence
from typing import Any

from negotium.adapters.llm.multimodal import to_openai_content
from negotium.domain.entities import LlmRoute
from negotium.domain.ports import (
    LlmCallOptions,
    LlmMessage,
    LlmProvider,
    LlmResponse,
    ToolCall,
    ToolSpec,
)
from negotium.observability import get_logger

_COMPLETION_TOKENS_PREFIXES = (
    "o1",
    "o3",
    "o4",
    "o5",
    "gpt-5",
    "gpt-6",
)
_COMPLETION_TOKENS_KEYWORDS = ("reasoning",)


def _model_uses_completion_tokens_param(model: str) -> bool:
    """Return True when the model only accepts ``max_completion_tokens``.

    OpenAI reasoning/next-gen chat models (``o*``, ``gpt-5*``) reject the
    legacy ``max_tokens`` parameter and require ``max_completion_tokens``
    instead. Older chat models keep using ``max_tokens``.
    """

    name = (model or "").strip().lower()
    if not name:
        return False
    if name.startswith(_COMPLETION_TOKENS_PREFIXES):
        return True
    return any(keyword in name for keyword in _COMPLETION_TOKENS_KEYWORDS)


_UNSUPPORTED_PARAM_RE = re.compile(r"Unsupported parameter:\s*'?(?P<param>[\w_]+)'?", re.IGNORECASE)
_UNSUPPORTED_VALUE_PARAM_RE = re.compile(r"Unsupported value:.*?'(?P<param>[\w_]+)'", re.IGNORECASE)


def _extract_unsupported_param(message: str) -> str | None:
    match = _UNSUPPORTED_PARAM_RE.search(message or "")
    if not match:
        match = _UNSUPPORTED_VALUE_PARAM_RE.search(message or "")
    if not match:
        return None
    return match.group("param")


# The function-calling schema (OpenAI, Solar, Together) only accepts
# [a-zA-Z0-9_-] in a function name and rejects the entire request otherwise.
_WIRE_NAME_RE = re.compile(r"[^a-zA-Z0-9_-]")


def _wire_name(name: str) -> str:
    return _WIRE_NAME_RE.sub("_", name)[:64]


def _to_openai_tool(tool: ToolSpec) -> dict[str, Any]:
    return {
        "type": "function",
        "function": {
            "name": _wire_name(tool.name),
            "description": tool.description,
            "parameters": tool.parameters,
        },
    }


def _to_openai_message(message: LlmMessage) -> dict[str, Any]:
    """Translate one :class:`LlmMessage` into the OpenAI wire shape.

    Assistant turns that requested tools are replayed from ``raw`` when the
    adapter captured it, so provider-specific fields (ids, reasoning traces)
    survive the round trip byte for byte.
    """

    if message.role == "assistant" and message.raw:
        return dict(message.raw)
    if message.role == "tool":
        # Tool results are always plain strings — running them through
        # to_openai_content would wrap them in a content-part list, which the
        # API rejects for this role.
        return {
            "role": "tool",
            "tool_call_id": message.tool_call_id,
            "content": message.content if isinstance(message.content, str) else "",
        }
    payload: dict[str, Any] = {"role": message.role, "content": to_openai_content(message.content)}
    if message.tool_calls:
        payload["tool_calls"] = [
            {
                "id": call.id,
                "type": "function",
                "function": {
                    "name": _wire_name(call.name),
                    "arguments": json.dumps(call.arguments),
                },
            }
            for call in message.tool_calls
        ]
    if message.name:
        payload["name"] = message.name
    return payload


def _parse_tool_calls(message: Any) -> list[ToolCall]:
    raw_calls = getattr(message, "tool_calls", None) or []
    parsed: list[ToolCall] = []
    for raw in raw_calls:
        function = getattr(raw, "function", None)
        if function is None:
            continue
        raw_arguments = getattr(function, "arguments", "") or "{}"
        try:
            arguments = json.loads(raw_arguments)
        except (TypeError, ValueError):
            # Malformed JSON must not raise: the loop turns it into an error
            # tool result so the model can correct itself on the next turn.
            arguments = {}
        if not isinstance(arguments, dict):
            arguments = {"value": arguments}
        parsed.append(
            ToolCall(
                id=str(getattr(raw, "id", "") or ""),
                name=str(getattr(function, "name", "") or ""),
                arguments=arguments,
            )
        )
    return parsed


def _extract_reasoning(message: Any) -> str:
    for attribute in ("reasoning_content", "reasoning"):
        value = getattr(message, attribute, None)
        if isinstance(value, str) and value:
            return value
    return ""


def _assistant_raw_message(
    message: Any, text: str, tool_calls: Sequence[ToolCall]
) -> dict[str, Any] | None:
    if not tool_calls:
        return None
    return {
        "role": "assistant",
        "content": text or None,
        "tool_calls": [
            {
                "id": call.id,
                "type": "function",
                "function": {
                    "name": _wire_name(call.name),
                    "arguments": json.dumps(call.arguments),
                },
            }
            for call in tool_calls
        ],
    }


class OpenAiProvider(LlmProvider):
    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        base_url: str | None = None,
        client: object | None = None,
    ) -> None:
        self._api_key = api_key
        self._model = model
        self._base_url = base_url or None
        self._client = client
        self._log = get_logger(component="llm.openai", model=model)

    async def complete(
        self,
        messages: Sequence[LlmMessage],
        *,
        route: LlmRoute = "cloud",
        temperature: float = 0.0,
        max_tokens: int | None = None,
        options: LlmCallOptions | None = None,
    ) -> LlmResponse:
        client = self._resolve_client()
        payload = [_to_openai_message(message) for message in messages]
        kwargs: dict[str, Any] = {
            "model": self._model,
            "messages": payload,
        }
        if not _model_uses_completion_tokens_param(self._model):
            kwargs["temperature"] = temperature
        if max_tokens is not None:
            if _model_uses_completion_tokens_param(self._model):
                kwargs["max_completion_tokens"] = max_tokens
            else:
                kwargs["max_tokens"] = max_tokens
        extra_body: dict[str, Any] = {}
        if options is not None:
            if options.tools:
                kwargs["tools"] = [_to_openai_tool(tool) for tool in options.tools]
                kwargs["tool_choice"] = options.tool_choice or "auto"
                if options.parallel_tool_calls is not None:
                    kwargs["parallel_tool_calls"] = options.parallel_tool_calls
            if options.reasoning_effort:
                extra_body["reasoning_effort"] = options.reasoning_effort
            extra_body.update(options.extra_body)
        if extra_body:
            kwargs["extra_body"] = extra_body
        started = time.perf_counter()
        response = await self._create_completion(client, kwargs)
        latency_ms = int((time.perf_counter() - started) * 1000)
        choice = response.choices[0]
        message = choice.message
        text = message.content or ""
        tool_calls = _parse_tool_calls(message)
        usage = getattr(response, "usage", None)
        prompt_tokens = getattr(usage, "prompt_tokens", 0) if usage else 0
        completion_tokens = getattr(usage, "completion_tokens", 0) if usage else 0
        self._log.info(
            "llm.openai.complete",
            route=route,
            latency_ms=latency_ms,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            tool_calls=len(tool_calls),
        )
        return LlmResponse(
            text=text,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            route=route,
            model=self._model,
            tool_calls=tool_calls,
            stop_reason=str(getattr(choice, "finish_reason", "") or ""),
            reasoning=_extract_reasoning(message),
            raw_message=_assistant_raw_message(message, text, tool_calls),
        )

    async def _create_completion(self, client: Any, kwargs: dict[str, Any]) -> Any:
        try:
            return await client.chat.completions.create(**kwargs)
        except Exception as exc:  # pragma: no cover - defensive remap
            message = str(exc)
            param = _extract_unsupported_param(message)
            if param == "max_tokens" and "max_tokens" in kwargs:
                fallback = dict(kwargs)
                fallback["max_completion_tokens"] = fallback.pop("max_tokens")
                self._log.info(
                    "llm.openai.retry_with_max_completion_tokens",
                    model=self._model,
                )
                return await client.chat.completions.create(**fallback)
            if param == "max_completion_tokens" and "max_completion_tokens" in kwargs:
                fallback = dict(kwargs)
                fallback["max_tokens"] = fallback.pop("max_completion_tokens")
                self._log.info(
                    "llm.openai.retry_with_max_tokens",
                    model=self._model,
                )
                return await client.chat.completions.create(**fallback)
            if param == "temperature" and "temperature" in kwargs:
                fallback = dict(kwargs)
                fallback.pop("temperature", None)
                self._log.info(
                    "llm.openai.retry_without_temperature",
                    model=self._model,
                )
                return await client.chat.completions.create(**fallback)
            # reasoning_effort travels in extra_body, so it is not a top-level
            # kwarg. Older Solar builds and vLLM servers reject it outright.
            if param == "reasoning_effort" and "reasoning_effort" in kwargs.get("extra_body", {}):
                fallback = dict(kwargs)
                extra = dict(fallback["extra_body"])
                extra.pop("reasoning_effort", None)
                if extra:
                    fallback["extra_body"] = extra
                else:
                    fallback.pop("extra_body")
                self._log.info(
                    "llm.openai.retry_without_reasoning_effort",
                    model=self._model,
                )
                return await client.chat.completions.create(**fallback)
            if param == "parallel_tool_calls" and "parallel_tool_calls" in kwargs:
                fallback = dict(kwargs)
                fallback.pop("parallel_tool_calls", None)
                self._log.info(
                    "llm.openai.retry_without_parallel_tool_calls",
                    model=self._model,
                )
                return await client.chat.completions.create(**fallback)
            raise

    def _resolve_client(self) -> Any:
        if self._client is not None:
            return self._client
        from openai import AsyncOpenAI

        self._client = AsyncOpenAI(api_key=self._api_key, base_url=self._base_url)
        return self._client
