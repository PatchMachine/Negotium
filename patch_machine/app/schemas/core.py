"""Pydantic schemas for frontend API payloads."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

from patch_machine.app.container import Container
from patch_machine.archive.access_control import ALL_PERMISSIONS, RoleRecord, UserRecord
from patch_machine.archive.llm_runtime import LlmProviderName, LlmRuntimeConfig, LlmTaskRoute
from patch_machine.archive.memory_schema import MemorySchema
from patch_machine.archive.operations_memory import OperationsMemory
from patch_machine.archive.volatile_memory import MemoryScope, VolatileMemory
from patch_machine.archive.work_memory import WorkMemory, WorkScheduleItem


class OperationsMemoryPayload(BaseModel):
    company_name: str = ""
    office_project: str = ""
    active_plan: str = ""
    organization: str = ""
    departments: str = ""
    roles: str = ""
    key_workflows: str = ""
    office_tools: str = ""
    sensitive_policy: str = ""

    def to_memory(self) -> OperationsMemory:
        return OperationsMemory(
            company_name=self.company_name.strip(),
            office_project=self.office_project.strip(),
            active_plan=self.active_plan.strip(),
            organization=self.organization.strip(),
            departments=self.departments.strip(),
            roles=self.roles.strip(),
            key_workflows=self.key_workflows.strip(),
            office_tools=self.office_tools.strip(),
            sensitive_policy=self.sensitive_policy.strip(),
        )


class ApiStatusPayload(BaseModel):
    ok: bool
    queue_size: int
    queue_capacity: int
    metrics: dict[str, Any]
    operations_memory_configured: bool


class LlmRuntimePayload(BaseModel):
    local_enabled: bool = True
    api_enabled: bool = True
    default_route: Literal["local", "api"] = "local"
    default_provider: LlmProviderName = "vllm"
    local_model: str = "Qwen/Qwen3-4B"
    vllm_base_url: str = ""
    openai_model: str = ""
    anthropic_model: str = ""
    gemini_model: str = ""
    task_routes: dict[str, dict[str, str]] = Field(default_factory=dict)

    @classmethod
    def from_config(cls, config: LlmRuntimeConfig, container: Container) -> LlmRuntimePayload:
        base = config.to_dict()
        base.pop("task_routes", None)
        return cls(
            **base,
            vllm_base_url=container.settings.llm.vllm_base_url,
            openai_model=container.settings.llm.openai_model,
            anthropic_model=container.settings.llm.anthropic_model,
            gemini_model=container.settings.llm.gemini_model,
            task_routes={
                task: route.to_dict() for task, route in (config.task_routes or {}).items()
            },
        )

    def to_config(self) -> LlmRuntimeConfig:
        return LlmRuntimeConfig(
            local_enabled=self.local_enabled,
            api_enabled=self.api_enabled,
            default_route=self.default_route,
            default_provider=self.default_provider,
            local_model=self.local_model.strip() or "Qwen/Qwen3-4B",
            task_routes={
                task: LlmTaskRoute.from_mapping(route) for task, route in self.task_routes.items()
            }
            or None,
        )


class ChatRequest(BaseModel):
    message: str
    route: Literal["local", "api"] | None = None
    provider: LlmProviderName | None = None
    task: str = "chat"


class ChatResponse(BaseModel):
    answer: str
    route: Literal["local", "api"]
    provider: LlmProviderName
    model: str
    prompt_tokens: int
    completion_tokens: int
    ai_job: dict[str, Any] = Field(default_factory=dict)


class LocalLlmStatusPayload(BaseModel):
    enabled: bool
    mode: str
    state: str
    model: str
    loaded: bool
    message: str
    error: str = ""
    started_at: str = ""
    ready_at: str = ""


class ProgressPayload(BaseModel):
    current_status_md: str
    queue_size: int
    queue_capacity: int
    recent_logs: list[dict[str, Any]]


class WorkItemsPayload(BaseModel):
    items: list[dict[str, Any]]
    bottleneck_summary: str = ""


class WorkMemoryPayload(BaseModel):
    goals: str = ""
    active_projects: str = ""
    current_focus: str = ""
    blockers: str = ""
    decisions: str = ""
    risks: str = ""
    next_actions: str = ""
    updated_at: str = ""

    @classmethod
    def from_memory(cls, memory: WorkMemory) -> WorkMemoryPayload:
        return cls(**memory.to_dict())

    def to_memory(self) -> WorkMemory:
        return WorkMemory(
            goals=self.goals.strip(),
            active_projects=self.active_projects.strip(),
            current_focus=self.current_focus.strip(),
            blockers=self.blockers.strip(),
            decisions=self.decisions.strip(),
            risks=self.risks.strip(),
            next_actions=self.next_actions.strip(),
            updated_at=self.updated_at,
        )


class WorkScheduleItemPayload(BaseModel):
    id: str = ""
    title: str
    owner_id: str = ""
    owner_name: str = ""
    status: str = "todo"
    priority: str = "normal"
    start_date: str = ""
    due_date: str = ""
    dependencies: list[str] = []
    notes: str = ""
    source_architecture_id: str = ""

    def to_record(self, *, item_id: str | None = None) -> WorkScheduleItem:
        return WorkScheduleItem.create(
            id=item_id or self.id,
            title=self.title,
            owner_id=self.owner_id,
            owner_name=self.owner_name,
            status=self.status,
            priority=self.priority,
            start_date=self.start_date,
            due_date=self.due_date,
            dependencies=self.dependencies,
            notes=self.notes,
            source_architecture_id=self.source_architecture_id,
        )


class WorkArchitectureRequest(BaseModel):
    objective: str
    scope: str = ""
    horizon: str = ""
    participants: str = ""
    constraints: str = ""
    use_memory: bool = True


class WorkArchitecturePayload(BaseModel):
    title: str
    markdown: str
    path: str
    architecture: dict[str, object]
    ai_job: dict[str, Any] = Field(default_factory=dict)


class WorkScheduleGenerationRequest(BaseModel):
    objective: str
    participants: str = ""
    horizon: str = ""
    constraints: str = ""


class VolatileMemoryPayload(BaseModel):
    scope: MemoryScope = "global"
    key: str = "default"
    summary: str = ""
    current_intent: str = ""
    active_context: str = ""
    preferences: str = ""
    open_questions: list[str] = []
    next_actions: list[str] = []
    relevant_sources: list[str] = []
    expires_at: str = ""
    updated_at: str = ""

    @classmethod
    def from_memory(cls, memory: VolatileMemory) -> VolatileMemoryPayload:
        return cls(**memory.to_dict())

    def to_memory(self) -> VolatileMemory:
        return VolatileMemory(
            scope=self.scope,
            key=self.key.strip() or "default",
            summary=self.summary.strip(),
            current_intent=self.current_intent.strip(),
            active_context=self.active_context.strip(),
            preferences=self.preferences.strip(),
            open_questions=[item.strip() for item in self.open_questions if item.strip()],
            next_actions=[item.strip() for item in self.next_actions if item.strip()],
            relevant_sources=[item.strip() for item in self.relevant_sources if item.strip()],
            expires_at=self.expires_at.strip(),
            updated_at=self.updated_at,
        )


class MemoryRefreshRequest(BaseModel):
    scope: MemoryScope = "user"
    key: str = ""
    query: str = ""
    source_limit: int = 10
    source_ids: list[str] = Field(default_factory=list)


class ContextCompressRequest(BaseModel):
    scope: MemoryScope = "global"
    key: str = "default"
    query: str = ""
    token_budget: int = 4000
    source_limit: int = 20
    source_ids: list[str] = Field(default_factory=list)
    include_volatile: bool = False


class ReadableContextPreviewRequest(BaseModel):
    query: str = ""
    source_ids: list[str] = Field(default_factory=list)
    source_limit: int = 20
    include_volatile: bool = False
    token_budget: int = 4000


class ReadableContextSourcePayload(BaseModel):
    id: str
    kind: str
    path: str
    title: str
    excerpt: str = ""
    content: str = ""
    selected: bool = False
    order: int = 0
    sensitivity: str = "internal"
    origin: str = "archive"
    updated_at: str = ""


class ReadableContextBundlePayload(BaseModel):
    query: str = ""
    used_sources: list[ReadableContextSourcePayload] = Field(default_factory=list)
    volatile_memories: list[VolatileMemoryPayload] = Field(default_factory=list)
    estimated_tokens: int = 0
    warnings: list[str] = Field(default_factory=list)
    markdown: str = ""


class AiJobStatusPayload(BaseModel):
    job_id: str
    task: str
    status: Literal["queued", "running", "succeeded", "failed"] = "queued"
    actor: str = ""
    input_summary: str = ""
    used_sources: list[str] = Field(default_factory=list)
    result_path: str = ""
    error: str = ""
    created_at: str = ""
    updated_at: str = ""


class PromoteMemoryPayload(BaseModel):
    title: str
    content: str
    source_refs: list[str] = []


class MemorySchemaPayload(BaseModel):
    type_id: str
    display_name: str
    description: str = ""
    fields: list[dict[str, object]] = []
    retention_policy: str = "keep"
    sensitivity: str = "internal"
    delete_requires_approval: bool = True
    allowed_roles: list[str] = ["owner", "manager"]

    def to_record(self, *, actor: str) -> MemorySchema:
        return MemorySchema(
            type_id=self.type_id.strip(),
            display_name=self.display_name.strip(),
            description=self.description.strip(),
            fields=self.fields,
            retention_policy=self.retention_policy.strip() or "keep",
            sensitivity=self.sensitivity.strip() or "internal",
            delete_requires_approval=self.delete_requires_approval,
            allowed_roles=self.allowed_roles,
            created_by=actor,
        )


class MemorySchemaProposalPayload(BaseModel):
    mode: str = "llm_propose_human_approve"
    proposal: dict[str, object]


class DeletionRequestPayload(BaseModel):
    target_type: str
    target_id: str
    summary: str
    source_path: str = ""
    sensitivity: str = "internal"
    reason: str = ""


class AgentPlanRequest(BaseModel):
    objective: str
    title: str = ""
    mode: str = "plan_only"
    schedule_refs: list[str] = []
    memory_refs: list[str] = []


class PatchRunCreatePayload(BaseModel):
    repo_id: str = "local"
    request: str
    autonomy_level: str = "L1"
    privacy_mode: str = "hybrid_redacted"
    target_branch: str = "main"
    constraints: dict[str, Any] = Field(default_factory=dict)


class PatchRunApprovalPayload(BaseModel):
    decision: Literal["approve", "reject"] = "approve"
    comment: str = ""


class PatchRunPayload(BaseModel):
    id: str
    repo_id: str
    request: str
    autonomy_level: str
    privacy_mode: str
    target_branch: str
    status: str
    risk_level: str
    created_by: str = ""
    approved_by: str = ""
    plan: dict[str, Any] = Field(default_factory=dict)
    questions: list[dict[str, Any]] = Field(default_factory=list)
    artifacts: dict[str, Any] = Field(default_factory=dict)
    context: dict[str, Any] = Field(default_factory=dict)
    constraints: dict[str, Any] = Field(default_factory=dict)
    created_at: str = ""
    updated_at: str = ""


class IntegrationStatusPayload(BaseModel):
    ok: bool
    configured: bool
    reason: str = ""
    items: list[dict[str, Any]]


class GitHubConnectorPayload(BaseModel):
    enabled: bool = False
    allowed_repos: list[str] = Field(default_factory=list)
    trigger_label: str = "patch-machine"
    webhook_secret: str = ""
    app_token: str = ""
    webhook_secret_present: bool = False
    app_token_present: bool = False
    event_forms: list[str] = Field(
        default_factory=lambda: ["issue", "pull_request", "repository", "push"]
    )


class DiscordChannelBindingPayload(BaseModel):
    guild_id: str = ""
    channel_id: str = ""
    channel_name: str = ""
    repo: str = ""


class DiscordConnectorPayload(BaseModel):
    enabled: bool = False
    bot_token: str = ""
    bot_token_present: bool = False
    guild_allowlist: list[str] = Field(default_factory=list)
    channel_bindings: list[DiscordChannelBindingPayload] = Field(default_factory=list)
    command_forms: list[str] = Field(
        default_factory=lambda: ["bug_report", "thread_digest", "slash_command"]
    )


class IntegrationConfigPayload(BaseModel):
    github: GitHubConnectorPayload = Field(default_factory=GitHubConnectorPayload)
    discord: DiscordConnectorPayload = Field(default_factory=DiscordConnectorPayload)


class DocumentReadPayload(BaseModel):
    path: str
    markdown: str
    bytes: int
    modified_at: str


class TokenLimitPayload(BaseModel):
    enforcement_enabled: bool = True
    per_request_max_tokens: int = 4000
    daily_total_tokens: int = 200_000
    monthly_total_tokens: int = 4_000_000


class TokenUsageEntryPayload(BaseModel):
    provider: str = ""
    model: str = ""
    task: str = ""
    actor: str = ""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    occurred_at: str = ""


class TokenUsageSummaryPayload(BaseModel):
    daily_total: int = 0
    monthly_total: int = 0
    by_provider: dict[str, int] = Field(default_factory=dict)
    by_task: dict[str, int] = Field(default_factory=dict)
    by_actor: dict[str, int] = Field(default_factory=dict)
    recent: list[TokenUsageEntryPayload] = Field(default_factory=list)


class TokenLimitStatusPayload(BaseModel):
    limits: TokenLimitPayload
    usage: TokenUsageSummaryPayload


class PatchRecordCreatePayload(BaseModel):
    title: str
    summary: str = ""
    request: str = ""
    plan: list[str] = Field(default_factory=list)
    changed_files: list[str] = Field(default_factory=list)
    verification: list[str] = Field(default_factory=list)
    follow_ups: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    agent: str = ""


class PatchRecordPayload(BaseModel):
    record_id: str
    title: str
    summary: str = ""
    request: str = ""
    plan: list[str] = Field(default_factory=list)
    changed_files: list[str] = Field(default_factory=list)
    verification: list[str] = Field(default_factory=list)
    follow_ups: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    actor: str = ""
    agent: str = ""
    created_at: str = ""
    relative_path: str = ""


class PatchRecordDetailPayload(PatchRecordPayload):
    markdown: str = ""


class HiringRequest(BaseModel):
    role_title: str
    business_need: str = ""
    priority: str = "normal"


class GeneratedDocumentPayload(BaseModel):
    title: str
    markdown: str
    path: str
    ai_job: dict[str, Any] = Field(default_factory=dict)


class HandoverRequest(BaseModel):
    work_title: str
    outgoing_owner: str = ""
    incoming_owner: str = ""
    notes: str = ""


class OfficeDocumentRequest(BaseModel):
    document_type: Literal["meeting_minutes", "report_draft", "work_request", "ppt_outline"]
    title: str
    source_text: str
    audience: str = ""


class ApiKeyPayload(BaseModel):
    provider: str
    api_key: str = ""
    model: str = ""
    base_url: str = ""


class ProviderModelPayload(BaseModel):
    provider: str
    models: list[str]
    source: str
    refreshed_at: str
    reason: str = ""
    configured: bool = False
    requires_api_key: bool = True


class ProviderModelPreviewPayload(BaseModel):
    api_key: str = ""
    base_url: str = ""
    include_fallback: bool = True


class HuggingFaceModelSearchPayload(BaseModel):
    query: str = ""
    limit: int = 12


class HuggingFaceModelItemPayload(BaseModel):
    id: str
    downloads: int = 0
    likes: int = 0
    tags: list[str] = Field(default_factory=list)
    pipeline_tag: str = ""


class HuggingFaceModelSearchResultPayload(BaseModel):
    query: str
    models: list[HuggingFaceModelItemPayload]


class SetupStatusPayload(BaseModel):
    setup_required: bool


class SetupAdminPayload(BaseModel):
    user_id: str
    display_name: str
    password: str
    title: str = "관리자"


class LoginPayload(BaseModel):
    user_id: str
    password: str


class AuthSessionPayload(BaseModel):
    token: str
    user: dict[str, object]


class CurrentUserPayload(BaseModel):
    authenticated: bool
    user: dict[str, object] | None = None


class AccountRequestPayload(BaseModel):
    user_id: str
    display_name: str
    title: str = ""
    password: str


class RolePayload(BaseModel):
    id: str
    name: str
    level: int = 0
    permissions: list[str] = []

    def to_record(self) -> RoleRecord:
        allowed = {*ALL_PERMISSIONS, "*"}
        return RoleRecord(
            id=self.id.strip(),
            name=self.name.strip(),
            level=self.level,
            permissions=[permission for permission in self.permissions if permission in allowed],
        )


class UserPayload(BaseModel):
    id: str
    display_name: str
    title: str = ""
    role_id: str = "viewer"
    active: bool = True

    def to_record(self) -> UserRecord:
        return UserRecord(
            id=self.id.strip(),
            display_name=self.display_name.strip(),
            title=self.title.strip(),
            role_id=self.role_id.strip() or "viewer",
            active=self.active,
        )


class CompanyProfilePayload(BaseModel):
    organization_size: str = "startup"
    industries: list[str] = Field(default_factory=lambda: ["it_saas"])
    departments: list[str] = Field(default_factory=lambda: ["product_dev_it", "cs"])
    primary_goals: list[str] = Field(
        default_factory=lambda: [
            "meeting_notes",
            "action_items",
            "weekly_patch_notes",
            "release_notes",
            "integrated_search",
        ]
    )
    data_sensitivity: list[str] = Field(default_factory=lambda: ["general"])
    deployment_preference: str = "local_recommended"
    company_name: str = ""
    office_project: str = ""
    work_summary: str = ""
    current_tools: str = ""
    recurring_workflows: str = ""
    change_management_needs: str = ""
    automation_priorities: str = ""


class PatchNoteRecommendationPayload(BaseModel):
    workspace_profile: dict[str, Any] = Field(default_factory=dict)
    recommended_package: str = "Patch Note Team"
    agent_packs: list[dict[str, Any]] = Field(default_factory=list)
    templates: list[dict[str, Any]] = Field(default_factory=list)
    workflows: list[dict[str, Any]] = Field(default_factory=list)
    security_defaults: list[dict[str, Any]] = Field(default_factory=list)
    integration_priorities: list[dict[str, Any]] = Field(default_factory=list)
    llm_task_routes: dict[str, dict[str, str]] = Field(default_factory=dict)
    first_14_days: list[str] = Field(default_factory=list)
    human_review_required: list[str] = Field(default_factory=list)


class InitialOfficeAnalyzeRequest(BaseModel):
    message: str = ""
    upload_ids: list[str] = Field(default_factory=list)
    intent: str = "initial_office_setup"
    company_profile: CompanyProfilePayload = Field(default_factory=CompanyProfilePayload)


class InitialOfficeSetupResult(BaseModel):
    operations_memory: dict[str, Any] = Field(default_factory=dict)
    work_memory: dict[str, Any] = Field(default_factory=dict)
    workspace_profile: dict[str, Any] = Field(default_factory=dict)
    recommended_package: str = "Patch Note Team"
    agent_packs: list[dict[str, Any]] = Field(default_factory=list)
    templates: list[dict[str, Any]] = Field(default_factory=list)
    workflows: list[dict[str, Any]] = Field(default_factory=list)
    security_defaults: list[dict[str, Any]] = Field(default_factory=list)
    integration_priorities: list[dict[str, Any]] = Field(default_factory=list)
    llm_task_routes: dict[str, dict[str, str]] = Field(default_factory=dict)
    first_14_days: list[str] = Field(default_factory=list)
    human_review_required: list[str] = Field(default_factory=list)
    roles: list[RolePayload] = Field(default_factory=list)
    users: list[UserPayload] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    questions: list[str] = Field(default_factory=list)
    sensitive_hint: bool = False
    ai_job: dict[str, Any] = Field(default_factory=dict)
