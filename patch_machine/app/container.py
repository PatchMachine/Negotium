"""Composition root — wires adapters into the domain."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from patch_machine.adapters.ingestion.channel_map import ChannelMap
from patch_machine.adapters.ingestion.discord_bot import DiscordBotAdapter
from patch_machine.adapters.ingestion.github_webhook import GitHubWebhookRouter
from patch_machine.adapters.llm.anthropic_adapter import AnthropicProvider
from patch_machine.adapters.llm.fake_adapter import FakeLlmProvider
from patch_machine.adapters.llm.gateway import LlmGateway
from patch_machine.adapters.llm.gemini_adapter import GeminiProvider
from patch_machine.adapters.llm.openai_adapter import OpenAiProvider
from patch_machine.adapters.llm.vllm_adapter import VllmProvider
from patch_machine.adapters.llm.vllm_embedded_adapter import VllmEmbeddedProvider
from patch_machine.adapters.notifier.discord_notifier import DiscordNotifier
from patch_machine.adapters.notifier.github_notifier import GitHubNotifier
from patch_machine.agents.developer import DeveloperAgent
from patch_machine.agents.graph import AgentGraph
from patch_machine.agents.pm import PmAgent
from patch_machine.agents.reviewer import ReviewerAgent
from patch_machine.app.settings import Settings, load_settings
from patch_machine.application.event_bus import EventBus
from patch_machine.application.orchestrator import Orchestrator
from patch_machine.archive.access_control import AccessControlStore
from patch_machine.archive.agent_execution import AgentExecutionStore
from patch_machine.archive.audit_log import AuditLogStore
from patch_machine.archive.auth_store import AuthStore
from patch_machine.archive.context_compressor import CompressedContextStore
from patch_machine.archive.conversation_store import ConversationStore
from patch_machine.archive.deletion_requests import DeletionRequestStore
from patch_machine.archive.llm_runtime import LlmRuntimeStore
from patch_machine.archive.memory_schema import MemorySchemaStore
from patch_machine.archive.operations_memory import OperationsMemoryStore
from patch_machine.archive.permanent_memory import PermanentMemoryStore
from patch_machine.archive.secret_store import SecretStore
from patch_machine.archive.uploads import UploadStore
from patch_machine.archive.volatile_memory import VolatileMemoryStore
from patch_machine.archive.work_memory import WorkMemoryStore, WorkScheduleStore
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
    operations_memory: OperationsMemoryStore
    llm_runtime: LlmRuntimeStore
    access_control: AccessControlStore
    agent_execution: AgentExecutionStore
    audit_log: AuditLogStore
    auth_store: AuthStore
    compressed_context: CompressedContextStore
    conversations: ConversationStore
    deletion_requests: DeletionRequestStore
    memory_schema: MemorySchemaStore
    permanent_memory: PermanentMemoryStore
    secret_store: SecretStore
    uploads: UploadStore
    volatile_memory: VolatileMemoryStore
    work_memory: WorkMemoryStore
    work_schedule: WorkScheduleStore
    llm: LlmProvider
    graph: AgentGraph
    discord: DiscordBotAdapter
    github_router: GitHubWebhookRouter
    orchestrator: Orchestrator
    metrics: AgentMetrics = field(default_factory=AgentMetrics)

    def embedded_vllm(self) -> VllmEmbeddedProvider | None:
        if not isinstance(self.llm, LlmGateway) or not self.llm.local_providers:
            return None
        provider = self.llm.local_providers.get("vllm")
        if isinstance(provider, VllmEmbeddedProvider):
            return provider
        return None

    @classmethod
    def build(cls, settings: Settings | None = None) -> Container:
        settings = settings or load_settings()
        configure_logging(settings.log_level)
        log = get_logger(component="container")

        bus = EventBus(max_size=settings.event_queue_size)

        archive = ArchiveWriter(settings.archive_dir)
        operations_memory = OperationsMemoryStore(settings.archive_dir)
        llm_runtime = LlmRuntimeStore(settings.archive_dir)
        access_control = AccessControlStore(settings.archive_dir)
        agent_execution = AgentExecutionStore(settings.archive_dir)
        audit_log = AuditLogStore(settings.archive_dir)
        auth_store = AuthStore(settings.archive_dir)
        compressed_context = CompressedContextStore(settings.archive_dir)
        conversations = ConversationStore(settings.archive_dir)
        deletion_requests = DeletionRequestStore(settings.archive_dir)
        memory_schema = MemorySchemaStore(settings.archive_dir)
        permanent_memory = PermanentMemoryStore(settings.archive_dir)
        secret_store = SecretStore(settings.archive_dir, master_key=settings.secret_key)
        uploads = UploadStore(settings.archive_dir)
        volatile_memory = VolatileMemoryStore(settings.archive_dir)
        work_memory = WorkMemoryStore(settings.archive_dir)
        work_schedule = WorkScheduleStore(settings.archive_dir)
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
            operations_memory=operations_memory,
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
            operations_memory=operations_memory,
            llm_runtime=llm_runtime,
            access_control=access_control,
            agent_execution=agent_execution,
            audit_log=audit_log,
            auth_store=auth_store,
            compressed_context=compressed_context,
            conversations=conversations,
            deletion_requests=deletion_requests,
            memory_schema=memory_schema,
            permanent_memory=permanent_memory,
            secret_store=secret_store,
            uploads=uploads,
            volatile_memory=volatile_memory,
            work_memory=work_memory,
            work_schedule=work_schedule,
            llm=llm,
            graph=graph,
            discord=discord,
            github_router=github_router,
            orchestrator=orchestrator,
            metrics=metrics,
        )

    @staticmethod
    def _build_llm(settings: Settings) -> LlmProvider:
        fake = FakeLlmProvider()
        cloud_providers: dict[str, LlmProvider] = {"fake": fake}
        vllm_provider: LlmProvider
        if settings.llm.vllm_mode == "embedded":
            vllm_provider = VllmEmbeddedProvider(
                model=settings.llm.vllm_model,
                dtype=settings.llm.vllm_dtype,
                max_model_len=settings.llm.vllm_max_model_len,
                gpu_memory_utilization=settings.llm.vllm_gpu_memory_utilization,
                enforce_eager=settings.llm.vllm_enforce_eager,
                trust_remote_code=settings.llm.vllm_trust_remote_code,
                worker_multiproc_method=settings.llm.vllm_worker_multiproc_method,
            )
        else:
            vllm_provider = VllmProvider(
                base_url=settings.llm.vllm_base_url or settings.llm.local_base_url,
                model=settings.llm.vllm_model,
            )
        local_providers: dict[str, LlmProvider] = {
            "vllm": vllm_provider,
            "fake": fake,
        }
        if settings.llm.openai_api_key or settings.llm.provider == "openai":
            cloud_providers["openai"] = OpenAiProvider(
                api_key=settings.llm.openai_api_key,
                model=settings.llm.openai_model,
                base_url=settings.llm.openai_base_url or None,
            )
        if settings.llm.anthropic_api_key:
            cloud_providers["anthropic"] = AnthropicProvider(
                api_key=settings.llm.anthropic_api_key,
                model=settings.llm.anthropic_model,
            )
        if settings.llm.gemini_api_key:
            cloud_providers["gemini"] = GeminiProvider(
                api_key=settings.llm.gemini_api_key,
                model=settings.llm.gemini_model,
            )

        cloud = cloud_providers.get(settings.llm.provider) or cloud_providers.get("openai") or fake
        local = local_providers.get("vllm")
        return LlmGateway(
            cloud=cloud,
            local=local,
            default_route=settings.llm.default_route,
            cloud_providers=cloud_providers,
            local_providers=local_providers,
        )


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
