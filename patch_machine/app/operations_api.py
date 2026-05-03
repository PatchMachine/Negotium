"""JSON API routes for the local frontend."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated, Any, Literal

import httpx
import portalocker
from fastapi import APIRouter, File, Form, Header, HTTPException, UploadFile, status
from pydantic import BaseModel

from patch_machine.adapters.llm.anthropic_adapter import AnthropicProvider
from patch_machine.adapters.llm.gateway import LlmGateway
from patch_machine.adapters.llm.gemini_adapter import GeminiProvider
from patch_machine.adapters.llm.openai_adapter import OpenAiProvider
from patch_machine.adapters.llm.vllm_adapter import VllmConnectionError, VllmProvider
from patch_machine.app.container import Container
from patch_machine.archive.access_control import ALL_PERMISSIONS, RoleRecord, UserRecord
from patch_machine.archive.llm_runtime import LlmProviderName, LlmRuntimeConfig
from patch_machine.archive.operations_memory import OperationsMemory
from patch_machine.archive.schema import parse_front_matter
from patch_machine.archive.secret_store import ApiKeyRecord
from patch_machine.domain.entities import LlmRoute
from patch_machine.domain.ports import LlmMessage, LlmResponse

_PRELOAD_TASKS: set[asyncio.Task[None]] = set()


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

    @classmethod
    def from_config(cls, config: LlmRuntimeConfig, container: Container) -> LlmRuntimePayload:
        return cls(
            **config.to_dict(),
            vllm_base_url=container.settings.llm.vllm_base_url,
            openai_model=container.settings.llm.openai_model,
            anthropic_model=container.settings.llm.anthropic_model,
            gemini_model=container.settings.llm.gemini_model,
        )

    def to_config(self) -> LlmRuntimeConfig:
        return LlmRuntimeConfig(
            local_enabled=self.local_enabled,
            api_enabled=self.api_enabled,
            default_route=self.default_route,
            default_provider=self.default_provider,
            local_model=self.local_model.strip() or "Qwen/Qwen3-4B",
        )


class ChatRequest(BaseModel):
    message: str
    route: Literal["local", "api"] | None = None
    provider: LlmProviderName | None = None


class ChatResponse(BaseModel):
    answer: str
    route: Literal["local", "api"]
    provider: LlmProviderName
    model: str
    prompt_tokens: int
    completion_tokens: int


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


class IntegrationStatusPayload(BaseModel):
    ok: bool
    configured: bool
    reason: str = ""
    items: list[dict[str, Any]]


class HiringRequest(BaseModel):
    role_title: str
    business_need: str = ""
    priority: str = "normal"


class GeneratedDocumentPayload(BaseModel):
    title: str
    markdown: str
    path: str


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


def create_operations_api_router(container: Container) -> APIRouter:
    """Create frontend-facing API routes bound to the app container."""
    router = APIRouter(prefix="/api", tags=["frontend-api"])

    @router.get("/operations-memory")
    async def read_operations_memory() -> OperationsMemoryPayload:
        memory = container.operations_memory.read()
        return OperationsMemoryPayload(**memory.to_dict())

    @router.put("/operations-memory")
    async def write_operations_memory(
        payload: OperationsMemoryPayload,
        x_pm_user: str | None = Header(default=None, alias="X-PM-User"),
    ) -> OperationsMemoryPayload:
        _require(container, x_pm_user, "memory:write")
        memory = payload.to_memory()
        container.operations_memory.write(memory)
        return OperationsMemoryPayload(**memory.to_dict())

    @router.get("/status")
    async def read_status() -> ApiStatusPayload:
        memory = container.operations_memory.read()
        return ApiStatusPayload(
            ok=True,
            queue_size=container.bus.size,
            queue_capacity=container.bus.capacity,
            metrics=container.metrics.snapshot(),
            operations_memory_configured=any(memory.to_dict().values()),
        )

    @router.get("/llm/runtime")
    async def read_llm_runtime() -> LlmRuntimePayload:
        return LlmRuntimePayload.from_config(container.llm_runtime.read(), container)

    @router.put("/llm/runtime")
    async def write_llm_runtime(payload: LlmRuntimePayload) -> LlmRuntimePayload:
        config = payload.to_config()
        container.llm_runtime.write(config)
        _sync_local_llm_state(container, enabled=config.local_enabled)
        return LlmRuntimePayload.from_config(config, container)

    @router.get("/llm/local-status")
    async def read_local_llm_status() -> LocalLlmStatusPayload:
        return _local_llm_status(container)

    @router.post("/llm/local/start")
    async def start_local_llm(
        x_pm_user: str | None = Header(default=None, alias="X-PM-User"),
    ) -> LocalLlmStatusPayload:
        _require(container, x_pm_user, "llm:chat")
        runtime = container.llm_runtime.read()
        if not runtime.local_enabled:
            container.llm_runtime.write(
                LlmRuntimeConfig(
                    local_enabled=True,
                    api_enabled=runtime.api_enabled,
                    default_route=runtime.default_route,
                    default_provider=runtime.default_provider,
                    local_model=runtime.local_model,
                )
            )
        _sync_local_llm_state(container, enabled=True)
        return _local_llm_status(container)

    @router.post("/llm/local/stop")
    async def stop_local_llm(
        x_pm_user: str | None = Header(default=None, alias="X-PM-User"),
    ) -> LocalLlmStatusPayload:
        _require(container, x_pm_user, "llm:chat")
        runtime = container.llm_runtime.read()
        container.llm_runtime.write(
            LlmRuntimeConfig(
                local_enabled=False,
                api_enabled=runtime.api_enabled,
                default_route=runtime.default_route,
                default_provider=runtime.default_provider,
                local_model=runtime.local_model,
            )
        )
        _sync_local_llm_state(container, enabled=False)
        return _local_llm_status(container)

    @router.post("/llm/chat")
    async def chat(
        payload: ChatRequest,
        x_pm_user: str | None = Header(default=None, alias="X-PM-User"),
    ) -> ChatResponse:
        _require(container, x_pm_user, "llm:chat")
        runtime = container.llm_runtime.read()
        route = payload.route or runtime.default_route
        provider = payload.provider or runtime.default_provider
        if route == "local" and not runtime.local_enabled:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="local LLM route is disabled")
        if route == "api" and not runtime.api_enabled:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="API LLM route is disabled")
        llm_route: LlmRoute = "local" if route == "local" else "cloud"
        messages = _build_chat_messages(container, payload.message)
        response = await _complete_with_provider(
            container,
            messages,
            provider=provider,
            route=llm_route,
            temperature=0.2,
            max_tokens=1024,
        )
        container.metrics.record(
            agent="chat",
            route=response.route,
            tokens_in=response.prompt_tokens,
            tokens_out=response.completion_tokens,
            latency_ms=0,
        )
        return ChatResponse(
            answer=response.text,
            route=route,
            provider=provider,
            model=response.model,
            prompt_tokens=response.prompt_tokens,
            completion_tokens=response.completion_tokens,
        )

    @router.get("/progress")
    async def read_progress() -> ProgressPayload:
        return ProgressPayload(
            current_status_md=container.archive.status.read(),
            queue_size=container.bus.size,
            queue_capacity=container.bus.capacity,
            recent_logs=_recent_logs(container.settings.archive_dir, limit=8),
        )

    @router.get("/work-items")
    async def read_work_items() -> WorkItemsPayload:
        items = _recent_logs(container.settings.archive_dir, limit=20)
        for item in items:
            item["kind"] = item.get("source") or "archive"
            item["summary"] = f"{item.get('repo', 'unknown')} #{item.get('external_id', '-')}"
        summary = _summarize_bottlenecks(items)
        return WorkItemsPayload(items=items, bottleneck_summary=summary)

    @router.get("/integrations/github")
    async def read_github_status() -> IntegrationStatusPayload:
        return await _fetch_github_status(container)

    @router.get("/integrations/discord")
    async def read_discord_status() -> IntegrationStatusPayload:
        return await _fetch_discord_status(container)

    @router.post("/hr/role-requirements")
    async def create_role_requirements(
        payload: HiringRequest,
        x_pm_user: str | None = Header(default=None, alias="X-PM-User"),
    ) -> GeneratedDocumentPayload:
        _require(container, x_pm_user, "documents:write")
        return await _generate_hiring_document(
            container,
            payload,
            kind="role_requirements",
            instruction="필요 역량, 경험, 성향, 필수/우대 조건을 정리하세요.",
        )

    @router.post("/hr/interview-kit")
    async def create_interview_kit(
        payload: HiringRequest,
        x_pm_user: str | None = Header(default=None, alias="X-PM-User"),
    ) -> GeneratedDocumentPayload:
        _require(container, x_pm_user, "documents:write")
        return await _generate_hiring_document(
            container,
            payload,
            kind="interview_kit",
            instruction="면접 질문, 좋은 답변 기준, 평가 루브릭을 작성하세요.",
        )

    @router.post("/hr/onboarding-plan")
    async def create_onboarding_plan(
        payload: HiringRequest,
        x_pm_user: str | None = Header(default=None, alias="X-PM-User"),
    ) -> GeneratedDocumentPayload:
        _require(container, x_pm_user, "documents:write")
        return await _generate_hiring_document(
            container,
            payload,
            kind="onboarding_plan",
            instruction="입사 후 1주/1개월/3개월 온보딩 계획과 산출물을 작성하세요.",
        )

    @router.post("/handover/brief")
    async def create_handover_brief(
        payload: HandoverRequest,
        x_pm_user: str | None = Header(default=None, alias="X-PM-User"),
    ) -> GeneratedDocumentPayload:
        _require(container, x_pm_user, "documents:write")
        context = _office_context(container)
        prompt = f"""
{context}

