"""OpenAI chat completion adapter."""

from __future__ import annotations

import time
from collections.abc import Sequence
from typing import Any

from patch_machine.domain.entities import LlmRoute
from patch_machine.domain.ports import LlmMessage, LlmProvider, LlmResponse
from patch_machine.observability import get_logger


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
    ) -> LlmResponse:
        client = self._resolve_client()
        payload = [{"role": m.role, "content": m.content} for m in messages]
        started = time.perf_counter()
        response = await client.chat.completions.create(
            model=self._model,
            messages=payload,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        latency_ms = int((time.perf_counter() - started) * 1000)
        choice = response.choices[0]
        text = choice.message.content or ""
        usage = getattr(response, "usage", None)
        prompt_tokens = getattr(usage, "prompt_tokens", 0) if usage else 0
        completion_tokens = getattr(usage, "completion_tokens", 0) if usage else 0
        self._log.info(
            "llm.openai.complete",
            route=route,
            latency_ms=latency_ms,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
        )
        return LlmResponse(
            text=text,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            route=route,
            model=self._model,
        )

    def _resolve_client(self) -> Any:
        if self._client is not None:
            return self._client
        from openai import AsyncOpenAI

        self._client = AsyncOpenAI(api_key=self._api_key, base_url=self._base_url)
        return self._client
