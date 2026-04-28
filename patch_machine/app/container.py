"""Composition root — wires adapters into the domain."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from patch_machine.adapters.ingestion.channel_map import ChannelMap
from patch_machine.adapters.ingestion.discord_bot import DiscordBotAdapter
from patch_machine.adapters.ingestion.github_webhook import GitHubWebhookRouter
from patch_machine.adapters.llm.fake_adapter import FakeLlmProvider
from patch_machine.adapters.llm.gateway import LlmGateway
from patch_machine.adapters.llm.openai_adapter import OpenAiProvider
from patch_machine.adapters.notifier.discord_notifier import DiscordNotifier
from patch_machine.adapters.notifier.github_notifier import GitHubNotifier
from patch_machine.agents.developer import DeveloperAgent
from patch_machine.agents.graph import AgentGraph
from patch_machine.agents.pm import PmAgent
from patch_machine.agents.reviewer import ReviewerAgent
from patch_machine.app.settings import Settings, load_settings
from patch_machine.application.event_bus import EventBus
from patch_machine.application.orchestrator import Orchestrator
from patch_machine.archive.writer import ArchiveWriter
from patch_machine.context.md_retriever import MarkdownRetriever
from patch_machine.context.repo_snapshot import RepoSnapshotService
from patch_machine.domain.ports import LlmProvider, Notifier
from patch_machine.observability import AgentMetrics, configure_logging, get_logger


@dataclass
class Container:
    settings: Settings
    bus: EventBus
    archive: ArchiveWriter
    repo_snapshot: RepoSnapshotService
    retriever: MarkdownRetriever
    llm: LlmProvider
    graph: AgentGraph
    discord: DiscordBotAdapter
    github_router: GitHubWebhookRouter
    orchestrator: Orchestrator
    metrics: AgentMetrics = field(default_factory=AgentMetrics)

    @classmethod
    def build(cls, settings: Settings | None = None) -> Container:
        settings = settings or load_settings()
        configure_logging(settings.log_level)
        log = get_logger(component="container")

        bus = EventBus(max_size=settings.event_queue_size)

        archive = ArchiveWriter(settings.archive_dir)
        repo_snapshot = RepoSnapshotService(settings.workspace_dir)
        retriever = MarkdownRetriever(
            archive_root=settings.archive_dir,
            index=archive.index,
        )

        metrics = AgentMetrics()
        llm = cls._build_llm(settings)

        pm = PmAgent(llm, metrics=metrics)
        developer = DeveloperAgent(llm, metrics=metrics)
        reviewer = ReviewerAgent(llm, metrics=metrics)
        graph = AgentGraph(
            pm=pm,
            developer=developer,
            reviewer=reviewer,
            max_iterations=settings.max_self_correction,
        )

        channel_map = ChannelMap.load(settings.discord.channel_map_path)
        discord = DiscordBotAdapter(
            settings=settings.discord,
            bus=bus,
            channel_map=channel_map,
        )
        github_router = GitHubWebhookRouter(bus=bus, settings=settings.github)

        notifiers: dict[str, Notifier] = {
            "github": GitHubNotifier(token=settings.github.app_token),
            "discord": DiscordNotifier(sender=discord),
        }

        orchestrator = Orchestrator(
            graph=graph,
            repo_snapshot=repo_snapshot,
            retriever=retriever,
            archive=archive,
            notifiers=notifiers,
        )

        log.info(
            "container.built",
            env=settings.env,
            provider=settings.llm.provider,
        )
        return cls(
            settings=settings,
            bus=bus,
            archive=archive,
            repo_snapshot=repo_snapshot,
            retriever=retriever,
            llm=llm,
            graph=graph,
            discord=discord,
            github_router=github_router,
            orchestrator=orchestrator,
            metrics=metrics,
        )

    @staticmethod
    def _build_llm(settings: Settings) -> LlmProvider:
        cloud: LlmProvider
        if settings.llm.provider == "openai":
            cloud = OpenAiProvider(
                api_key=settings.llm.openai_api_key,
                model=settings.llm.openai_model,
                base_url=settings.llm.openai_base_url or None,
            )
        else:
            cloud = FakeLlmProvider()
        return LlmGateway(cloud=cloud, default_route=settings.llm.default_route)


def build_container(
    *,
    settings: Settings | None = None,
    overrides: dict[str, Any] | None = None,
) -> Container:
    container = Container.build(settings)
    if overrides:
        for attr, value in overrides.items():
            setattr(container, attr, value)
    return container
