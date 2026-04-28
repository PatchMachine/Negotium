"""Domain layer: framework/IO-agnostic core entities, value objects, and ports."""

from patch_machine.domain.entities import (
    IssueEvent,
    PatchProposal,
    RepoRef,
    ReviewVerdict,
    WorkSpec,
)
from patch_machine.domain.ports import (
    ArchiveStore,
    CodeRepository,
    IssueSource,
    LlmProvider,
    Notifier,
)

__all__ = [
    "ArchiveStore",
    "CodeRepository",
    "IssueEvent",
    "IssueSource",
    "LlmProvider",
    "Notifier",
    "PatchProposal",
    "RepoRef",
    "ReviewVerdict",
    "WorkSpec",
]
