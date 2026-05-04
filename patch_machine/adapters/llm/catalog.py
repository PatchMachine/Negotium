"""Provider metadata and model catalog helpers for external LLM APIs."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal

import httpx

ProviderName = Literal["openai", "anthropic", "gemini", "vllm"]


@dataclass(frozen=True)
class ProviderMetadata:
    id: ProviderName
    label: str
    default_base_url: str
    fallback_models: tuple[str, ...]


PROVIDERS: dict[str, ProviderMetadata] = {
    "openai": ProviderMetadata(
        id="openai",
        label="OpenAI / GPT",
        default_base_url="https://api.openai.com/v1",
        fallback_models=(
            "gpt-5.5-pro",
            "gpt-5.4",
            "gpt-5.4-mini",
            "gpt-5-nano",
            "gpt-4.1",
            "gpt-4.1-mini",
            "gpt-4o",
            "gpt-4o-mini",
            "o4-mini",
        ),
    ),
    "anthropic": ProviderMetadata(
        id="anthropic",
        label="Anthropic / Claude",
        default_base_url="https://api.anthropic.com/v1",
        fallback_models=(
            "claude-opus-4-7",
            "claude-sonnet-4-6",
            "claude-haiku-4-5",
            "claude-3-7-sonnet-latest",
            "claude-3-5-sonnet-latest",
            "claude-3-5-haiku-latest",
        ),
    ),
    "gemini": ProviderMetadata(
        id="gemini",
        label="Google / Gemini",
        default_base_url="https://generativelanguage.googleapis.com/v1beta",
        fallback_models=(
            "gemini-3.1-pro",
            "gemini-3-flash",
            "gemini-3-flash-lite",
            "gemini-2.0-flash",
            "gemini-1.5-pro",
            "gemini-1.5-flash",
        ),
    ),
    "vllm": ProviderMetadata(
        id="vllm",
        label="vLLM / Local HTTP",
        default_base_url="http://localhost:8000/v1",
        fallback_models=("Qwen/Qwen3-4B",),
    ),
}


def require_provider(provider: str) -> ProviderMetadata:
    try:
        return PROVIDERS[provider]
    except KeyError as exc:
        raise ValueError(f"unsupported LLM provider: {provider}") from exc


def default_base_url(provider: str, *, vllm_base_url: str = "") -> str:
    metadata = require_provider(provider)
    if provider == "vllm" and vllm_base_url.strip():
        return vllm_base_url.strip().rstrip("/")
    return metadata.default_base_url


async def list_models(
    provider: str,
    *,
    api_key: str = "",
    base_url: str = "",
) -> dict[str, object]:
    metadata = require_provider(provider)
    refreshed_at = datetime.now(UTC).isoformat()
    requires_api_key = provider in {"openai", "anthropic", "gemini"}
    if not api_key and requires_api_key:
        return _fallback_payload(
            metadata,
            reason="api key is not configured",
            refreshed_at=refreshed_at,
            configured=False,
            requires_api_key=requires_api_key,
        )
    try:
        if provider == "openai":
            models = await _openai_models(
                api_key=api_key, base_url=base_url or metadata.default_base_url
            )
        elif provider == "anthropic":
            models = await _anthropic_models(
                api_key=api_key, base_url=base_url or metadata.default_base_url
            )
        elif provider == "gemini":
            models = await _gemini_models(
                api_key=api_key, base_url=base_url or metadata.default_base_url
            )
        elif provider == "vllm":
            models = await _openai_compatible_models(
                base_url=base_url or metadata.default_base_url, api_key=api_key
            )
        else:
            models = []
        if models:
            return {
                "provider": provider,
                "models": models,
                "source": "live",
                "refreshed_at": refreshed_at,
                "reason": "",
                "configured": bool(api_key) or not requires_api_key,
                "requires_api_key": requires_api_key,
            }
    except (httpx.HTTPError, KeyError, TypeError, ValueError) as exc:
        return _fallback_payload(
            metadata,
            reason=str(exc),
            refreshed_at=refreshed_at,
            configured=bool(api_key) or not requires_api_key,
            requires_api_key=requires_api_key,
        )
    return _fallback_payload(
        metadata,
        reason="live model list is unavailable",
        refreshed_at=refreshed_at,
        configured=bool(api_key) or not requires_api_key,
        requires_api_key=requires_api_key,
    )


def provider_payload(*, vllm_base_url: str = "") -> list[dict[str, object]]:
    return [
        {
            "provider": provider,
            "label": metadata.label,
            "base_url": default_base_url(provider, vllm_base_url=vllm_base_url),
            "base_url_source": "system",
            "fallback_models": list(metadata.fallback_models),
        }
        for provider, metadata in PROVIDERS.items()
    ]


def _fallback_payload(
    metadata: ProviderMetadata,
    *,
    reason: str,
    refreshed_at: str,
    configured: bool = False,
    requires_api_key: bool = True,
) -> dict[str, object]:
    return {
        "provider": metadata.id,
        "models": list(metadata.fallback_models),
        "source": "fallback",
        "refreshed_at": refreshed_at,
        "reason": reason,
        "configured": configured,
        "requires_api_key": requires_api_key,
    }


async def _openai_models(*, api_key: str, base_url: str) -> list[str]:
    async with httpx.AsyncClient(timeout=20) as client:
        response = await client.get(
            f"{base_url.rstrip('/')}/models",
            headers={"Authorization": f"Bearer {api_key}"},
        )
        response.raise_for_status()
    return sorted(
        model["id"]
        for model in response.json().get("data", [])
        if isinstance(model, dict) and isinstance(model.get("id"), str)
    )


async def _openai_compatible_models(*, base_url: str, api_key: str) -> list[str]:
    headers = {"Authorization": f"Bearer {api_key or 'EMPTY'}"}
    async with httpx.AsyncClient(timeout=20) as client:
        response = await client.get(f"{base_url.rstrip('/')}/models", headers=headers)
        response.raise_for_status()
    return sorted(
        model["id"]
        for model in response.json().get("data", [])
        if isinstance(model, dict) and isinstance(model.get("id"), str)
    )


async def _anthropic_models(*, api_key: str, base_url: str) -> list[str]:
    async with httpx.AsyncClient(timeout=20) as client:
        response = await client.get(
            f"{base_url.rstrip('/')}/models",
            params={"limit": 100},
            headers={
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
            },
        )
        response.raise_for_status()
    return sorted(
        model["id"]
        for model in response.json().get("data", [])
        if isinstance(model, dict) and isinstance(model.get("id"), str)
    )


async def _gemini_models(*, api_key: str, base_url: str) -> list[str]:
    async with httpx.AsyncClient(timeout=20) as client:
        response = await client.get(f"{base_url.rstrip('/')}/models", params={"key": api_key})
        response.raise_for_status()
    models: list[str] = []
    for item in response.json().get("models", []):
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "").removeprefix("models/")
        methods = item.get("supportedGenerationMethods") or []
        if name and "generateContent" in methods:
            models.append(name)
    return sorted(models)
