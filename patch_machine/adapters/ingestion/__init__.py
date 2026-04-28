"""Ingestion adapters normalize external events into ``IssueEvent``."""

from patch_machine.adapters.ingestion.discord_bot import DiscordBotAdapter
from patch_machine.adapters.ingestion.github_webhook import (
    GitHubWebhookRouter,
    normalize_github_payload,
)

__all__ = [
    "DiscordBotAdapter",
    "GitHubWebhookRouter",
    "normalize_github_payload",
]