인수인계 대상 업무: {payload.work_title}
기존 담당자: {payload.outgoing_owner or "(미지정)"}
신규 담당자: {payload.incoming_owner or "(미지정)"}
추가 메모:
{payload.notes or "(없음)"}

최근 archive 로그와 회사 메모리를 바탕으로 인수인계 문서를 작성하세요.
반드시 다음 섹션을 포함하세요: 업무 목적, 현재 진행상황, 주요 결정사항, 남은 작업, 관련자, 리스크, 첫 3일 액션.
""".strip()
        markdown = await _complete_office_task(container, prompt)
        path = _write_generated_doc(
            container.settings.archive_dir,
            folder="handover",
            slug=payload.work_title or "handover",
            markdown=markdown,
        )
        return GeneratedDocumentPayload(title=payload.work_title, markdown=markdown, path=path)

    @router.post("/documents/generate")
    async def create_office_document(
        payload: OfficeDocumentRequest,
        x_pm_user: str | None = Header(default=None, alias="X-PM-User"),
    ) -> GeneratedDocumentPayload:
        _require(container, x_pm_user, "documents:write")
        labels = {
            "meeting_minutes": "회의록",
            "report_draft": "보고서 초안",
            "work_request": "업무 요청서",
            "ppt_outline": "PPT 초안",
        }
        prompt = f"""
{_office_context(container)}

