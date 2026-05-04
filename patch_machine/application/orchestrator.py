"""Use-case orchestrator.

Reads a ``DomainEvent`` from the bus, runs the context builder, executes the
LangGraph agent pipeline, persists the MD log and invokes notifiers.
"""

from __future__ import annotations

from dataclasses import dataclass

from patch_machine.agents.graph import AgentGraph, GraphState
from patch_machine.app.services.issue_memory_service import capture_issue_event
from patch_machine.application.event_bus import EventBus
from patch_machine.archive.issue_memory import IssueMemoryStore
from patch_machine.archive.operations_memory import OperationsMemoryStore
from patch_machine.archive.writer import ArchiveWriter
from patch_machine.context.md_retriever import MarkdownRetriever
from patch_machine.context.repo_snapshot import RepoSnapshotService
from patch_machine.domain.entities import IssueEvent
from patch_machine.domain.ports import Notifier
from patch_machine.observability import get_logger


@dataclass
class Orchestrator:
    """Composition of the domain pipeline. All collaborators are injected."""

    graph: AgentGraph
    repo_snapshot: RepoSnapshotService
    retriever: MarkdownRetriever
    operations_memory: OperationsMemoryStore
    archive: ArchiveWriter
    issue_memory: IssueMemoryStore
    notifiers: dict[str, Notifier]

    def __post_init__(self) -> None:
        self._log = get_logger(component="orchestrator")

    async def handle(self, event: IssueEvent) -> None:
        log = self._log.bind(event_id=str(event.event_id), source=event.source)
        log.info("orchestrator.start")
        capture = capture_issue_event(self.issue_memory, event)
        log.info(
            "orchestrator.issue_memory_captured",
            cluster_id=capture["cluster"]["id"],
            issue_id=capture["canonical_issue"]["id"],
        )

        snapshot_path = self.repo_snapshot.ensure(event.repo)
        related = self.retriever.find_related(event, limit=5)
        operations_memory_md = self.operations_memory.read().to_markdown()

        state: GraphState = {
            "issue": event,
            "snapshot_path": str(snapshot_path),
            "related_logs": [str(p) for p in related],
            "operations_memory_md": operations_memory_md,
            "workspec_md": "",
            "diff": "",
            "review_verdict": "",
            "review_md": "",
            "iteration": 0,
        }

        result = await self.graph.run(state)

        log_path = self.archive.write_from_state(event=event, state=result)
        log.info("orchestrator.log_written", path=str(log_path))

        notifier = self.notifiers.get(event.source)
        if notifier is None:
            log.warning("orchestrator.no_notifier", source=event.source)
            return

        summary = self._build_summary(result, log_path)
        await notifier.reply(event, summary)
        log.info("orchestrator.done")

    async def run_forever(self, bus: EventBus) -> None:
        async for envelope in bus.consume():
            try:
                await self.handle(envelope.payload)
            except Exception:
                self._log.exception(
                    "orchestrator.error",
                    event_id=str(envelope.payload.event_id),
                    attempt=envelope.attempt,
                )
                await bus.retry(envelope)

    @staticmethod
    def _build_summary(state: GraphState, log_path: object) -> str:
        diff = state.get("diff") or ""
        verdict = state.get("review_verdict") or "unknown"
        header = f"**Patch Machine 제안** — 검토 결과: `{verdict}`\n\n"
        if diff:
            header += (
                "```diff\n"
                + diff[:4000]
                + ("\n... (truncated)" if len(diff) > 4000 else "")
                + "\n```\n"
            )
        header += f"\n전체 근거: `{log_path}`"
        return header
