"""vLLM OpenAI-compatible chat completion adapter."""

from __future__ import annotations

import asyncio
import json
import time
from collections.abc import Sequence
from typing import Any

import httpx

from negotium.adapters.llm.multimodal import to_text
from negotium.domain.entities import LlmRoute
from negotium.domain.ports import (
    LlmCallOptions,
    LlmMessage,
    LlmProvider,
    LlmResponse,
    ToolCall,
)
from negotium.observability import get_logger

# httpx default read timeout is too small for first-request / long generations
_DEFAULT_TIMEOUT = httpx.Timeout(connect=10.0, read=300.0, write=30.0, pool=10.0)


class VllmConnectionError(RuntimeError):
    """Raised when the vLLM HTTP server stays unreachable after startup retries."""


def _to_vllm_message(message: LlmMessage) -> dict[str, Any]:
    if message.role == "assistant" and message.raw:
        return dict(message.raw)
    if message.role == "tool":
        return {
            "role": "tool",
            "tool_call_id": message.tool_call_id,
            "content": message.content if isinstance(message.content, str) else "",
        }
    payload: dict[str, Any] = {"role": message.role, "content": to_text(message.content)}
    if message.tool_calls:
        payload["tool_calls"] = [
            {
                "id": call.id,
                "type": "function",
                "function": {"name": call.name, "arguments": json.dumps(call.arguments)},
            }
            for call in message.tool_calls
        ]
    return payload


def _parse_vllm_tool_calls(message: dict[str, Any]) -> list[ToolCall]:
    parsed: list[ToolCall] = []
    for raw in message.get("tool_calls") or []:
        if not isinstance(raw, dict):
            continue
        function = raw.get("function") or {}
        try:
            arguments = json.loads(function.get("arguments") or "{}")
        except (TypeError, ValueError):
            arguments = {}
        if not isinstance(arguments, dict):
            arguments = {"value": arguments}
        parsed.append(
            ToolCall(
                id=str(raw.get("id") or ""),
                name=str(function.get("name") or ""),
                arguments=arguments,
            )
        )
    return parsed


class VllmProvider(LlmProvider):
    def __init__(
        self,
        *,
        base_url: str,
        model: str = "Qwen/Qwen3-4B",
        api_key: str = "EMPTY",
        client: httpx.AsyncClient | None = None,
        startup_wait_seconds: float = 5.0,
        retry_interval_seconds: float = 2.0,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._api_key = api_key
        self._client = client
        self._startup_wait_seconds = startup_wait_seconds
        self._retry_interval_seconds = retry_interval_seconds
        self._log = get_logger(component="llm.vllm", model=model)

    async def complete(
        self,
        messages: Sequence[LlmMessage],
        *,
        route: LlmRoute = "local",
        temperature: float = 0.0,
        max_tokens: int | None = None,
        options: LlmCallOptions | None = None,
    ) -> LlmResponse:
        payload: dict[str, Any] = {
            "model": self._model,
            "messages": [_to_vllm_message(message) for message in messages],
            "temperature": temperature,
        }
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens
        if options is not None:
            if options.tools:
                # Requires the server to be started with
                # --enable-auto-tool-choice and a matching --tool-call-parser.
                payload["tools"] = [
                    {
                        "type": "function",
                        "function": {
                            "name": tool.name,
                            "description": tool.description,
                            "parameters": tool.parameters,
                        },
                    }
                    for tool in options.tools
                ]
                payload["tool_choice"] = options.tool_choice or "auto"
            if options.reasoning_effort:
                payload["reasoning_effort"] = options.reasoning_effort
            payload.update(options.extra_body)

        started = time.perf_counter()
        client = self._resolve_client()
        deadline = time.monotonic() + self._startup_wait_seconds
        while True:
            try:
                response = await client.post(
                    f"{self._base_url}/chat/completions",
                    headers={"Authorization": f"Bearer {self._api_key}"},
                    json=payload,
                )
                response.raise_for_status()
                break
            except (httpx.ConnectError, httpx.ConnectTimeout) as exc:
                if time.monotonic() >= deadline:
                    self._log.warning(
                        "llm.vllm.unreachable",
                        base_url=self._base_url,
                        error=str(exc),
                    )
                    raise VllmConnectionError(
                        f"vLLM HTTP 서버({self._base_url})에 연결할 수 없습니다. "
                        "로컬 GPU 임베드 모드는 Docker 백엔드가 아니라 호스트에서 "
                        "`NG_VLLM_MODE=embedded uv run negotium serve`로 실행해야 합니다."
                    ) from exc
                self._log.info(
                    "llm.vllm.waiting_for_server",
                    retry_in_s=self._retry_interval_seconds,
                    base_url=self._base_url,
                )
                await asyncio.sleep(self._retry_interval_seconds)
            except httpx.HTTPStatusError as exc:
                # Cold start: engine may return 5xx while weights load
                if exc.response.status_code >= 500 and time.monotonic() < deadline:
                    self._log.info(
                        "llm.vllm.server_error_retry",
                        status=exc.response.status_code,
                        retry_in_s=self._retry_interval_seconds,
                    )
                    await asyncio.sleep(self._retry_interval_seconds)
                    continue
                raise

        data = response.json()
        latency_ms = int((time.perf_counter() - started) * 1000)
        choice = data["choices"][0]
        message = choice.get("message") or {}
        text = message.get("content") or ""
        tool_calls = _parse_vllm_tool_calls(message)
        usage = data.get("usage") or {}
        self._log.info(
            "llm.vllm.complete", route=route, latency_ms=latency_ms, tool_calls=len(tool_calls)
        )
        return LlmResponse(
            text=text,
            prompt_tokens=int(usage.get("prompt_tokens") or 0),
            completion_tokens=int(usage.get("completion_tokens") or 0),
            route=route,
            model=self._model,
            tool_calls=tool_calls,
            stop_reason=str(choice.get("finish_reason") or ""),
            reasoning=str(message.get("reasoning_content") or message.get("reasoning") or ""),
            raw_message=dict(message) if tool_calls else None,
        )

    def _resolve_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=_DEFAULT_TIMEOUT)
        return self._client