문서 유형: {labels[payload.document_type]}
제목: {payload.title}
대상 독자: {payload.audience or "(미지정)"}
원문/메모:
{payload.source_text}

회사 업무에 바로 사용할 수 있는 Markdown 문서로 작성하세요.
핵심 요약, 본문, 액션 아이템, 확인 필요사항을 포함하세요.
""".strip()
        markdown = await _complete_office_task(container, prompt)
        path = _write_generated_doc(
            container.settings.archive_dir,
            folder="documents",
            slug=f"{payload.document_type}_{payload.title}",
            markdown=markdown,
        )
        return GeneratedDocumentPayload(title=payload.title, markdown=markdown, path=path)

    @router.get("/admin/api-keys")
    async def list_api_keys(
        x_pm_user: str | None = Header(default=None, alias="X-PM-User"),
    ) -> dict[str, object]:
        _require(container, x_pm_user, "admin:api_keys")
        try:
            providers = container.secret_store.list_masked()
        except ValueError as exc:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
        return {"providers": providers}

    @router.put("/admin/api-keys/{provider}")
    async def save_api_key(
        provider: str,
        payload: ApiKeyPayload,
        x_pm_user: str | None = Header(default=None, alias="X-PM-User"),
    ) -> dict[str, object]:
        _require(container, x_pm_user, "admin:api_keys")
        try:
            container.secret_store.upsert(
                ApiKeyRecord(
                    provider=provider,
                    api_key=payload.api_key.strip(),
                    model=payload.model.strip(),
                    base_url=payload.base_url.strip(),
                )
            )
            return {"ok": True, "providers": container.secret_store.list_masked()}
        except ValueError as exc:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    @router.delete("/admin/api-keys/{provider}")
    async def delete_api_key(
        provider: str,
        x_pm_user: str | None = Header(default=None, alias="X-PM-User"),
    ) -> dict[str, object]:
        _require(container, x_pm_user, "admin:api_keys")
        container.secret_store.delete(provider)
        return {"ok": True, "providers": container.secret_store.list_masked()}

    @router.get("/admin/access-control")
    async def read_access_control(
        x_pm_user: str | None = Header(default=None, alias="X-PM-User"),
    ) -> dict[str, Any]:
        _require(container, x_pm_user, "admin:users")
        return {**container.access_control.read(), "permissions": ALL_PERMISSIONS}

    @router.post("/admin/roles")
    async def upsert_role(
        payload: RolePayload,
        x_pm_user: str | None = Header(default=None, alias="X-PM-User"),
    ) -> dict[str, Any]:
        _require(container, x_pm_user, "admin:users")
        container.access_control.upsert_role(payload.to_record())
        return container.access_control.read()

    @router.delete("/admin/roles/{role_id}")
    async def delete_role(
        role_id: str,
        x_pm_user: str | None = Header(default=None, alias="X-PM-User"),
    ) -> dict[str, Any]:
        _require(container, x_pm_user, "admin:users")
        try:
            container.access_control.delete_role(role_id)
        except ValueError as exc:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
        return container.access_control.read()

    @router.post("/admin/users")
    async def upsert_user(
        payload: UserPayload,
        x_pm_user: str | None = Header(default=None, alias="X-PM-User"),
    ) -> dict[str, Any]:
        _require(container, x_pm_user, "admin:users")
        container.access_control.upsert_user(payload.to_record())
        return container.access_control.read()

    @router.delete("/admin/users/{user_id}")
    async def delete_user(
        user_id: str,
        x_pm_user: str | None = Header(default=None, alias="X-PM-User"),
    ) -> dict[str, Any]:
        _require(container, x_pm_user, "admin:users")
        container.access_control.delete_user(user_id)
        return container.access_control.read()

    @router.get("/uploads")
    async def list_uploads() -> dict[str, object]:
        return {"uploads": container.uploads.list()}

    @router.post("/uploads")
    async def upload_file(
        file: Annotated[UploadFile, File(...)],
        description: Annotated[str, Form()] = "",
        tags: Annotated[str, Form()] = "",
        work_title: Annotated[str, Form()] = "",
        x_pm_user: str | None = Header(default=None, alias="X-PM-User"),
    ) -> dict[str, object]:
        _require(container, x_pm_user, "uploads:write")
        record = container.uploads.save(
            filename=file.filename or "upload.bin",
            source=file.file,
            description=description,
            tags=tags,
            work_title=work_title,
        )
        return {"ok": True, "upload": record.to_dict()}

    @router.delete("/uploads/{upload_id}")
    async def delete_upload(
        upload_id: str,
        x_pm_user: str | None = Header(default=None, alias="X-PM-User"),
    ) -> dict[str, object]:
        _require(container, x_pm_user, "uploads:write")
        return {"ok": container.uploads.delete(upload_id)}

    return router


def _build_chat_messages(container: Container, user_message: str) -> list[LlmMessage]:
    memory = container.operations_memory.read().to_markdown()
    status_md = container.archive.status.read()
    recent = _recent_logs(container.settings.archive_dir, limit=5)
    recent_md = "\n".join(
        f"- {entry.get('created', '')} {entry.get('repo', '')} #{entry.get('external_id', '')} "
        f"status={entry.get('status', '')}"
        for entry in recent
    )
    system = (
        "당신은 Patch Machine의 운영 채팅 에이전트입니다. "
        "운영 메모리, 진행 로그, 최근 처리 이슈를 근거로 한국어로 짧고 실행 가능하게 답하세요. "
        "모르는 내용은 추측하지 말고 필요한 설정을 알려주세요."
    )
    context = f"""
