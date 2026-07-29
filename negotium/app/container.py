"""Composition root — wires adapters into the domain."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from negotium.adapters.llm.anthropic_adapter import AnthropicProvider
from negotium.adapters.llm.fake_adapter import FakeLlmProvider
from negotium.adapters.llm.gateway import LlmGateway
from negotium.adapters.llm.gemini_adapter import GeminiProvider
from negotium.adapters.llm.openai_adapter import OpenAiProvider
from negotium.adapters.llm.vllm_adapter import VllmProvider
from negotium.adapters.llm.vllm_embedded_adapter import VllmEmbeddedProvider
from negotium.app.settings import Settings, load_settings
from negotium.archive.access_control import AccessControlStore
from negotium.archive.agent_execution import AgentExecutionStore
from negotium.archive.ai_jobs import AiJobStore
from negotium.archive.audit_log import AuditLogStore
from negotium.archive.auth_store import AuthStore
from negotium.archive.automation import AutomationStore
from negotium.archive.context_compressor import CompressedContextStore
from negotium.archive.context_firewall import ContextFirewallStore
from negotium.archive.conversation_store import ConversationStore
from negotium.archive.deletion_requests import DeletionRequestStore
from negotium.archive.hr_evaluations import HrEvaluationStore
from negotium.archive.llm_runtime import LlmRuntimeStore
from negotium.archive.mcp_audit import McpAuditStore
from negotium.archive.mcp_sessions import McpSessionStore
from negotium.archive.memory_schema import MemorySchemaStore
from negotium.archive.notifications import NotificationStore
from negotium.archive.operations_memory import OperationsMemoryStore
from negotium.archive.permanent_memory import PermanentMemoryStore
from negotium.archive.process_plans import ProcessPlanStore
from negotium.archive.public_references import PublicReferenceStore
from negotium.archive.search_index import SearchIndexStore
from negotium.archive.secret_store import SecretStore
from negotium.archive.token_usage import TokenUsageStore
from negotium.archive.uploads import UploadStore
from negotium.archive.volatile_memory import VolatileMemoryStore
from negotium.archive.work_memory import WorkMemoryStore, WorkScheduleStore
from negotium.archive.writer import ArchiveWriter
from negotium.domain.ports import LlmProvider
from negotium.observability import AgentMetrics, configure_logging, get_logger


@dataclass
class Container:
    settings: Settings
    archive: ArchiveWriter
    operations_memory: OperationsMemoryStore
    ai_jobs: AiJobStore
    llm_runtime: LlmRuntimeStore
    access_control: AccessControlStore
    agent_execution: AgentExecutionStore
    audit_log: AuditLogStore
    auth_store: AuthStore
    compressed_context: CompressedContextStore
    context_firewall: ContextFirewallStore
    conversations: ConversationStore
    deletion_requests: DeletionRequestStore
    hr_evaluations: HrEvaluationStore
    memory_schema: MemorySchemaStore
    mcp_audit: McpAuditStore
    mcp_sessions: McpSessionStore
    permanent_memory: PermanentMemoryStore
    secret_store: SecretStore
    public_references: PublicReferenceStore
    token_usage: TokenUsageStore
    uploads: UploadStore
    volatile_memory: VolatileMemoryStore
    work_memory: WorkMemoryStore
    work_schedule: WorkScheduleStore
    process_plans: ProcessPlanStore
    automation: AutomationStore
    notifications: NotificationStore
    search_index: SearchIndexStore
    llm: LlmProvider
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

        archive = ArchiveWriter(settings.archive_dir)
        operations_memory = OperationsMemoryStore(settings.archive_dir)
        ai_jobs = AiJobStore(settings.archive_dir)
        llm_runtime = LlmRuntimeStore(settings.archive_dir)
        access_control = AccessControlStore(settings.archive_dir)
        agent_execution = AgentExecutionStore(settings.archive_dir)
        audit_log = AuditLogStore(settings.archive_dir)
        auth_store = AuthStore(settings.archive_dir)
        compressed_context = CompressedContextStore(settings.archive_dir)
        context_firewall = ContextFirewallStore(settings.archive_dir)
        conversations = ConversationStore(settings.archive_dir)
        deletion_requests = DeletionRequestStore(settings.archive_dir)
        hr_evaluations = HrEvaluationStore(settings.archive_dir)
        mcp_audit = McpAuditStore(settings.archive_dir)
        mcp_sessions = McpSessionStore(settings.archive_dir)
        memory_schema = MemorySchemaStore(settings.archive_dir)
        search_index = SearchIndexStore(settings.archive_dir)
        permanent_memory = PermanentMemoryStore(settings.archive_dir, search_index=search_index)
        public_references = PublicReferenceStore(settings.archive_dir)
        secret_store = SecretStore(
            settings.archive_dir,
            master_key=_resolve_secret_key(settings),
        )
        token_usage = TokenUsageStore(settings.archive_dir)
        uploads = UploadStore(settings.archive_dir)
        volatile_memory = VolatileMemoryStore(settings.archive_dir)
        work_memory = WorkMemoryStore(settings.archive_dir)
        work_schedule = WorkScheduleStore(settings.archive_dir)
        process_plans = ProcessPlanStore(settings.archive_dir)
        automation = AutomationStore(settings.archive_dir)
        notifications = NotificationStore(settings.archive_dir)

        metrics = AgentMetrics()
        llm = cls._build_llm(settings)

        log.info(
            "container.built",
            env=settings.env,
            provider=settings.llm.provider,
        )
        return cls(
            settings=settings,
            archive=archive,
            operations_memory=operations_memory,
            ai_jobs=ai_jobs,
            llm_runtime=llm_runtime,
            access_control=access_control,
            agent_execution=agent_execution,
            audit_log=audit_log,
            auth_store=auth_store,
            compressed_context=compressed_context,
            context_firewall=context_firewall,
            conversations=conversations,
            deletion_requests=deletion_requests,
            hr_evaluations=hr_evaluations,
            mcp_audit=mcp_audit,
            mcp_sessions=mcp_sessions,
            memory_schema=memory_schema,
            permanent_memory=permanent_memory,
            secret_store=secret_store,
            public_references=public_references,
            token_usage=token_usage,
            uploads=uploads,
            volatile_memory=volatile_memory,
            work_memory=work_memory,
            work_schedule=work_schedule,
            process_plans=process_plans,
            automation=automation,
            notifications=notifications,
            search_index=search_index,
            llm=llm,
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
        if settings.llm.together_api_key or settings.llm.provider == "together":
            cloud_providers["together"] = OpenAiProvider(
                api_key=settings.llm.together_api_key,
                model=settings.llm.together_model,
                base_url=settings.llm.together_base_url,
            )
        if settings.llm.solar_api_key or settings.llm.provider == "solar":
            cloud_providers["solar"] = OpenAiProvider(
                api_key=settings.llm.solar_api_key,
                model=settings.llm.solar_model,
                base_url=settings.llm.solar_base_url,
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


def _resolve_secret_key(settings: Settings) -> str:
    if settings.secret_key:
        return settings.secret_key
    if settings.env == "production":
        return ""
    return SecretStore.local_master_key(settings.archive_dir)
