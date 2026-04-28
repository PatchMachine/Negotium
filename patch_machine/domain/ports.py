"""Port interfaces (Hexagonal architecture).

Upstream ports are driven by external systems (ingestion sources) and push
``IssueEvent`` into the domain. Downstream ports are driven by the domain to
reach external systems (LLM, Git, filesystem archive, messaging surfaces).

All adapters in ``patch_machine.adapters`` implement one of these protocols.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Sequence
from pathlib import Path
from typing import Protocol, runtime_checkable

from patch_machine.domain.entities import (
    IssueEvent,
    LlmRoute,
    PatchProposal,
    RepoRef,
    ReviewVerdict,
    WorkSpec,
)


@runtime_checkable
class IssueSource(Protocol):
    """Upstream port: yields normalized issue events from a channel."""

    async def listen(self) -> AsyncIterator[IssueEvent]:  # pragma: no cover - interface
        ...


@runtime_checkable
class CodeRepository(Protocol):
    """Access to a source repository snapshot."""

    def snapshot(self, repo: RepoRef) -> Path: ...

    def read_file(self, repo: RepoRef, relative_path: str) -> str: ...

    def list_paths(self, repo: RepoRef, *, globs: Sequence[str] | None = None) -> list[Path]: ...


class LlmResponse:
    """Value object for an LLM completion. Kept simple to avoid coupling to any SDK."""

    __slots__ = ("completion_tokens", "model", "prompt_tokens", "route", "text")

    def __init__(
        self,
        *,
        text: str,
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
        route: LlmRoute = "cloud",
        model: str = "",
    ) -> None:
        self.text = text
        self.prompt_tokens = prompt_tokens
        self.completion_tokens = completion_tokens
        self.route = route
        self.model = model


class LlmMessage:
    """Minimal chat message structure usable across providers."""

    __slots__ = ("content", "role")

    def __init__(self, role: str, content: str) -> None:
        self.role = role
        self.content = content


@runtime_checkable
class LlmProvider(Protocol):
    """Downstream port: unified chat-completion interface."""

    async def complete(
        self,
        messages: Sequence[LlmMessage],
        *,
        route: LlmRoute = "cloud",
        temperature: float = 0.0,
        max_tokens: int | None = None,
    ) -> LlmResponse: ...


@runtime_checkable
class ArchiveStore(Protocol):
    """Persistence of MD logs, indexes and rolling status file."""

    def write_log(
        self,
        *,
        issue: IssueEvent,
        workspec: WorkSpec,
        proposal: PatchProposal,
        verdict: ReviewVerdict,
        status: str,
    ) -> Path: ...

    def update_indexes(
        self,
        *,
        log_path: Path,
        keywords: Sequence[str],
        modules: Sequence[str],
        author: str,
    ) -> None: ...

    def update_status(self, *, summary_md: str) -> None: ...

    def read_recent(self, k: int = 5) -> list[Path]: ...

    def search_by_keywords(self, keywords: Sequence[str], *, limit: int = 20) -> list[Path]: ...


@runtime_checkable
class Notifier(Protocol):
    """Downstream port: reply to the originating channel."""

    async def reply(self, event: IssueEvent, markdown: str) -> None: ...