운영 메모리:
{memory}

현재 상태:
{status_md}

최근 처리 로그:
{recent_md or "- 없음"}
""".strip()
    return [
        LlmMessage("system", system),
        LlmMessage("user", f"{context}\n\n질문:\n{user_message.strip()}"),
    ]


def _require(container: Container, user_id: str | None, permission: str) -> None:
    if not container.access_control.has_permission(user_id, permission):
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            detail=f"permission required: {permission}",
        )


def _sync_local_llm_state(container: Container, *, enabled: bool) -> None:
    provider = container.embedded_vllm()
    if provider is None:
        return
    if enabled:
        if provider.status()["state"] not in {"loading", "running"}:
            task = asyncio.create_task(provider.preload(), name="vllm-local-preload")
            _PRELOAD_TASKS.add(task)
            task.add_done_callback(_PRELOAD_TASKS.discard)
    else:
        provider.unload()


def _local_llm_status(container: Container) -> LocalLlmStatusPayload:
    runtime = container.llm_runtime.read()
    model = runtime.local_model or container.settings.llm.vllm_model
    if not runtime.local_enabled:
        return LocalLlmStatusPayload(
            enabled=False,
            mode=container.settings.llm.vllm_mode,
            state="disabled",
            model=model,
            loaded=False,
            message="로컬 LLM이 OFF 상태입니다. Local ON을 누르면 모델 로딩을 시작합니다.",
        )
    provider = container.embedded_vllm()
    if provider is None:
        return LocalLlmStatusPayload(
            enabled=True,
            mode=container.settings.llm.vllm_mode,
            state="http",
            model=model,
            loaded=False,
            message="외부 vLLM HTTP 서버 모드입니다. PM_VLLM_BASE_URL 상태를 확인하세요.",
        )
    raw = provider.status()
    state = str(raw["state"])
    messages = {
        "offline": "로컬 LLM이 아직 올라오지 않았습니다. Local ON을 누르면 GPU에 모델을 올립니다.",
        "loading": "로컬 LLM을 GPU에 올리는 중입니다. 첫 로딩은 수십 초에서 수 분 걸릴 수 있습니다.",
        "running": "로컬 LLM이 GPU 상에서 가동 중입니다!",
        "error": "로컬 LLM 로딩에 실패했습니다. 서버 로그의 vLLM 오류를 확인하세요.",
    }
    return LocalLlmStatusPayload(
        enabled=True,
        mode=str(raw["mode"]),
        state=state,
        model=str(raw["model"]),
        loaded=bool(raw["loaded"]),
        message=messages.get(state, "로컬 LLM 상태를 확인 중입니다."),
        error=str(raw["error"]),
        started_at=str(raw["started_at"]),
        ready_at=str(raw["ready_at"]),
    )


async def _generate_hiring_document(
    container: Container,
    payload: HiringRequest,
    *,
    kind: str,
    instruction: str,
) -> GeneratedDocumentPayload:
    prompt = f"""
{_office_context(container)}

