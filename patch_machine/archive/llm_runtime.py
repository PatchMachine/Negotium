"""Persistent runtime switches for chat-oriented LLM providers."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

import portalocker

LlmProviderName = Literal["vllm", "openai", "anthropic", "gemini", "fake"]
LlmRuntimeRoute = Literal["local", "api"]


@dataclass(frozen=True)
class LlmRuntimeConfig:
    local_enabled: bool = True
    api_enabled: bool = True
    default_route: LlmRuntimeRoute = "local"
    default_provider: LlmProviderName = "vllm"
    local_model: str = "Qwen/Qwen3-4B"

    @classmethod
    def from_mapping(cls, payload: dict[str, Any]) -> LlmRuntimeConfig:
        route = payload.get("default_route") or "local"
        provider = payload.get("default_provider") or "vllm"
        if route not in {"local", "api"}:
            route = "local"
        if provider not in {"vllm", "openai", "anthropic", "gemini", "fake"}:
            provider = "vllm"
        return cls(
            local_enabled=bool(payload.get("local_enabled", True)),
            api_enabled=bool(payload.get("api_enabled", True)),
            default_route=route,
            default_provider=provider,
            local_model=str(payload.get("local_model") or "Qwen/Qwen3-4B"),
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "local_enabled": self.local_enabled,
            "api_enabled": self.api_enabled,
            "default_route": self.default_route,
            "default_provider": self.default_provider,
            "local_model": self.local_model,
        }


class LlmRuntimeStore:
    """File-backed runtime flags for the local console."""

    def __init__(self, archive_dir: Path) -> None:
        self._path = archive_dir / "llm_runtime.json"

    @property
    def path(self) -> Path:
        return self._path

    def read(self) -> LlmRuntimeConfig:
        if not self._path.exists():
            return LlmRuntimeConfig()
        raw = self._path.read_text(encoding="utf-8")
        if not raw.strip():
            return LlmRuntimeConfig()
        payload = json.loads(raw)
        if not isinstance(payload, dict):
            raise ValueError("LLM runtime config must be a JSON object")
        return LlmRuntimeConfig.from_mapping(payload)

    def write(self, config: LlmRuntimeConfig) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            **config.to_dict(),
            "updated_at": datetime.now(UTC).isoformat(),
        }
        rendered = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
        with portalocker.Lock(self._path, "w", encoding="utf-8", timeout=5) as fh:
            fh.write(rendered)
