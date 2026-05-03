"""Typed configuration loaded from environment variables (12-Factor)."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class GitHubSettings(BaseSettings):
    webhook_secret: str = "change-me"
    app_token: str = ""
    allowed_repos: list[str] = Field(default_factory=list)
    trigger_label: str = "patch-machine"

    model_config = SettingsConfigDict(env_prefix="PM_GITHUB_")


class DiscordSettings(BaseSettings):
    bot_token: str = ""
    guild_allowlist: list[str] = Field(default_factory=list)
    channel_map_path: Path = Path("./config/channel_map.yml")

    model_config = SettingsConfigDict(env_prefix="PM_DISCORD_")


class LlmSettings(BaseSettings):
    default_route: Literal["cloud", "local"] = "cloud"
    provider: Literal["openai", "vllm", "ollama", "anthropic", "gemini", "fake"] = "openai"
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"
    openai_base_url: str = ""
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-3-5-sonnet-latest"
    gemini_api_key: str = ""
    gemini_model: str = "gemini-1.5-flash"
    vllm_base_url: str = "http://localhost:8000/v1"
    vllm_model: str = "Qwen/Qwen3-4B"
    vllm_mode: Literal["embedded", "http"] = "embedded"
    vllm_dtype: Literal["auto", "bfloat16", "float16"] = "bfloat16"
    vllm_max_model_len: int = 8192
    vllm_gpu_memory_utilization: float = 0.9
    vllm_enforce_eager: bool = False
    vllm_trust_remote_code: bool = True
    vllm_preload_on_startup: bool = True
    vllm_worker_multiproc_method: Literal["spawn", "fork"] = "spawn"
    local_base_url: str = "http://localhost:8000/v1"

    model_config = SettingsConfigDict(env_prefix="PM_")


class Settings(BaseSettings):
    """Top-level settings container.

    Nested sub-settings each read their own ``PM_*`` prefix directly; we only
    need to compose them once at startup and pass the whole object into the DI
    container.
    """

    env: Literal["development", "production", "test"] = "development"
    log_level: str = "INFO"
    workspace_dir: Path = Path("./.pm_workspaces")
    archive_dir: Path = Path("./archive")
    http_host: str = "0.0.0.0"
    http_port: int = 8080
    event_queue_size: int = 100
    max_self_correction: int = 2
    secret_key: str = ""

    github: GitHubSettings = Field(default_factory=GitHubSettings)
    discord: DiscordSettings = Field(default_factory=DiscordSettings)
    llm: LlmSettings = Field(default_factory=LlmSettings)

    model_config = SettingsConfigDict(
        env_prefix="PM_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


def load_settings() -> Settings:
    """Factory that materializes settings; kept as a function for easy stubbing."""
    return Settings()