채용 대상 직무: {payload.role_title}
비즈니스 필요:
{payload.business_need or "(미입력)"}
우선순위: {payload.priority}

{instruction}
대표와 실무자가 바로 쓸 수 있게 한국어 Markdown으로 작성하세요.
""".strip()
    markdown = await _complete_office_task(container, prompt)
    path = _write_generated_doc(
        container.settings.archive_dir,
        folder="hr/interview_kits",
        slug=f"{kind}_{payload.role_title}",
        markdown=markdown,
    )
    return GeneratedDocumentPayload(title=payload.role_title, markdown=markdown, path=path)


async def _complete_office_task(container: Container, prompt: str) -> str:
    runtime = container.llm_runtime.read()
    route: LlmRoute = "local" if runtime.default_route == "local" else "cloud"
    provider = runtime.default_provider
    messages = [
        LlmMessage(
            "system",
            "당신은 AI 오피스워크/BPA 컨설턴트입니다. 회사 메모리와 진행 로그를 바탕으로 실행 가능한 문서를 작성합니다.",
        ),
        LlmMessage("user", prompt),
    ]
    response = await _complete_with_provider(
        container,
        messages,
        provider=provider,
        route=route,
        temperature=0.2,
        max_tokens=1600,
    )
    return response.text.strip() or "_(LLM 응답 없음)_"


async def _complete_with_provider(
    container: Container,
    messages: list[LlmMessage],
    *,
    provider: LlmProviderName,
    route: LlmRoute,
    temperature: float,
    max_tokens: int,
) -> LlmResponse:
    try:
        saved = container.secret_store.read(provider)
        if saved and saved.api_key and provider == "openai":
            return await OpenAiProvider(
                api_key=saved.api_key,
                model=saved.model or container.settings.llm.openai_model,
                base_url=saved.base_url or None,
            ).complete(messages, route=route, temperature=temperature, max_tokens=max_tokens)
        if saved and saved.api_key and provider == "anthropic":
            return await AnthropicProvider(
                api_key=saved.api_key,
                model=saved.model or container.settings.llm.anthropic_model,
                base_url=saved.base_url or "https://api.anthropic.com/v1",
            ).complete(messages, route=route, temperature=temperature, max_tokens=max_tokens)
        if saved and saved.api_key and provider == "gemini":
            return await GeminiProvider(
                api_key=saved.api_key,
                model=saved.model or container.settings.llm.gemini_model,
                base_url=saved.base_url or "https://generativelanguage.googleapis.com/v1beta",
            ).complete(messages, route=route, temperature=temperature, max_tokens=max_tokens)
        if (
            saved
            and provider == "vllm"
            and container.settings.llm.vllm_mode != "embedded"
        ):
            return await VllmProvider(
                base_url=saved.base_url or container.settings.llm.vllm_base_url,
                model=saved.model or container.settings.llm.vllm_model,
                api_key=saved.api_key or "EMPTY",
            ).complete(messages, route=route, temperature=temperature, max_tokens=max_tokens)
        if isinstance(container.llm, LlmGateway):
            return await container.llm.complete_with_provider(
                messages,
                provider_name=provider,
                route=route,
                temperature=temperature,
                max_tokens=max_tokens,
            )
        return await container.llm.complete(
            messages,
            route=route,
            temperature=temperature,
            max_tokens=max_tokens,
        )
    except VllmConnectionError as exc:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc


def _office_context(container: Container) -> str:
    recent = _recent_logs(container.settings.archive_dir, limit=8)
    recent_md = "\n".join(
        f"- {entry.get('repo', '')} #{entry.get('external_id', '')} status={entry.get('status', '')} path={entry.get('path', '')}"
        for entry in recent
    )
    return f"""
회사 메모리:
{container.operations_memory.read().to_markdown()}

현재 상태:
{container.archive.status.read()}

최근 업무 로그:
{recent_md or "- 없음"}
""".strip()


def _write_generated_doc(archive_dir: Path, *, folder: str, slug: str, markdown: str) -> str:
    safe_slug = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "_" for ch in slug).strip("_")
    safe_slug = safe_slug[:80] or "generated"
    created = datetime.now(UTC)
    relative = Path(folder) / f"{created.strftime('%Y%m%d_%H%M%S')}_{safe_slug}.md"
    path = archive_dir / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    body = f"# {slug}\n\n_생성: {created.isoformat()}_\n\n{markdown.strip()}\n"
    with portalocker.Lock(path, "w", encoding="utf-8", timeout=5) as fh:
        fh.write(body)
    return relative.as_posix()


def _recent_logs(archive_dir: Path, *, limit: int) -> list[dict[str, Any]]:
    candidates = [
        path
        for path in archive_dir.rglob("*.md")
        if path.name != "current_status.md" and "index" not in path.parts
    ]
    candidates.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    logs: list[dict[str, Any]] = []
    for path in candidates[:limit]:
        text = path.read_text(encoding="utf-8", errors="ignore")
        fm = parse_front_matter(text)
        logs.append(
            {
                "path": str(path.relative_to(archive_dir)),
                "title": path.name,
                "repo": fm.get("repo", ""),
                "source": fm.get("source", ""),
                "external_id": fm.get("external_id", ""),
                "status": fm.get("status", ""),
                "created": fm.get("created", ""),
                "llm_route": fm.get("llm_route", ""),
            }
        )
    return logs


def _summarize_bottlenecks(items: list[dict[str, Any]]) -> str:
    if not items:
        return "아직 업무 로그가 없어 병목을 판단할 수 없습니다."
    rejected = [item for item in items if item.get("status") in {"rejected", "exhausted"}]
    proposed = [item for item in items if item.get("status") == "proposed"]
    lines = [
        f"최근 업무 {len(items)}건 중 제안 완료 {len(proposed)}건, 재검토/거절 {len(rejected)}건입니다.",
    ]
    if rejected:
        lines.append("우선 확인이 필요한 병목 후보:")
        lines.extend(
            f"- {item.get('summary') or item.get('title')} ({item.get('status')})" for item in rejected[:5]
        )
    else:
        lines.append("명시적인 실패 상태는 없습니다. 오래된 진행 항목과 담당자 공백을 확인하세요.")
    return "\n".join(lines)


async def _fetch_github_status(container: Container) -> IntegrationStatusPayload:
    repos = container.settings.github.allowed_repos
    if not repos:
        return IntegrationStatusPayload(
            ok=False,
            configured=False,
            reason="PM_GITHUB_ALLOWED_REPOS is empty",
            items=[],
        )
    token = container.settings.github.app_token
    headers = {"Accept": "application/vnd.github+json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    items: list[dict[str, Any]] = []
    async with httpx.AsyncClient(timeout=10) as client:
        for repo in repos:
            try:
                response = await client.get(
                    f"https://api.github.com/repos/{repo}/issues",
                    headers=headers,
                    params={
                        "state": "open",
                        "labels": container.settings.github.trigger_label,
                        "per_page": 10,
                        "sort": "updated",
                    },
                )
                response.raise_for_status()
                issues = response.json()
                items.append(
                    {
                        "repo": repo,
                        "open_issue_count": len(issues) if isinstance(issues, list) else 0,
                        "issues": [
                            {
                                "number": issue.get("number"),
                                "title": issue.get("title"),
                                "url": issue.get("html_url"),
                                "updated_at": issue.get("updated_at"),
                            }
                            for issue in issues
                            if isinstance(issue, dict)
                        ],
                    }
                )
            except Exception as exc:
                items.append({"repo": repo, "error": str(exc)})
    return IntegrationStatusPayload(ok=True, configured=True, items=items)


async def _fetch_discord_status(container: Container) -> IntegrationStatusPayload:
    bindings = container.discord.channel_map.bindings
    if not bindings:
        return IntegrationStatusPayload(
            ok=False,
            configured=False,
            reason="config/channel_map.yml has no active channel mappings",
            items=[],
        )
    token = container.settings.discord.bot_token
    items: list[dict[str, Any]] = []
    async with httpx.AsyncClient(timeout=10) as client:
        for binding in bindings:
            item: dict[str, Any] = {
                "guild_id": binding.guild_id,
                "channel_id": binding.channel_id,
                "channel_name": binding.channel_name,
                "repo": binding.repo.full_name,
                "live": False,
            }
            if token:
                try:
                    response = await client.get(
                        f"https://discord.com/api/v10/channels/{binding.channel_id}",
                        headers={"Authorization": f"Bot {token}"},
                    )
                    response.raise_for_status()
                    data = response.json()
                    item.update({"live": True, "name": data.get("name", binding.channel_name)})
                except Exception as exc:
                    item["error"] = str(exc)
            else:
                item["reason"] = "PM_DISCORD_BOT_TOKEN is empty"
            items.append(item)
    return IntegrationStatusPayload(ok=True, configured=True, items=items)
