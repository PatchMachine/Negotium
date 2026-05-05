"""JSON API routes for the local frontend."""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated, Any, Literal, cast

import httpx
import portalocker
import yaml
from fastapi import APIRouter, File, Form, Header, HTTPException, UploadFile, status
from fastapi.responses import StreamingResponse

from patch_machine.adapters.llm.anthropic_adapter import AnthropicProvider
from patch_machine.adapters.llm.catalog import (
    default_base_url,
    list_models,
    provider_payload,
    require_provider,
    search_huggingface_models,
)
from patch_machine.adapters.llm.gateway import LlmGateway
from patch_machine.adapters.llm.gemini_adapter import GeminiProvider
from patch_machine.adapters.llm.openai_adapter import OpenAiProvider
from patch_machine.adapters.llm.vllm_adapter import VllmConnectionError, VllmProvider
from patch_machine.adapters.llm.vllm_embedded_adapter import VllmEmbeddedError
from patch_machine.app.api.patchops_execution import create_patchops_execution_router
from patch_machine.app.container import Container
from patch_machine.app.initial_setup import ParsedSetupFile, parse_setup_uploads
from patch_machine.app.schemas.core import (
    AccountRequestPayload,
    AgentPlanRequest,
    AiJobStatusPayload,
    ApiKeyPayload,
    ApiStatusPayload,
    AuthSessionPayload,
    ChatRequest,
    ChatResponse,
    CompanyProfilePayload,
    ContextCompressRequest,
    CurrentUserPayload,
    DeletionRequestPayload,
    DiscordChannelBindingPayload,
    DiscordConnectorPayload,
    DocumentReadPayload,
    GeneratedDocumentPayload,
    GitHubConnectorPayload,
    HandoverRequest,
    HiringRequest,
    HuggingFaceModelItemPayload,
    HuggingFaceModelSearchPayload,
    HuggingFaceModelSearchResultPayload,
    InitialOfficeAnalyzeRequest,
    InitialOfficeSetupResult,
    IntegrationConfigPayload,
    IntegrationStatusPayload,
    LlmRuntimePayload,
    LocalLlmStatusPayload,
    LoginPayload,
    MemoryRefreshRequest,
    MemorySchemaPayload,
    MemorySchemaProposalPayload,
    OfficeDocumentRequest,
    OperationsMemoryPayload,
    PatchRecordCreatePayload,
    PatchRecordDetailPayload,
    PatchRecordPayload,
    PatchRunApprovalPayload,
    PatchRunCreatePayload,
    PatchRunPayload,
    ProgressPayload,
    PromoteMemoryPayload,
    ProviderModelPayload,
    ProviderModelPreviewPayload,
    ReadableContextBundlePayload,
    ReadableContextPreviewRequest,
    ReadableContextSourcePayload,
    RolePayload,
    SetupAdminPayload,
    SetupStatusPayload,
    TokenLimitPayload,
    TokenLimitStatusPayload,
    TokenUsageEntryPayload,
    TokenUsageSummaryPayload,
    UserPayload,
    VolatileMemoryPayload,
    WorkArchitecturePayload,
    WorkArchitectureRequest,
    WorkItemsPayload,
    WorkMemoryPayload,
    WorkScheduleGenerationRequest,
    WorkScheduleItemPayload,
)
from patch_machine.app.schemas.issue_memory import (
    McpToolCallPayload,
)
from patch_machine.app.services.context_firewall_service import (
    default_policy_payload,
    load_context_firewall_policy,
    record_firewall_audit,
    sanitize_context,
    sanitize_llm_messages,
    sanitize_llm_response,
)
from patch_machine.app.services.mcp_hub_service import (
    call_tool,
    handle_json_rpc,
    list_prompts,
    list_resources,
    list_tool_descriptors,
    read_resource,
    record_mcp_audit,
    render_mcp_prompt,
    required_permission,
)
from patch_machine.app.services.patchops_service import (
    analyze_patch_run,
    draft_patch_artifacts,
    write_patch_memory,
)
from patch_machine.app.services.setup_catalog import (
    recommend_patchnote_setup,
    render_recommendation_markdown,
)
from patch_machine.archive.access_control import ALL_PERMISSIONS, UserRecord
from patch_machine.archive.agent_execution import AgentPlan
from patch_machine.archive.ai_jobs import AiJobRecord
from patch_machine.archive.auth_store import RequestStatus
from patch_machine.archive.context_compressor import CompressedContext
from patch_machine.archive.deletion_requests import DeletionRequest
from patch_machine.archive.integration_config import (
    DiscordChannelBindingConfig,
    DiscordConnectorConfig,
    GitHubConnectorConfig,
    IntegrationConfig,
)
from patch_machine.archive.llm_runtime import LlmProviderName, LlmRuntimeConfig, LlmTaskRoute
from patch_machine.archive.patch_records import PatchRecord
from patch_machine.archive.patch_runs import PatchRun
from patch_machine.archive.schema import parse_front_matter
from patch_machine.archive.secret_store import ApiKeyRecord
from patch_machine.archive.token_usage import (
    TokenLimitConfig,
    TokenLimitExceededError,
)
from patch_machine.archive.volatile_memory import MemoryScope, VolatileMemory
from patch_machine.archive.work_memory import WorkMemory, WorkScheduleItem
from patch_machine.domain.entities import LlmRoute
from patch_machine.domain.ports import LlmMessage, LlmResponse
from patch_machine.prompts import render as render_prompt

_PRELOAD_TASKS: set[asyncio.Task[None]] = set()


def create_operations_api_router(container: Container) -> APIRouter:
    """Create frontend-facing API routes bound to the app container."""
    router = APIRouter(prefix="/api", tags=["frontend-api"])
    router.include_router(create_patchops_execution_router(container))

    @router.get("/auth/setup-status")
    async def setup_status() -> SetupStatusPayload:
        return SetupStatusPayload(setup_required=container.auth_store.setup_required())

    @router.post("/auth/setup-admin")
    async def setup_admin(payload: SetupAdminPayload) -> AuthSessionPayload:
        if not container.auth_store.setup_required():
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST, detail="admin user is already configured"
            )
        try:
            container.auth_store.create_user(
                user_id=payload.user_id.strip(),
                display_name=payload.display_name.strip(),
                password=payload.password,
            )
            container.access_control.upsert_user(
                UserRecord(
                    id=payload.user_id.strip(),
                    display_name=payload.display_name.strip(),
                    title=payload.title.strip() or "관리자",
                    role_id="owner",
                    active=True,
                )
            )
            token = container.auth_store.authenticate(payload.user_id.strip(), payload.password)
        except ValueError as exc:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
        if token is None:
            raise HTTPException(
                status.HTTP_500_INTERNAL_SERVER_ERROR, detail="failed to create admin session"
            )
        _audit(
            container,
            actor=payload.user_id.strip(),
            action="auth.setup_admin",
            target="user",
            target_id=payload.user_id.strip(),
        )
        return AuthSessionPayload(
            token=token, user=_user_payload(container, payload.user_id.strip())
        )

    @router.post("/auth/login")
    async def login(payload: LoginPayload) -> AuthSessionPayload:
        token = container.auth_store.authenticate(payload.user_id.strip(), payload.password)
        if token is None:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="invalid user id or password")
        return AuthSessionPayload(
            token=token, user=_user_payload(container, payload.user_id.strip())
        )

    @router.post("/auth/logout")
    async def logout(
        x_pm_user: str | None = Header(default=None, alias="X-PM-User"),
    ) -> dict[str, bool]:
        token = _extract_token(x_pm_user)
        if token:
            container.auth_store.revoke_token(token)
        return {"ok": True}

    @router.get("/auth/me")
    async def me(
        x_pm_user: str | None = Header(default=None, alias="X-PM-User"),
    ) -> CurrentUserPayload:
        user_id = _resolve_authenticated_user(container, x_pm_user)
        if user_id is None:
            return CurrentUserPayload(authenticated=False)
        return CurrentUserPayload(authenticated=True, user=_user_payload(container, user_id))

    @router.post("/account-requests")
    async def create_account_request(payload: AccountRequestPayload) -> dict[str, object]:
        try:
            request = container.auth_store.request_account(
                user_id=payload.user_id.strip(),
                display_name=payload.display_name.strip(),
                title=payload.title.strip(),
                password=payload.password,
            )
        except ValueError as exc:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
        _audit(
            container,
            actor="anonymous",
            action="account_request.create",
            target="account_request",
            target_id=request.id,
            details={"user_id": request.user_id},
        )
        return {"ok": True, "request": request.to_dict()}

    @router.post("/setup/office/analyze")
    async def analyze_initial_office_setup(
        payload: InitialOfficeAnalyzeRequest,
        x_pm_user: str | None = Header(default=None, alias="X-PM-User"),
    ) -> InitialOfficeSetupResult:
        actor = _require(container, x_pm_user, "admin:users")
        uploads = _selected_upload_records(container.uploads.list(), payload.upload_ids)
        parsed_files = parse_setup_uploads(uploads, archive_root=container.settings.archive_dir)
        prompt = _initial_office_setup_prompt(
            message=payload.message,
            intent=payload.intent,
            parsed_files=parsed_files,
            company_profile=payload.company_profile,
        )
        job = _start_ai_job(
            container,
            task="initial_office_setup.analyze",
            actor=actor,
            input_summary=payload.message or payload.company_profile.company_name,
            used_sources=[str(item.path) for item in parsed_files],
        )
        try:
            markdown = await _complete_office_task(container, prompt, task="memory_summary")
            job = _finish_ai_job(
                container,
                job,
                status="succeeded",
                used_sources=[str(item.path) for item in parsed_files],
            )
        except Exception as exc:
            _finish_ai_job(container, job, status="failed", error=str(exc))
            raise
        result = _parse_initial_setup_result(
            markdown,
            parsed_files=parsed_files,
            company_profile=payload.company_profile,
        )
        result.ai_job = _ai_job_payload(job).model_dump()
        return result

    @router.post("/setup/office/apply")
    async def apply_initial_office_setup(
        payload: InitialOfficeSetupResult,
        x_pm_user: str | None = Header(default=None, alias="X-PM-User"),
    ) -> dict[str, object]:
        actor = _require(container, x_pm_user, "admin:users")
        operations_memory, work_memory = _initial_setup_memories_with_recommendations(payload)
        if operations_memory:
            container.operations_memory.write(
                OperationsMemoryPayload(**operations_memory).to_memory()
            )
        if work_memory:
            container.work_memory.write(WorkMemoryPayload(**work_memory).to_memory())
        for role in payload.roles:
            if role.id.strip():
                container.access_control.upsert_role(role.to_record())
        for user in payload.users:
            if user.id.strip():
                container.access_control.upsert_user(user.to_record())
        if payload.llm_task_routes:
            _apply_initial_setup_llm_routes(container, payload.llm_task_routes)
        _audit(
            container,
            actor=actor,
            action="setup.office.apply",
            target="initial_office_setup",
            details={
                "roles": [role.id for role in payload.roles],
                "users": [user.id for user in payload.users],
                "sensitive_hint": payload.sensitive_hint,
                "recommended_package": payload.recommended_package,
                "agent_packs": [item.get("id") for item in payload.agent_packs],
                "templates": [item.get("id") for item in payload.templates],
                "workflows": [item.get("id") for item in payload.workflows],
                "security_defaults": [item.get("id") for item in payload.security_defaults],
                "integration_priorities": [
                    item.get("id") for item in payload.integration_priorities
                ],
            },
        )
        return {
            "ok": True,
            "access_control": {**container.access_control.read(), "permissions": ALL_PERMISSIONS},
        }

    @router.get("/memory/permanent/sources")
    async def list_permanent_sources(
        limit: int = 50,
        x_pm_user: str | None = Header(default=None, alias="X-PM-User"),
    ) -> dict[str, object]:
        _require(container, x_pm_user, "work:read")
        return {"sources": container.permanent_memory.recent(limit=max(1, min(limit, 200)))}

    @router.get("/memory/permanent/recent")
    async def recent_permanent_memory(
        limit: int = 50,
        x_pm_user: str | None = Header(default=None, alias="X-PM-User"),
    ) -> dict[str, object]:
        _require(container, x_pm_user, "work:read")
        return {"sources": container.permanent_memory.recent(limit=max(1, min(limit, 200)))}

    @router.get("/memory/permanent/search")
    async def search_permanent_memory(
        q: str = "",
        limit: int = 50,
        x_pm_user: str | None = Header(default=None, alias="X-PM-User"),
    ) -> dict[str, object]:
        _require(container, x_pm_user, "work:read")
        return {"sources": container.permanent_memory.search(q, limit=max(1, min(limit, 200)))}

    @router.get("/memory/readable-sources")
    async def list_readable_sources(
        q: str = "",
        limit: int = 100,
        x_pm_user: str | None = Header(default=None, alias="X-PM-User"),
    ) -> dict[str, object]:
        _require(container, x_pm_user, "work:read")
        source_limit = max(1, min(limit, 300))
        sources = (
            container.permanent_memory.search(q, limit=source_limit)
            if q.strip()
            else container.permanent_memory.recent(limit=source_limit)
        )
        return {
            "sources": [
                _readable_source_payload(source, selected=False, order=index).model_dump()
                for index, source in enumerate(sources)
            ]
        }

    @router.get("/memory/readable-source")
    async def read_readable_source(
        source_id: str,
        x_pm_user: str | None = Header(default=None, alias="X-PM-User"),
    ) -> ReadableContextSourcePayload:
        _require(container, x_pm_user, "work:read")
        try:
            source = container.permanent_memory.read_source(source_id)
        except FileNotFoundError as exc:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail="source not found") from exc
        except ValueError as exc:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
        return _readable_source_payload(source, selected=True, order=0)

    @router.post("/memory/readable-context/preview")
    async def preview_readable_context(
        payload: ReadableContextPreviewRequest,
        x_pm_user: str | None = Header(default=None, alias="X-PM-User"),
    ) -> ReadableContextBundlePayload:
        _require(container, x_pm_user, "work:read")
        return _readable_context_bundle(container, payload)

    @router.post("/memory/permanent/promote")
    async def promote_permanent_memory(
        payload: PromoteMemoryPayload,
        x_pm_user: str | None = Header(default=None, alias="X-PM-User"),
    ) -> dict[str, object]:
        actor = _require(container, x_pm_user, "memory:write")
        promoted = container.permanent_memory.promote(
            title=payload.title,
            content=payload.content,
            source_refs=payload.source_refs,
            actor=actor,
        )
        _audit(
            container,
            actor=actor,
            action="memory.promote",
            target="permanent_memory",
            target_id=str(promoted["path"]),
        )
        return {"ok": True, "memory": promoted}

    @router.get("/memory/conversations")
    async def list_conversations(
        user_id: str | None = None,
        limit: int = 100,
        x_pm_user: str | None = Header(default=None, alias="X-PM-User"),
    ) -> dict[str, object]:
        actor = _require(container, x_pm_user, "work:read")
        requested_user = (
            user_id if container.access_control.has_permission(actor, "admin:users") else actor
        )
        return {
            "records": container.conversations.list_recent(
                user_id=requested_user, limit=max(1, min(limit, 500))
            )
        }

    @router.get("/memory/volatile")
    async def list_volatile_memory(
        scope: MemoryScope | None = None,
        x_pm_user: str | None = Header(default=None, alias="X-PM-User"),
    ) -> dict[str, object]:
        _require(container, x_pm_user, "work:read")
        return {"memories": container.volatile_memory.list(scope=scope)}

    @router.get("/memory/volatile/{scope}/{key}")
    async def read_volatile_memory(
        scope: MemoryScope,
        key: str,
        x_pm_user: str | None = Header(default=None, alias="X-PM-User"),
    ) -> VolatileMemoryPayload:
        _require(container, x_pm_user, "work:read")
        return VolatileMemoryPayload.from_memory(
            container.volatile_memory.read(scope=scope, key=key)
        )

    @router.put("/memory/volatile/{scope}/{key}")
    async def write_volatile_memory(
        scope: MemoryScope,
        key: str,
        payload: VolatileMemoryPayload,
        x_pm_user: str | None = Header(default=None, alias="X-PM-User"),
    ) -> VolatileMemoryPayload:
        actor = _require(container, x_pm_user, "memory:write")
        memory = payload.to_memory()
        saved = container.volatile_memory.write(
            VolatileMemory.from_mapping({**memory.to_dict(), "scope": scope, "key": key})
        )
        _audit(
            container,
            actor=actor,
            action="memory.volatile.upsert",
            target="volatile_memory",
            target_id=f"{scope}:{key}",
        )
        return VolatileMemoryPayload.from_memory(saved)

    @router.delete("/memory/volatile/{scope}/{key}")
    async def delete_volatile_memory(
        scope: MemoryScope,
        key: str,
        x_pm_user: str | None = Header(default=None, alias="X-PM-User"),
    ) -> dict[str, object]:
        actor = _require(container, x_pm_user, "memory:write")
        ok = container.volatile_memory.delete(scope=scope, key=key)
        _audit(
            container,
            actor=actor,
            action="memory.volatile.delete",
            target="volatile_memory",
            target_id=f"{scope}:{key}",
        )
        return {"ok": ok}

    @router.post("/memory/volatile/refresh")
    async def refresh_volatile_memory(
        payload: MemoryRefreshRequest,
        x_pm_user: str | None = Header(default=None, alias="X-PM-User"),
    ) -> VolatileMemoryPayload:
        actor = _require(container, x_pm_user, "llm:chat")
        key = payload.key.strip() or actor
        lim = max(1, min(payload.source_limit, 50))
        sources = container.permanent_memory.resolve_sources(
            query=payload.query,
            limit=lim,
            source_ids=payload.source_ids if payload.source_ids else None,
        )
        if not sources:
            sources = container.permanent_memory.search(payload.query, limit=lim)
        prompt = _memory_refresh_prompt(payload.query, sources)
        summary = await _complete_office_task(container, prompt, task="memory_summary")
        saved = container.volatile_memory.write(
            VolatileMemory(
                scope=payload.scope,
                key=key,
                summary=summary,
                current_intent=payload.query,
                relevant_sources=[str(source["path"]) for source in sources],
            )
        )
        _audit(
            container,
            actor=actor,
            action="memory.volatile.refresh",
            target="volatile_memory",
            target_id=f"{payload.scope}:{key}",
        )
        return VolatileMemoryPayload.from_memory(saved)

    @router.post("/memory/context/compress")
    async def compress_context_memory(
        payload: ContextCompressRequest,
        x_pm_user: str | None = Header(default=None, alias="X-PM-User"),
    ) -> dict[str, object]:
        actor = _require(container, x_pm_user, "llm:chat")
        key = payload.key.strip() or actor
        lim = max(1, min(payload.source_limit, 50))
        sources = container.permanent_memory.resolve_sources(
            query=payload.query,
            limit=lim,
            source_ids=payload.source_ids if payload.source_ids else None,
        )
        if not sources:
            sources = container.permanent_memory.search(payload.query, limit=lim)
        volatile_md = ""
        if payload.include_volatile:
            volatile_md = _volatile_memories_markdown(container)
        prompt = _context_compression_prompt(
            payload.query,
            payload.token_budget,
            sources,
            volatile_appendix=volatile_md,
        )
        summary = await _complete_office_task(container, prompt, task="memory_summary")
        saved = container.compressed_context.write(
            CompressedContext(
                scope=payload.scope,
                key=key,
                summary=summary,
                facts=_lines_from_markdown(summary, prefix="-"),
                source_refs=[str(source["path"]) for source in sources],
                token_budget=payload.token_budget,
            )
        )
        _audit(
            container,
            actor=actor,
            action="memory.context.compress",
            target="compressed_context",
            target_id=f"{payload.scope}:{key}",
        )
        volatile_refs = [f"{item['scope']}:{item['key']}" for item in container.volatile_memory.list()] if payload.include_volatile else []
        return {
            "context": saved.to_dict(),
            "used_sources": sources,
            "volatile_memories": volatile_refs,
        }

    @router.get("/memory/context/compressed")
    async def read_compressed_context(
        scope: MemoryScope = "global",
        key: str = "default",
        x_pm_user: str | None = Header(default=None, alias="X-PM-User"),
    ) -> dict[str, object]:
        _require(container, x_pm_user, "work:read")
        return {"context": container.compressed_context.read(scope=scope, key=key).to_dict()}

    @router.get("/ai-jobs/recent")
    async def list_ai_jobs(
        limit: int = 30,
        x_pm_user: str | None = Header(default=None, alias="X-PM-User"),
    ) -> dict[str, object]:
        _require(container, x_pm_user, "work:read")
        return {
            "jobs": [
                _ai_job_payload(record).model_dump()
                for record in container.ai_jobs.recent(limit=max(1, min(limit, 200)))
            ]
        }

    @router.get("/ai-jobs/{job_id}")
    async def read_ai_job(
        job_id: str,
        x_pm_user: str | None = Header(default=None, alias="X-PM-User"),
    ) -> AiJobStatusPayload:
        _require(container, x_pm_user, "work:read")
        record = container.ai_jobs.get(job_id)
        if record is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail="AI job not found")
        return _ai_job_payload(record)

    @router.get("/memory/schema")
    async def list_memory_schema(
        x_pm_user: str | None = Header(default=None, alias="X-PM-User"),
    ) -> dict[str, object]:
        _require(container, x_pm_user, "work:read")
        return {
            "schemas": container.memory_schema.list(),
            "proposals": container.memory_schema.proposals(),
        }

    @router.post("/memory/schema")
    async def upsert_memory_schema(
        payload: MemorySchemaPayload,
        x_pm_user: str | None = Header(default=None, alias="X-PM-User"),
    ) -> dict[str, object]:
        actor = _require(container, x_pm_user, "admin:users")
        schema = container.memory_schema.upsert(payload.to_record(actor=actor), actor=actor)
        _audit(
            container,
            actor=actor,
            action="memory.schema.upsert",
            target="memory_schema",
            target_id=schema.type_id,
        )
        return {"ok": True, "schema": schema.to_dict(), "schemas": container.memory_schema.list()}

    @router.post("/memory/schema/propose")
    async def propose_memory_schema(
        payload: MemorySchemaProposalPayload,
        x_pm_user: str | None = Header(default=None, alias="X-PM-User"),
    ) -> dict[str, object]:
        actor = _require(container, x_pm_user, "memory:write")
        proposal = container.memory_schema.propose(
            actor=actor, mode=payload.mode, proposal=payload.proposal
        )
        _audit(
            container,
            actor=actor,
            action="memory.schema.propose",
            target="memory_schema_proposal",
            target_id=str(proposal["id"]),
        )
        return {"ok": True, "proposal": proposal}

    @router.post("/memory/schema/proposals/{proposal_id}/approve")
    async def approve_memory_schema(
        proposal_id: str,
        x_pm_user: str | None = Header(default=None, alias="X-PM-User"),
    ) -> dict[str, object]:
        actor = _require(container, x_pm_user, "admin:users")
        proposal = container.memory_schema.approve(proposal_id, actor=actor)
        _audit(
            container,
            actor=actor,
            action="memory.schema.approve",
            target="memory_schema_proposal",
            target_id=proposal_id,
        )
        return {"ok": True, "proposal": proposal, "schemas": container.memory_schema.list()}

    @router.post("/memory/schema/code-proposals")
    async def create_memory_schema_code_proposal(
        payload: MemorySchemaProposalPayload,
        x_pm_user: str | None = Header(default=None, alias="X-PM-User"),
    ) -> dict[str, object]:
        actor = _require(container, x_pm_user, "admin:users")
        proposal = container.memory_schema.propose(
            actor=actor, mode="llm_code_write", proposal=payload.proposal
        )
        _audit(
            container,
            actor=actor,
            action="memory.schema.code_propose",
            target="memory_schema_proposal",
            target_id=str(proposal["id"]),
        )
        return {"ok": True, "proposal": proposal}

    @router.get("/memory/deletion-requests")
    async def list_deletion_requests(
        x_pm_user: str | None = Header(default=None, alias="X-PM-User"),
    ) -> dict[str, object]:
        _require(container, x_pm_user, "admin:users")
        return {"requests": container.deletion_requests.list()}

    @router.post("/memory/deletion-requests")
    async def create_deletion_request(
        payload: DeletionRequestPayload,
        x_pm_user: str | None = Header(default=None, alias="X-PM-User"),
    ) -> dict[str, object]:
        actor = _require(container, x_pm_user, "memory:write")
        request = container.deletion_requests.create(
            DeletionRequest.create(**payload.model_dump(), requester=actor)
        )
        _audit(
            container,
            actor=actor,
            action="memory.delete_requested",
            target=payload.target_type,
            target_id=payload.target_id,
        )
        return {"ok": True, "request": request.to_dict()}

    @router.post("/memory/deletion-requests/{request_id}/approve")
    async def approve_deletion_request(
        request_id: str,
        x_pm_user: str | None = Header(default=None, alias="X-PM-User"),
    ) -> dict[str, object]:
        actor = _require(container, x_pm_user, "admin:users")
        request = container.deletion_requests.decide(request_id, actor=actor, approved=True)
        _audit(
            container,
            actor=actor,
            action="memory.delete_approved",
            target=request.target_type,
            target_id=request.target_id,
        )
        return {"ok": True, "request": request.to_dict()}

    @router.post("/memory/deletion-requests/{request_id}/reject")
    async def reject_deletion_request(
        request_id: str,
        x_pm_user: str | None = Header(default=None, alias="X-PM-User"),
    ) -> dict[str, object]:
        actor = _require(container, x_pm_user, "admin:users")
        request = container.deletion_requests.decide(request_id, actor=actor, approved=False)
        _audit(
            container,
            actor=actor,
            action="memory.delete_rejected",
            target=request.target_type,
            target_id=request.target_id,
        )
        return {"ok": True, "request": request.to_dict()}

    @router.post("/agent/plans/generate")
    async def generate_agent_plan(
        payload: AgentPlanRequest,
        x_pm_user: str | None = Header(default=None, alias="X-PM-User"),
    ) -> dict[str, object]:
        actor = _require(container, x_pm_user, "memory:write")
        memory_refs = payload.memory_refs or [
            str(source["path"]) for source in container.permanent_memory.recent(limit=5)
        ]
        schedule_refs = payload.schedule_refs or [
            str(item["id"]) for item in container.work_schedule.list()[:10]
        ]
        steps = _agent_plan_steps(payload.objective, schedule_refs, memory_refs)
        plan = container.agent_execution.save_plan(
            AgentPlan.create(
                title=payload.title or payload.objective,
                objective=payload.objective,
                mode=payload.mode,
                schedule_refs=schedule_refs,
                memory_refs=memory_refs,
                steps=steps,
                created_by=actor,
            )
        )
        _audit(
            container,
            actor=actor,
            action="agent.plan.generate",
            target="agent_plan",
            target_id=plan.id,
        )
        return {"ok": True, "plan": plan.to_dict()}

    @router.get("/agent/plans")
    async def list_agent_plans(
        x_pm_user: str | None = Header(default=None, alias="X-PM-User"),
    ) -> dict[str, object]:
        _require(container, x_pm_user, "work:read")
        return {"plans": container.agent_execution.list_plans()}

    @router.post("/agent/plans/{plan_id}/approve")
    async def approve_agent_plan(
        plan_id: str,
        x_pm_user: str | None = Header(default=None, alias="X-PM-User"),
    ) -> dict[str, object]:
        actor = _require(container, x_pm_user, "admin:users")
        plan = container.agent_execution.approve_plan(plan_id, actor=actor)
        _audit(
            container,
            actor=actor,
            action="agent.plan.approve",
            target="agent_plan",
            target_id=plan_id,
        )
        return {"ok": True, "plan": plan.to_dict()}

    @router.post("/agent/plans/{plan_id}/run")
    async def run_agent_plan(
        plan_id: str,
        x_pm_user: str | None = Header(default=None, alias="X-PM-User"),
    ) -> dict[str, object]:
        actor = _require(container, x_pm_user, "memory:write")
        plan = container.agent_execution.read_plan(plan_id)
        if plan.status != "approved" and plan.mode != "plan_only":
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST, detail="agent plan requires approval before run"
            )
        run = container.agent_execution.append_run(
            plan_id, actor=actor, event="run_requested", details={"mode": plan.mode}
        )
        _audit(
            container,
            actor=actor,
            action="agent.plan.run_requested",
            target="agent_plan",
            target_id=plan_id,
        )
        return {"ok": True, "run": run}

    @router.post("/agent/runs/{run_id}/approve-step")
    async def approve_agent_run_step(
        run_id: str,
        x_pm_user: str | None = Header(default=None, alias="X-PM-User"),
    ) -> dict[str, object]:
        actor = _require(container, x_pm_user, "admin:users")
        _audit(
            container,
            actor=actor,
            action="agent.run.step_approved",
            target="agent_run",
            target_id=run_id,
        )
        return {"ok": True, "run_id": run_id, "approved_by": actor}

    @router.post("/patch-runs")
    async def create_patch_run(
        payload: PatchRunCreatePayload,
        x_pm_user: str | None = Header(default=None, alias="X-PM-User"),
    ) -> dict[str, object]:
        actor = _require(container, x_pm_user, "memory:write")
        run = container.patch_runs.create(
            PatchRun.create(
                repo_id=payload.repo_id,
                request=payload.request,
                autonomy_level=payload.autonomy_level,
                privacy_mode=payload.privacy_mode,
                target_branch=payload.target_branch,
                constraints=payload.constraints,
                created_by=actor,
            )
        )
        container.patch_runs.append_event(
            run.id,
            event_type="patch.created",
            summary="PatchOps run을 생성했습니다.",
            payload={
                "repo_id": run.repo_id,
                "autonomy_level": run.autonomy_level,
                "privacy_mode": run.privacy_mode,
            },
        )
        _audit(
            container, actor=actor, action="patchops.create", target="patch_run", target_id=run.id
        )
        return {"ok": True, "patch_run": PatchRunPayload(**run.to_dict())}

    @router.get("/patch-runs")
    async def list_patch_runs(
        x_pm_user: str | None = Header(default=None, alias="X-PM-User"),
    ) -> dict[str, object]:
        _require(container, x_pm_user, "work:read")
        return {"patch_runs": container.patch_runs.list()}

    @router.get("/patch-runs/{patch_id}")
    async def read_patch_run(
        patch_id: str,
        x_pm_user: str | None = Header(default=None, alias="X-PM-User"),
    ) -> dict[str, object]:
        _require(container, x_pm_user, "work:read")
        try:
            run = container.patch_runs.read(patch_id)
        except ValueError as exc:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
        return {"patch_run": run.to_dict(), "events": container.patch_runs.list_events(patch_id)}

    @router.get("/patch-runs/{patch_id}/events")
    async def list_patch_run_events(
        patch_id: str,
        x_pm_user: str | None = Header(default=None, alias="X-PM-User"),
    ) -> dict[str, object]:
        _require(container, x_pm_user, "work:read")
        return {"events": container.patch_runs.list_events(patch_id)}

    @router.post("/patch-runs/{patch_id}/analyze")
    async def analyze_patch_run_endpoint(
        patch_id: str,
        x_pm_user: str | None = Header(default=None, alias="X-PM-User"),
    ) -> dict[str, object]:
        actor = _require(container, x_pm_user, "memory:write")
        try:
            run = container.patch_runs.read(patch_id)
        except ValueError as exc:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

        async def complete(prompt: str, task: str) -> str:
            return await _complete_patchops_task(container, prompt, task=task)

        analyzed = await analyze_patch_run(
            container, run.with_updates(status="REPO_SCANNING"), complete
        )
        _audit(
            container,
            actor=actor,
            action="patchops.analyze",
            target="patch_run",
            target_id=patch_id,
        )
        return {
            "ok": True,
            "patch_run": analyzed.to_dict(),
            "events": container.patch_runs.list_events(patch_id),
        }

    @router.post("/patch-runs/{patch_id}/approve-plan")
    async def approve_patch_plan(
        patch_id: str,
        payload: PatchRunApprovalPayload,
        x_pm_user: str | None = Header(default=None, alias="X-PM-User"),
    ) -> dict[str, object]:
        actor = _require(container, x_pm_user, "admin:users")
        status_value = "WAITING_APPROVAL" if payload.decision == "approve" else "CANCELLED"
        try:
            run = container.patch_runs.update(
                patch_id,
                status=status_value,
                approved_by=actor if payload.decision == "approve" else "",
            )
        except ValueError as exc:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
        container.patch_runs.append_event(
            patch_id,
            event_type="approval.decided",
            summary=f"패치 계획 {payload.decision}",
            payload={"decision": payload.decision, "comment": payload.comment, "actor": actor},
        )
        _audit(
            container,
            actor=actor,
            action="patchops.approval",
            target="patch_run",
            target_id=patch_id,
        )
        return {"ok": True, "patch_run": run.to_dict()}

    @router.post("/patch-runs/{patch_id}/draft-diff")
    async def draft_patch_diff(
        patch_id: str,
        x_pm_user: str | None = Header(default=None, alias="X-PM-User"),
    ) -> dict[str, object]:
        actor = _require(container, x_pm_user, "memory:write")
        try:
            run = container.patch_runs.read(patch_id)
        except ValueError as exc:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

        async def complete(prompt: str, task: str) -> str:
            return await _complete_patchops_task(container, prompt, task=task)

        drafted = await draft_patch_artifacts(container, run, complete)
        _audit(
            container,
            actor=actor,
            action="patchops.draft_diff",
            target="patch_run",
            target_id=patch_id,
        )
        return {
            "ok": True,
            "patch_run": drafted.to_dict(),
            "events": container.patch_runs.list_events(patch_id),
        }

    @router.post("/patch-runs/{patch_id}/write-memory")
    async def write_patch_run_memory(
        patch_id: str,
        x_pm_user: str | None = Header(default=None, alias="X-PM-User"),
    ) -> dict[str, object]:
        actor = _require(container, x_pm_user, "memory:write")
        try:
            run = container.patch_runs.read(patch_id)
        except ValueError as exc:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

        async def complete(prompt: str, task: str) -> str:
            return await _complete_patchops_task(container, prompt, task=task)

        memory = await write_patch_memory(container, run, complete, actor=actor)
        _audit(
            container,
            actor=actor,
            action="patchops.memory_write",
            target="patch_run",
            target_id=patch_id,
        )
        return {
            "ok": True,
            "memory": memory,
            "patch_run": container.patch_runs.read(patch_id).to_dict(),
        }

    @router.get("/mcp-hub/tools")
    async def list_mcp_hub_tools(
        x_pm_user: str | None = Header(default=None, alias="X-PM-User"),
    ) -> dict[str, object]:
        _require(container, x_pm_user, "work:read")
        tools = list_tool_descriptors()
        return {
            "tools": tools,
            "transport": "http-compatible+json-rpc+sse-skeleton",
            "count": len(tools),
        }

    @router.post("/mcp-hub/tools/{tool_name:path}")
    async def call_mcp_hub_tool(
        tool_name: str,
        payload: McpToolCallPayload,
        x_pm_user: str | None = Header(default=None, alias="X-PM-User"),
    ) -> dict[str, object]:
        permission = required_permission(tool_name)
        actor = _require(container, x_pm_user, permission)
        try:
            call_result = call_tool(container, tool_name, payload.arguments)
        except ValueError as exc:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
        record_mcp_audit(
            container,
            actor=actor,
            tool_name=tool_name,
            arguments=payload.arguments,
            result_summary=call_result.result_summary,
            risk_level=call_result.risk_level,
            policy=call_result.policy,
            guard_findings=call_result.guard_findings,
        )
        _audit(
            container,
            actor=actor,
            action="mcp_hub.tool_call",
            target="mcp_tool",
            target_id=tool_name,
            details={
                "tool_name": tool_name,
                "arguments": payload.arguments,
                "result_summary": call_result.result_summary,
                "risk_level": call_result.risk_level,
                "guard_findings": call_result.guard_findings,
            },
        )
        return {"ok": True, "tool": tool_name, "result": call_result.result}

    @router.get("/mcp-hub/resources")
    async def list_mcp_hub_resources(
        x_pm_user: str | None = Header(default=None, alias="X-PM-User"),
    ) -> dict[str, object]:
        _require(container, x_pm_user, "work:read")
        resources = list_resources(container)
        return {"resources": resources, "count": len(resources)}

    @router.get("/mcp-hub/resources/{resource_uri:path}")
    async def read_mcp_hub_resource(
        resource_uri: str,
        x_pm_user: str | None = Header(default=None, alias="X-PM-User"),
    ) -> dict[str, object]:
        _require(container, x_pm_user, "work:read")
        try:
            return read_resource(container, resource_uri)
        except ValueError as exc:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    @router.get("/mcp-hub/prompts")
    async def list_mcp_hub_prompts(
        x_pm_user: str | None = Header(default=None, alias="X-PM-User"),
    ) -> dict[str, object]:
        _require(container, x_pm_user, "work:read")
        prompts = list_prompts()
        return {"prompts": prompts, "count": len(prompts)}

    @router.get("/mcp-hub/audit")
    async def list_mcp_hub_audit(
        limit: int = 100,
        x_pm_user: str | None = Header(default=None, alias="X-PM-User"),
    ) -> dict[str, object]:
        _require(container, x_pm_user, "admin:users")
        records = container.mcp_audit.list(limit=limit)
        return {"records": records, "count": len(records)}

    @router.post("/security/context-firewall/sanitize")
    async def sanitize_context_firewall(
        payload: dict[str, Any],
        x_pm_user: str | None = Header(default=None, alias="X-PM-User"),
    ) -> dict[str, object]:
        actor = _require(container, x_pm_user, "admin:users")
        destination = str(payload.get("destination") or "frontier_llm")
        task_type = str(payload.get("task_type") or "manual_security_test")
        source_uri = str(payload.get("source_uri") or "")
        content = payload.get("content", payload.get("sources", payload))
        result = sanitize_context(
            content,
            destination=destination,
            task_type=task_type,
            source_uri=source_uri,
            policy=load_context_firewall_policy(container.settings.workspace_dir),
        )
        result = record_firewall_audit(
            container,
            result,
            actor=actor,
            agent_run_id=str(payload.get("agent_run_id") or ""),
            destination=destination,
            task_type=task_type,
        )
        return {"ok": True, "result": result.to_dict()}

    @router.get("/security/context-firewall/audit")
    async def list_context_firewall_audit(
        limit: int = 100,
        x_pm_user: str | None = Header(default=None, alias="X-PM-User"),
    ) -> dict[str, object]:
        _require(container, x_pm_user, "admin:users")
        records = container.context_firewall.list(limit=limit)
        return {"records": records, "count": len(records)}

    @router.get("/security/context-firewall/policy")
    async def read_context_firewall_policy(
        x_pm_user: str | None = Header(default=None, alias="X-PM-User"),
    ) -> dict[str, object]:
        _require(container, x_pm_user, "admin:users")
        return {"policy": default_policy_payload(container.settings.workspace_dir)}

    @router.put("/security/context-firewall/policy")
    async def save_context_firewall_policy(
        payload: dict[str, Any],
        x_pm_user: str | None = Header(default=None, alias="X-PM-User"),
    ) -> dict[str, object]:
        actor = _require(container, x_pm_user, "admin:users")
        policy_path = container.settings.workspace_dir / ".patchnote-security.yml"
        body = {"context_firewall": payload.get("context_firewall") or payload}
        with portalocker.Lock(policy_path, "w", encoding="utf-8", timeout=5) as fh:
            fh.write(yaml.safe_dump(body, sort_keys=False, allow_unicode=True))
        _audit(
            container,
            actor=actor,
            action="context_firewall.policy_updated",
            target="security_policy",
            target_id=".patchnote-security.yml",
        )
        return {"ok": True, "policy": default_policy_payload(container.settings.workspace_dir)}

    @router.post("/mcp-hub/prompts/{prompt_name}")
    async def render_mcp_hub_prompt(
        prompt_name: str,
        payload: McpToolCallPayload,
        x_pm_user: str | None = Header(default=None, alias="X-PM-User"),
    ) -> dict[str, object]:
        _require(container, x_pm_user, "work:read")
        try:
            prompt = render_mcp_prompt(prompt_name, payload.arguments, container)
        except ValueError as exc:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
        return {"ok": True, "prompt": prompt}

    @router.post("/mcp")
    async def call_mcp_json_rpc(
        payload: dict[str, Any],
        x_pm_user: str | None = Header(default=None, alias="X-PM-User"),
    ) -> dict[str, object]:
        method = str(payload.get("method") or "")
        raw_params = payload.get("params")
        params: dict[str, Any] = raw_params if isinstance(raw_params, dict) else {}
        if method == "tools/call":
            tool_name = str(params.get("name") or "")
            actor = _require(container, x_pm_user, required_permission(tool_name))
            raw_arguments = params.get("arguments")
            arguments: dict[str, Any] = raw_arguments if isinstance(raw_arguments, dict) else {}
            try:
                call_result = call_tool(container, tool_name, arguments)
            except ValueError as exc:
                return {
                    "jsonrpc": "2.0",
                    "id": payload.get("id"),
                    "error": {"code": -32602, "message": str(exc)},
                }
            record_mcp_audit(
                container,
                actor=actor,
                tool_name=tool_name,
                arguments=arguments,
                result_summary=call_result.result_summary,
                risk_level=call_result.risk_level,
                policy=call_result.policy,
                guard_findings=call_result.guard_findings,
            )
            return {
                "jsonrpc": "2.0",
                "id": payload.get("id"),
                "result": {
                    "content": [{"type": "json", "json": call_result.result}],
                    "isError": False,
                },
            }
        _require(container, x_pm_user, "work:read")
        return handle_json_rpc(container, payload)

    @router.get("/mcp/sse")
    async def mcp_sse(
        x_pm_user: str | None = Header(default=None, alias="X-PM-User"),
    ) -> StreamingResponse:
        _require(container, x_pm_user, "work:read")

        async def events() -> AsyncIterator[str]:
            yield 'event: metadata\ndata: {"name":"patchnote-mcp-hub","transport":"sse-skeleton"}\n\n'
            yield 'event: heartbeat\ndata: {"ok":true}\n\n'

        return StreamingResponse(events(), media_type="text/event-stream")

    @router.get("/llm/providers")
    async def list_llm_providers() -> dict[str, object]:
        return {"providers": provider_payload(vllm_base_url=container.settings.llm.vllm_base_url)}

    @router.get("/llm/providers/{provider}/models")
    async def list_provider_models(provider: str) -> ProviderModelPayload:
        try:
            metadata = require_provider(provider)
            saved = container.secret_store.read(provider)
            api_key = saved.api_key if saved else _settings_api_key(container, provider)
            base_url = default_base_url(
                provider, vllm_base_url=container.settings.llm.vllm_base_url
            )
            if provider == "vllm":
                base_url = (saved.base_url if saved and saved.base_url else base_url).rstrip("/")
            payload = await list_models(provider, api_key=api_key, base_url=base_url)
        except ValueError as exc:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
        raw_models = payload.get("models")
        models = cast(list[object], raw_models) if isinstance(raw_models, list) else []
        return ProviderModelPayload(
            provider=str(payload.get("provider") or metadata.id),
            models=[str(model) for model in models],
            source=str(payload.get("source") or "fallback"),
            refreshed_at=str(payload.get("refreshed_at") or ""),
            reason=str(payload.get("reason") or ""),
            configured=bool(payload.get("configured", False)),
            requires_api_key=bool(payload.get("requires_api_key", True)),
        )

    @router.post("/llm/providers/{provider}/models/preview")
    async def preview_provider_models(
        provider: str,
        payload: ProviderModelPreviewPayload,
    ) -> ProviderModelPayload:
        try:
            metadata = require_provider(provider)
            base_url = payload.base_url.strip() or default_base_url(
                provider,
                vllm_base_url=container.settings.llm.vllm_base_url,
            )
            result = await list_models(provider, api_key=payload.api_key.strip(), base_url=base_url)
        except ValueError as exc:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
        raw_models = result.get("models")
        models = cast(list[object], raw_models) if isinstance(raw_models, list) else []
        return ProviderModelPayload(
            provider=str(result.get("provider") or metadata.id),
            models=[str(model) for model in models],
            source=str(result.get("source") or "fallback"),
            refreshed_at=str(result.get("refreshed_at") or ""),
            reason=str(result.get("reason") or ""),
            configured=bool(result.get("configured", False)),
            requires_api_key=bool(result.get("requires_api_key", True)),
        )

    @router.post("/llm/local/huggingface/search")
    async def search_local_huggingface_models(
        payload: HuggingFaceModelSearchPayload,
        x_pm_user: str | None = Header(default=None, alias="X-PM-User"),
    ) -> HuggingFaceModelSearchResultPayload:
        _require(container, x_pm_user, "admin:api_keys")
        try:
            results = await search_huggingface_models(
                payload.query,
                limit=max(1, min(payload.limit, 50)),
            )
        except httpx.HTTPError as exc:
            raise HTTPException(
                status.HTTP_502_BAD_GATEWAY,
                detail=f"Hugging Face model search failed: {exc}",
            ) from exc
        return HuggingFaceModelSearchResultPayload(
            query=payload.query,
            models=[HuggingFaceModelItemPayload(**item) for item in results],
        )

    @router.get("/operations-memory")
    async def read_operations_memory() -> OperationsMemoryPayload:
        memory = container.operations_memory.read()
        return OperationsMemoryPayload(**memory.to_dict())

    @router.put("/operations-memory")
    async def write_operations_memory(
        payload: OperationsMemoryPayload,
        x_pm_user: str | None = Header(default=None, alias="X-PM-User"),
    ) -> OperationsMemoryPayload:
        actor = _require(container, x_pm_user, "memory:write")
        memory = payload.to_memory()
        container.operations_memory.write(memory)
        _audit(
            container, actor=actor, action="operations_memory.update", target="operations_memory"
        )
        return OperationsMemoryPayload(**memory.to_dict())

    @router.get("/work-memory")
    async def read_work_memory(
        x_pm_user: str | None = Header(default=None, alias="X-PM-User"),
    ) -> WorkMemoryPayload:
        _require(container, x_pm_user, "work:read")
        return WorkMemoryPayload.from_memory(container.work_memory.read())

    @router.put("/work-memory")
    async def write_work_memory(
        payload: WorkMemoryPayload,
        x_pm_user: str | None = Header(default=None, alias="X-PM-User"),
    ) -> WorkMemoryPayload:
        actor = _require(container, x_pm_user, "memory:write")
        memory = container.work_memory.write(payload.to_memory())
        _audit(container, actor=actor, action="work_memory.update", target="work_memory")
        return WorkMemoryPayload.from_memory(memory)

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
    async def write_llm_runtime(
        payload: LlmRuntimePayload,
        x_pm_user: str | None = Header(default=None, alias="X-PM-User"),
    ) -> LlmRuntimePayload:
        actor = _require(container, x_pm_user, "admin:local_llm")
        config = payload.to_config()
        container.llm_runtime.write(config)
        _sync_local_llm_state(container, enabled=config.local_enabled)
        _audit(
            container,
            actor=actor,
            action="llm_runtime.update",
            target="llm_runtime",
            details=config.to_dict(),
        )
        return LlmRuntimePayload.from_config(config, container)

    @router.get("/llm/local-status")
    async def read_local_llm_status() -> LocalLlmStatusPayload:
        return _local_llm_status(container)

    @router.post("/llm/local/start")
    async def start_local_llm(
        x_pm_user: str | None = Header(default=None, alias="X-PM-User"),
    ) -> LocalLlmStatusPayload:
        actor = _require(container, x_pm_user, "admin:local_llm")
        if container.embedded_vllm() is None:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                detail=(
                    "현재 백엔드는 vLLM 임베드 모드가 아닙니다. Docker 백엔드는 로컬 GPU 모델을 "
                    "직접 올릴 수 없으니 호스트에서 PM_VLLM_MODE=embedded 로 patch-machine serve를 "
                    "실행하세요."
                ),
            )
        runtime = container.llm_runtime.read()
        if not runtime.local_enabled:
            container.llm_runtime.write(
                LlmRuntimeConfig(
                    local_enabled=True,
                    api_enabled=runtime.api_enabled,
                    default_route=runtime.default_route,
                    default_provider=runtime.default_provider,
                    local_model=runtime.local_model,
                    task_routes=runtime.task_routes,
                )
            )
        _sync_local_llm_state(container, enabled=True)
        _audit(container, actor=actor, action="llm_local.start", target="llm_runtime")
        return _local_llm_status(container)

    @router.post("/llm/local/stop")
    async def stop_local_llm(
        x_pm_user: str | None = Header(default=None, alias="X-PM-User"),
    ) -> LocalLlmStatusPayload:
        actor = _require(container, x_pm_user, "admin:local_llm")
        runtime = container.llm_runtime.read()
        container.llm_runtime.write(
            LlmRuntimeConfig(
                local_enabled=False,
                api_enabled=runtime.api_enabled,
                default_route=runtime.default_route,
                default_provider=runtime.default_provider,
                local_model=runtime.local_model,
                task_routes=runtime.task_routes,
            )
        )
        _sync_local_llm_state(container, enabled=False)
        _audit(container, actor=actor, action="llm_local.stop", target="llm_runtime")
        return _local_llm_status(container)

    @router.post("/llm/chat")
    async def chat(
        payload: ChatRequest,
        x_pm_user: str | None = Header(default=None, alias="X-PM-User"),
    ) -> ChatResponse:
        actor = _require(container, x_pm_user, "llm:chat")
        runtime = container.llm_runtime.read()
        task_route = runtime.route_for(payload.task or "chat")
        route = payload.route or task_route.route
        provider = payload.provider or task_route.provider
        if route == "local" and not runtime.local_enabled:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="local LLM route is disabled")
        if route == "local":
            _sync_local_llm_state(container, enabled=True)
        if route == "api" and not runtime.api_enabled:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="API LLM route is disabled")
        llm_route: LlmRoute = "local" if route == "local" else "cloud"
        messages = _build_chat_messages(container, payload.message, user_id=actor)
        job = _start_ai_job(
            container,
            task=payload.task or "chat",
            actor=actor,
            input_summary=payload.message,
        )
        try:
            response = await _complete_with_provider(
                container,
                messages,
                provider=provider,
                route=llm_route,
                temperature=0.2,
                max_tokens=1024,
                task=payload.task or "chat",
                actor=actor,
            )
            job = _finish_ai_job(container, job, status="succeeded")
        except Exception as exc:
            _finish_ai_job(container, job, status="failed", error=str(exc))
            raise
        container.metrics.record(
            agent="chat",
            route=response.route,
            tokens_in=response.prompt_tokens,
            tokens_out=response.completion_tokens,
            latency_ms=0,
        )
        container.conversations.append_pair(
            user_id=actor,
            user_message=payload.message,
            assistant_message=response.text,
            provider=provider,
            model=response.model,
            route=route,
            source_refs=[],
        )
        _update_user_volatile_memory_after_chat(
            container, actor=actor, user_message=payload.message, answer=response.text
        )
        return ChatResponse(
            answer=response.text,
            route=route,
            provider=provider,
            model=response.model,
            prompt_tokens=response.prompt_tokens,
            completion_tokens=response.completion_tokens,
            ai_job=_ai_job_payload(job).model_dump(),
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

    @router.post("/work-architecture/generate")
    async def generate_work_architecture(
        payload: WorkArchitectureRequest,
        x_pm_user: str | None = Header(default=None, alias="X-PM-User"),
    ) -> WorkArchitecturePayload:
        actor = _require(container, x_pm_user, "memory:write")
        context = _office_context(container) if payload.use_memory else ""
        prompt = render_prompt(
            "office/work_architecture.md.j2",
            context=context,
            objective=payload.objective,
            scope=payload.scope,
            horizon=payload.horizon,
            participants=payload.participants,
            constraints=payload.constraints,
        ).strip()
        job = _start_ai_job(
            container,
            task="work_architecture",
            actor=actor,
            input_summary=payload.objective,
        )
        try:
            markdown = await _complete_office_task(container, prompt, task="document_generation")
            path = _write_generated_doc(
                container.settings.archive_dir,
                folder="work_architecture",
                slug=payload.objective or "work_architecture",
                markdown=markdown,
            )
            job = _finish_ai_job(container, job, status="succeeded", result_path=path)
        except Exception as exc:
            _finish_ai_job(container, job, status="failed", error=str(exc))
            raise
        architecture = {
            "objective": payload.objective,
            "scope": payload.scope,
            "horizon": payload.horizon,
            "participants": payload.participants,
            "constraints": payload.constraints,
            "path": path,
        }
        work_memory = container.work_memory.read()
        container.work_memory.write(
            WorkMemory(
                goals=work_memory.goals or payload.objective,
                active_projects=payload.scope or work_memory.active_projects,
                current_focus=payload.objective,
                blockers=work_memory.blockers,
                decisions=work_memory.decisions,
                risks=payload.constraints or work_memory.risks,
                next_actions=f"업무 아키텍처 검토: {path}",
            )
        )
        _audit(
            container,
            actor=actor,
            action="work_architecture.generate",
            target="work_architecture",
            target_id=path,
        )
        return WorkArchitecturePayload(
            title=payload.objective,
            markdown=markdown,
            path=path,
            architecture=architecture,
            ai_job=_ai_job_payload(job).model_dump(),
        )

    @router.get("/work-schedule")
    async def list_work_schedule(
        x_pm_user: str | None = Header(default=None, alias="X-PM-User"),
    ) -> dict[str, object]:
        _require(container, x_pm_user, "work:read")
        return {"items": container.work_schedule.list()}

    @router.post("/work-schedule/items")
    async def create_work_schedule_item(
        payload: WorkScheduleItemPayload,
        x_pm_user: str | None = Header(default=None, alias="X-PM-User"),
    ) -> dict[str, object]:
        actor = _require(container, x_pm_user, "memory:write")
        item = container.work_schedule.upsert(payload.to_record())
        _audit(
            container,
            actor=actor,
            action="work_schedule.upsert",
            target="work_schedule",
            target_id=item.id,
        )
        return {"ok": True, "item": item.to_dict(), "items": container.work_schedule.list()}

    @router.put("/work-schedule/items/{item_id}")
    async def update_work_schedule_item(
        item_id: str,
        payload: WorkScheduleItemPayload,
        x_pm_user: str | None = Header(default=None, alias="X-PM-User"),
    ) -> dict[str, object]:
        actor = _require(container, x_pm_user, "memory:write")
        item = container.work_schedule.upsert(payload.to_record(item_id=item_id))
        _audit(
            container,
            actor=actor,
            action="work_schedule.upsert",
            target="work_schedule",
            target_id=item.id,
        )
        return {"ok": True, "item": item.to_dict(), "items": container.work_schedule.list()}

    @router.delete("/work-schedule/items/{item_id}")
    async def delete_work_schedule_item(
        item_id: str,
        x_pm_user: str | None = Header(default=None, alias="X-PM-User"),
    ) -> dict[str, object]:
        actor = _require(container, x_pm_user, "memory:write")
        ok = container.work_schedule.delete(item_id)
        _audit(
            container,
            actor=actor,
            action="work_schedule.delete",
            target="work_schedule",
            target_id=item_id,
        )
        return {"ok": ok, "items": container.work_schedule.list()}

    @router.post("/work-schedule/generate")
    async def generate_work_schedule(
        payload: WorkScheduleGenerationRequest,
        x_pm_user: str | None = Header(default=None, alias="X-PM-User"),
    ) -> GeneratedDocumentPayload:
        actor = _require(container, x_pm_user, "memory:write")
        prompt = render_prompt(
            "office/work_schedule.md.j2",
            context=_office_context(container),
            objective=payload.objective,
            participants=payload.participants,
            horizon=payload.horizon,
            constraints=payload.constraints,
        ).strip()
        job = _start_ai_job(
            container,
            task="work_schedule.generate",
            actor=actor,
            input_summary=payload.objective,
        )
        try:
            markdown = await _complete_office_task(container, prompt, task="document_generation")
            path = _write_generated_doc(
                container.settings.archive_dir,
                folder="work_architecture",
                slug=f"schedule_{payload.objective}",
                markdown=markdown,
            )
            job = _finish_ai_job(container, job, status="succeeded", result_path=path)
        except Exception as exc:
            _finish_ai_job(container, job, status="failed", error=str(exc))
            raise
        item = container.work_schedule.upsert(
            WorkScheduleItem.create(
                title=f"AI 생성 스케줄 검토: {payload.objective}",
                owner_name=payload.participants,
                priority="high",
                notes=f"생성 문서: {path}",
                source_architecture_id=path,
            )
        )
        _audit(
            container,
            actor=actor,
            action="work_schedule.generate",
            target="work_schedule",
            target_id=item.id,
        )
        return GeneratedDocumentPayload(
            title=payload.objective,
            markdown=markdown,
            path=path,
            ai_job=_ai_job_payload(job).model_dump(),
        )

    @router.get("/integrations/github")
    async def read_github_status() -> IntegrationStatusPayload:
        return await _fetch_github_status(container)

    @router.get("/integrations/discord")
    async def read_discord_status() -> IntegrationStatusPayload:
        return await _fetch_discord_status(container)

    @router.get("/integrations/config")
    async def read_integration_config(
        x_pm_user: str | None = Header(default=None, alias="X-PM-User"),
    ) -> IntegrationConfigPayload:
        _require(container, x_pm_user, "admin:integrations")
        return _integration_config_payload(container)

    @router.put("/integrations/github")
    async def upsert_github_connector(
        payload: GitHubConnectorPayload,
        x_pm_user: str | None = Header(default=None, alias="X-PM-User"),
    ) -> IntegrationConfigPayload:
        actor = _require(container, x_pm_user, "admin:integrations")
        _save_github_secrets(container, payload)
        config = container.integration_config.update_github(
            GitHubConnectorConfig(
                enabled=payload.enabled,
                allowed_repos=[
                    repo.strip()
                    for repo in payload.allowed_repos
                    if repo.strip()
                ],
                trigger_label=payload.trigger_label.strip() or "patch-machine",
                webhook_secret_present=container.secret_store.has_secret("github_webhook"),
                app_token_present=container.secret_store.has_secret("github_app"),
                event_forms=[
                    item.strip()
                    for item in payload.event_forms
                    if item.strip()
                ]
                or ["issue", "pull_request", "repository", "push"],
            )
        )
        _audit(
            container,
            actor=actor,
            action="integration.github.update",
            target="integration",
            target_id="github",
        )
        return _integration_config_payload(container, config=config)

    @router.put("/integrations/discord")
    async def upsert_discord_connector(
        payload: DiscordConnectorPayload,
        x_pm_user: str | None = Header(default=None, alias="X-PM-User"),
    ) -> IntegrationConfigPayload:
        actor = _require(container, x_pm_user, "admin:integrations")
        _save_discord_secrets(container, payload)
        bindings: list[DiscordChannelBindingConfig] = []
        for binding in payload.channel_bindings:
            channel_id = binding.channel_id.strip()
            if not channel_id:
                continue
            bindings.append(
                DiscordChannelBindingConfig(
                    guild_id=binding.guild_id.strip(),
                    channel_id=channel_id,
                    channel_name=binding.channel_name.strip(),
                    repo=binding.repo.strip(),
                )
            )
        config = container.integration_config.update_discord(
            DiscordConnectorConfig(
                enabled=payload.enabled,
                bot_token_present=container.secret_store.has_secret("discord_bot"),
                guild_allowlist=[
                    item.strip()
                    for item in payload.guild_allowlist
                    if item.strip()
                ],
                channel_bindings=bindings,
                command_forms=[
                    item.strip()
                    for item in payload.command_forms
                    if item.strip()
                ]
                or ["bug_report", "thread_digest", "slash_command"],
            )
        )
        _audit(
            container,
            actor=actor,
            action="integration.discord.update",
            target="integration",
            target_id="discord",
        )
        return _integration_config_payload(container, config=config)

    @router.get("/archive/documents")
    async def read_archive_document(
        path: str,
        x_pm_user: str | None = Header(default=None, alias="X-PM-User"),
    ) -> DocumentReadPayload:
        _require(container, x_pm_user, "documents:read")
        try:
            return _read_archive_document(container, path)
        except FileNotFoundError as exc:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    @router.get("/llm/token-limits")
    async def read_token_limits(
        x_pm_user: str | None = Header(default=None, alias="X-PM-User"),
    ) -> TokenLimitStatusPayload:
        _require(container, x_pm_user, "admin:token_limits")
        return _token_limit_status(container)

    @router.put("/llm/token-limits")
    async def update_token_limits(
        payload: TokenLimitPayload,
        x_pm_user: str | None = Header(default=None, alias="X-PM-User"),
    ) -> TokenLimitStatusPayload:
        actor = _require(container, x_pm_user, "admin:token_limits")
        container.token_usage.write_limits(
            TokenLimitConfig(
                enforcement_enabled=payload.enforcement_enabled,
                per_request_max_tokens=max(0, int(payload.per_request_max_tokens or 0)),
                daily_total_tokens=max(0, int(payload.daily_total_tokens or 0)),
                monthly_total_tokens=max(0, int(payload.monthly_total_tokens or 0)),
            )
        )
        _audit(
            container,
            actor=actor,
            action="llm.token_limits.update",
            target="token_limits",
            details=payload.model_dump(),
        )
        return _token_limit_status(container)

    @router.get("/patch-records")
    async def list_patch_records(
        x_pm_user: str | None = Header(default=None, alias="X-PM-User"),
    ) -> dict[str, list[PatchRecordPayload]]:
        _require(container, x_pm_user, "patch_records:read")
        return {
            "items": [_patch_record_payload(record) for record in container.patch_records.list()],
        }

    @router.get("/patch-records/{record_id}")
    async def read_patch_record(
        record_id: str,
        x_pm_user: str | None = Header(default=None, alias="X-PM-User"),
    ) -> PatchRecordDetailPayload:
        _require(container, x_pm_user, "patch_records:read")
        record = container.patch_records.get(record_id)
        if record is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail="패치 기록을 찾을 수 없습니다.")
        markdown = container.patch_records.read_markdown(record_id) or ""
        return _patch_record_detail_payload(record, markdown)

    @router.post("/patch-records")
    async def create_patch_record(
        payload: PatchRecordCreatePayload,
        x_pm_user: str | None = Header(default=None, alias="X-PM-User"),
    ) -> PatchRecordDetailPayload:
        actor = _require(container, x_pm_user, "patch_records:write")
        if not payload.title.strip():
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                detail="title 은 필수입니다.",
            )
        record = container.patch_records.append(
            title=payload.title,
            summary=payload.summary,
            request=payload.request,
            plan=payload.plan,
            changed_files=payload.changed_files,
            verification=payload.verification,
            follow_ups=payload.follow_ups,
            tags=payload.tags,
            actor=actor,
            agent=payload.agent,
        )
        markdown = container.patch_records.read_markdown(record.record_id) or ""
        _audit(
            container,
            actor=actor,
            action="patch_record.create",
            target="patch_record",
            target_id=record.record_id,
        )
        return _patch_record_detail_payload(record, markdown)

    @router.post("/hr/role-requirements")
    async def create_role_requirements(
        payload: HiringRequest,
        x_pm_user: str | None = Header(default=None, alias="X-PM-User"),
    ) -> GeneratedDocumentPayload:
        actor = _require(container, x_pm_user, "documents:write")
        result = await _generate_hiring_document(
            container,
            payload,
            actor=actor,
            kind="role_requirements",
            instruction="필요 역량, 경험, 성향, 필수/우대 조건을 정리하세요.",
        )
        _audit(
            container,
            actor=actor,
            action="document.create",
            target="document",
            target_id=result.path,
        )
        return result

    @router.post("/hr/interview-kit")
    async def create_interview_kit(
        payload: HiringRequest,
        x_pm_user: str | None = Header(default=None, alias="X-PM-User"),
    ) -> GeneratedDocumentPayload:
        actor = _require(container, x_pm_user, "documents:write")
        result = await _generate_hiring_document(
            container,
            payload,
            actor=actor,
            kind="interview_kit",
            instruction="면접 질문, 좋은 답변 기준, 평가 루브릭을 작성하세요.",
        )
        _audit(
            container,
            actor=actor,
            action="document.create",
            target="document",
            target_id=result.path,
        )
        return result

    @router.post("/hr/onboarding-plan")
    async def create_onboarding_plan(
        payload: HiringRequest,
        x_pm_user: str | None = Header(default=None, alias="X-PM-User"),
    ) -> GeneratedDocumentPayload:
        actor = _require(container, x_pm_user, "documents:write")
        result = await _generate_hiring_document(
            container,
            payload,
            actor=actor,
            kind="onboarding_plan",
            instruction="입사 후 1주/1개월/3개월 온보딩 계획과 산출물을 작성하세요.",
        )
        _audit(
            container,
            actor=actor,
            action="document.create",
            target="document",
            target_id=result.path,
        )
        return result

    @router.post("/handover/brief")
    async def create_handover_brief(
        payload: HandoverRequest,
        x_pm_user: str | None = Header(default=None, alias="X-PM-User"),
    ) -> GeneratedDocumentPayload:
        actor = _require(container, x_pm_user, "documents:write")
        context = _office_context(container)
        prompt = render_prompt(
            "office/handover.md.j2",
            context=context,
            work_title=payload.work_title,
            outgoing_owner=payload.outgoing_owner,
            incoming_owner=payload.incoming_owner,
            notes=payload.notes,
        ).strip()
        job = _start_ai_job(
            container,
            task="handover",
            actor=actor,
            input_summary=payload.work_title or payload.notes,
        )
        try:
            markdown = await _complete_office_task(container, prompt, task="handover")
            path = _write_generated_doc(
                container.settings.archive_dir,
                folder="handover",
                slug=payload.work_title or "handover",
                markdown=markdown,
            )
            job = _finish_ai_job(container, job, status="succeeded", result_path=path)
        except Exception as exc:
            _finish_ai_job(container, job, status="failed", error=str(exc))
            raise
        result = GeneratedDocumentPayload(title=payload.work_title, markdown=markdown, path=path, ai_job=_ai_job_payload(job).model_dump())
        _audit(container, actor=actor, action="document.create", target="document", target_id=path)
        return result

    @router.post("/documents/generate")
    async def create_office_document(
        payload: OfficeDocumentRequest,
        x_pm_user: str | None = Header(default=None, alias="X-PM-User"),
    ) -> GeneratedDocumentPayload:
        actor = _require(container, x_pm_user, "documents:write")
        labels = {
            "meeting_minutes": "회의록",
            "report_draft": "보고서 초안",
            "work_request": "업무 요청서",
            "ppt_outline": "PPT 초안",
        }
        prompt = render_prompt(
            "office/document_generation.md.j2",
            context=_office_context(container),
            document_label=labels[payload.document_type],
            title=payload.title,
            audience=payload.audience,
            source_text=payload.source_text,
        ).strip()
        job = _start_ai_job(
            container,
            task="document_generation",
            actor=actor,
            input_summary=f"{payload.document_type}: {payload.title}",
        )
        try:
            markdown = await _complete_office_task(container, prompt, task="document_generation")
            path = _write_generated_doc(
                container.settings.archive_dir,
                folder="documents",
                slug=f"{payload.document_type}_{payload.title}",
                markdown=markdown,
            )
            job = _finish_ai_job(container, job, status="succeeded", result_path=path)
        except Exception as exc:
            _finish_ai_job(container, job, status="failed", error=str(exc))
            raise
        result = GeneratedDocumentPayload(title=payload.title, markdown=markdown, path=path, ai_job=_ai_job_payload(job).model_dump())
        _audit(container, actor=actor, action="document.create", target="document", target_id=path)
        return result

    @router.get("/admin/api-keys")
    async def list_api_keys(
        x_pm_user: str | None = Header(default=None, alias="X-PM-User"),
    ) -> dict[str, object]:
        _require(container, x_pm_user, "admin:api_keys")
        try:
            providers = _masked_provider_payload(container)
        except ValueError as exc:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
        return {"providers": providers}

    @router.put("/admin/api-keys/{provider}")
    async def save_api_key(
        provider: str,
        payload: ApiKeyPayload,
        x_pm_user: str | None = Header(default=None, alias="X-PM-User"),
    ) -> dict[str, object]:
        actor = _require(container, x_pm_user, "admin:api_keys")
        try:
            require_provider(provider)
            container.secret_store.upsert(
                ApiKeyRecord(
                    provider=provider,
                    api_key=payload.api_key.strip(),
                    model=payload.model.strip(),
                    base_url=default_base_url(
                        provider,
                        vllm_base_url=container.settings.llm.vllm_base_url,
                    ),
                )
            )
            _audit(
                container,
                actor=actor,
                action="api_key.upsert",
                target="api_key",
                target_id=provider,
                details={
                    "model": payload.model.strip(),
                    "configured": bool(payload.api_key.strip()),
                },
            )
            return {"ok": True, "providers": _masked_provider_payload(container)}
        except ValueError as exc:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    @router.delete("/admin/api-keys/{provider}")
    async def delete_api_key(
        provider: str,
        x_pm_user: str | None = Header(default=None, alias="X-PM-User"),
    ) -> dict[str, object]:
        actor = _require(container, x_pm_user, "admin:api_keys")
        container.secret_store.delete(provider)
        _audit(
            container, actor=actor, action="api_key.delete", target="api_key", target_id=provider
        )
        return {"ok": True, "providers": _masked_provider_payload(container)}

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
        actor = _require(container, x_pm_user, "admin:users")
        container.access_control.upsert_role(payload.to_record())
        _audit(
            container,
            actor=actor,
            action="role.upsert",
            target="role",
            target_id=payload.id.strip(),
        )
        return container.access_control.read()

    @router.delete("/admin/roles/{role_id}")
    async def delete_role(
        role_id: str,
        x_pm_user: str | None = Header(default=None, alias="X-PM-User"),
    ) -> dict[str, Any]:
        actor = _require(container, x_pm_user, "admin:users")
        try:
            container.access_control.delete_role(role_id)
        except ValueError as exc:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
        _audit(container, actor=actor, action="role.delete", target="role", target_id=role_id)
        return container.access_control.read()

    @router.post("/admin/users")
    async def upsert_user(
        payload: UserPayload,
        x_pm_user: str | None = Header(default=None, alias="X-PM-User"),
    ) -> dict[str, Any]:
        actor = _require(container, x_pm_user, "admin:users")
        container.access_control.upsert_user(payload.to_record())
        _audit(
            container,
            actor=actor,
            action="user.upsert",
            target="user",
            target_id=payload.id.strip(),
        )
        return container.access_control.read()

    @router.delete("/admin/users/{user_id}")
    async def delete_user(
        user_id: str,
        x_pm_user: str | None = Header(default=None, alias="X-PM-User"),
    ) -> dict[str, Any]:
        actor = _require(container, x_pm_user, "admin:users")
        container.access_control.delete_user(user_id)
        _audit(container, actor=actor, action="user.delete", target="user", target_id=user_id)
        return container.access_control.read()

    @router.get("/admin/account-requests")
    async def list_account_requests(
        status_filter: RequestStatus | None = None,
        x_pm_user: str | None = Header(default=None, alias="X-PM-User"),
    ) -> dict[str, object]:
        _require(container, x_pm_user, "admin:users")
        return {
            "requests": [
                request.to_dict()
                for request in container.auth_store.list_requests(status=status_filter)
            ]
        }

    @router.get("/admin/audit-log")
    async def list_audit_log(
        limit: int = 100,
        x_pm_user: str | None = Header(default=None, alias="X-PM-User"),
    ) -> dict[str, object]:
        _require(container, x_pm_user, "admin:users")
        return {"records": container.audit_log.list_recent(limit=max(1, min(limit, 500)))}

    @router.post("/admin/account-requests/{request_id}/approve")
    async def approve_account_request(
        request_id: str,
        x_pm_user: str | None = Header(default=None, alias="X-PM-User"),
    ) -> dict[str, object]:
        admin_user = _require(container, x_pm_user, "admin:users")
        try:
            request = container.auth_store.decide_request(
                request_id,
                status="approved",
                decided_by=admin_user,
            )
            container.auth_store.create_user_with_hash(
                user_id=request.user_id,
                display_name=request.display_name,
                password_hash=request.password_hash,
            )
            container.access_control.upsert_user(
                UserRecord(
                    id=request.user_id,
                    display_name=request.display_name,
                    title=request.title,
                    role_id="viewer",
                    active=True,
                )
            )
        except ValueError as exc:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
        _audit(
            container,
            actor=admin_user,
            action="account_request.approve",
            target="account_request",
            target_id=request.id,
            details={"user_id": request.user_id},
        )
        return {"ok": True, "request": request.to_dict()}

    @router.post("/admin/account-requests/{request_id}/reject")
    async def reject_account_request(
        request_id: str,
        x_pm_user: str | None = Header(default=None, alias="X-PM-User"),
    ) -> dict[str, object]:
        admin_user = _require(container, x_pm_user, "admin:users")
        try:
            request = container.auth_store.decide_request(
                request_id,
                status="rejected",
                decided_by=admin_user,
            )
        except ValueError as exc:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
        _audit(
            container,
            actor=admin_user,
            action="account_request.reject",
            target="account_request",
            target_id=request.id,
            details={"user_id": request.user_id},
        )
        return {"ok": True, "request": request.to_dict()}

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
        actor = _require(container, x_pm_user, "uploads:write")
        record = container.uploads.save(
            filename=file.filename or "upload.bin",
            source=file.file,
            description=description,
            tags=tags,
            work_title=work_title,
        )
        _audit(
            container,
            actor=actor,
            action="upload.create",
            target="upload",
            target_id=record.id,
            details={"path": record.path},
        )
        return {"ok": True, "upload": record.to_dict()}

    @router.delete("/uploads/{upload_id}")
    async def delete_upload(
        upload_id: str,
        x_pm_user: str | None = Header(default=None, alias="X-PM-User"),
    ) -> dict[str, object]:
        actor = _require(container, x_pm_user, "uploads:write")
        ok = container.uploads.delete(upload_id)
        _audit(container, actor=actor, action="upload.delete", target="upload", target_id=upload_id)
        return {"ok": ok}

    return router


def _selected_upload_records(
    records: list[dict[str, str]], upload_ids: list[str]
) -> list[dict[str, str]]:
    if not upload_ids:
        return records[:5]
    wanted = {item.strip() for item in upload_ids if item.strip()}
    return [record for record in records if str(record.get("id") or "") in wanted]


def _initial_office_setup_prompt(
    *,
    message: str,
    intent: str,
    parsed_files: list[ParsedSetupFile],
    company_profile: CompanyProfilePayload | None = None,
) -> str:
    file_blocks = "\n\n".join(file.to_prompt_block() for file in parsed_files)
    profile = company_profile or CompanyProfilePayload()
    return render_prompt(
        "office/initial_office_setup.md.j2",
        intent=intent,
        message=message,
        file_blocks=file_blocks,
        company_profile=profile.model_dump(),
        market_positioning=render_prompt("catalogs/patchnote_market.md.j2").strip(),
    ).strip()


def _parse_initial_setup_result(
    raw: str,
    *,
    parsed_files: list[ParsedSetupFile],
    company_profile: CompanyProfilePayload | None = None,
) -> InitialOfficeSetupResult:
    profile = company_profile or CompanyProfilePayload()
    recommendation = recommend_patchnote_setup(
        profile,
        sensitive_hint=any(file.sensitive_hint for file in parsed_files),
    )
    operations_seed = recommendation.pop("operations_memory_seed", {}) or {}
    work_seed = recommendation.pop("work_memory_seed", {}) or {}
    data = _try_load_json_object(raw)
    if data is None:
        data = {
            "operations_memory": _fallback_operations_memory(parsed_files),
            "work_memory": {
                "goals": "초기 오피스 환경 세팅",
                "current_focus": "업로드 파일 검토와 조직/사용자 명세 정리",
                "next_actions": "AI 분석 결과를 검토한 뒤 적용하세요.",
            },
            "roles": [],
            "users": _fallback_users(parsed_files),
            "notes": ["LLM 응답을 JSON으로 파싱하지 못해 파일 기반 기본 초안을 만들었습니다."],
            "warnings": [],
            "questions": ["회사명, 부서 구조, 직함별 권한을 최종 확인하세요."],
        }
    for key, value in recommendation.items():
        data.setdefault(key, value)
    operations_memory = dict(data.get("operations_memory") or {})
    for key, value in operations_seed.items():
        if value and not str(operations_memory.get(key) or "").strip():
            operations_memory[key] = value
    data["operations_memory"] = operations_memory
    work_memory = dict(data.get("work_memory") or {})
    for key, value in work_seed.items():
        if value and not str(work_memory.get(key) or "").strip():
            work_memory[key] = value
    data["work_memory"] = work_memory
    data.setdefault("sensitive_hint", any(file.sensitive_hint for file in parsed_files))
    if data.get("sensitive_hint"):
        warnings = list(data.get("warnings") or [])
        warnings.append("민감정보가 포함될 수 있으므로 로컬 에이전트 서버 사용을 권장합니다.")
        data["warnings"] = list(dict.fromkeys(str(item) for item in warnings))
    return InitialOfficeSetupResult.model_validate(data)


def _initial_setup_memories_with_recommendations(
    payload: InitialOfficeSetupResult,
) -> tuple[dict[str, Any], dict[str, Any]]:
    operations_memory = dict(payload.operations_memory)
    work_memory = dict(payload.work_memory)
    has_recommendations = any(
        [
            payload.agent_packs,
            payload.templates,
            payload.workflows,
            payload.security_defaults,
            payload.integration_priorities,
            payload.first_14_days,
        ]
    )
    if not has_recommendations:
        return operations_memory, work_memory

    recommendation_md = render_recommendation_markdown(payload.model_dump())
    operations_memory.setdefault(
        "office_project",
        f"{payload.recommended_package or 'Patch Note Team'} 계정 맞춤 도입",
    )
    operations_memory.setdefault("active_plan", "계정 맞춤 Patch Note 조립안 검토 및 적용")
    operations_memory["key_workflows"] = _join_markdown_blocks(
        str(operations_memory.get("key_workflows") or ""),
        recommendation_md,
    )
    security_lines = [
        str(item.get("name") or item.get("id") or "")
        for item in payload.security_defaults
        if item.get("enabled", True)
    ]
    if security_lines:
        operations_memory["sensitive_policy"] = _join_markdown_blocks(
            str(operations_memory.get("sensitive_policy") or ""),
            "초기 보안 기본값:\n" + "\n".join(f"- {line}" for line in security_lines if line),
        )

    work_memory.setdefault("goals", "첫 30일 동안 Patch Note 기반 AI 업무 운영 레이어 정착")
    work_memory["active_projects"] = _join_markdown_blocks(
        str(work_memory.get("active_projects") or ""),
        _items_to_lines("에이전트 팩", payload.agent_packs),
        _items_to_lines("템플릿", payload.templates),
    )
    work_memory["next_actions"] = _join_markdown_blocks(
        str(work_memory.get("next_actions") or ""),
        "\n".join(f"- {item}" for item in payload.first_14_days),
    )
    if payload.human_review_required:
        work_memory["risks"] = _join_markdown_blocks(
            str(work_memory.get("risks") or ""),
            "사람 검토 필수 업무:\n"
            + "\n".join(f"- {item}" for item in payload.human_review_required),
        )
    return operations_memory, work_memory


def _apply_initial_setup_llm_routes(
    container: Container,
    routes: dict[str, dict[str, str]],
) -> None:
    runtime = container.llm_runtime.read()
    merged = dict(runtime.task_routes or {})
    for task, route in routes.items():
        if isinstance(route, dict):
            merged[str(task)] = LlmTaskRoute.from_mapping(route, fallback=runtime)
    container.llm_runtime.write(
        LlmRuntimeConfig(
            local_enabled=runtime.local_enabled,
            api_enabled=runtime.api_enabled,
            default_route=runtime.default_route,
            default_provider=runtime.default_provider,
            local_model=runtime.local_model,
            task_routes=merged or None,
        )
    )


def _join_markdown_blocks(*blocks: str) -> str:
    return "\n\n".join(block.strip() for block in blocks if block.strip())


def _items_to_lines(title: str, items: list[dict[str, Any]]) -> str:
    if not items:
        return ""
    lines = [f"{title}:"]
    for item in items:
        name = item.get("name") or item.get("id")
        description = item.get("description") or item.get("reason") or item.get("priority") or ""
        lines.append(f"- {name}: {description}".rstrip(": "))
    return "\n".join(lines)


def _try_load_json_object(raw: str) -> dict[str, Any] | None:
    text = raw.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        text = text[start : end + 1]
    try:
        loaded = json.loads(text)
    except json.JSONDecodeError:
        return None
    return loaded if isinstance(loaded, dict) else None


def _fallback_operations_memory(parsed_files: list[ParsedSetupFile]) -> dict[str, str]:
    departments: list[str] = []
    roles: list[str] = []
    for file in parsed_files:
        for row in file.rows[:50]:
            departments.extend(
                value for key, value in row.items() if "부서" in key or "department" in key.lower()
            )
            roles.extend(
                value for key, value in row.items() if "직함" in key or "title" in key.lower()
            )
    return {
        "company_name": "",
        "organization": "\n".join(file.filename for file in parsed_files),
        "departments": ", ".join(sorted({item for item in departments if item})),
        "roles": ", ".join(sorted({item for item in roles if item})),
        "key_workflows": "초기 업로드 파일을 기반으로 업무 흐름을 정리하세요.",
        "sensitive_policy": "민감한 파일은 로컬 에이전트 서버에서 처리하는 것을 권장합니다.",
    }


def _fallback_users(parsed_files: list[ParsedSetupFile]) -> list[dict[str, object]]:
    users: list[dict[str, object]] = []
    for file in parsed_files:
        for row in file.rows[:100]:
            name = _first_value(row, ("이름", "성명", "name", "employee"))
            title = _first_value(row, ("직함", "직급", "title", "role"))
            if not name:
                continue
            user_id = _safe_user_id(_first_value(row, ("id", "email", "이메일")) or name)
            users.append(
                {
                    "id": user_id,
                    "display_name": name,
                    "title": title,
                    "role_id": _role_for_title(title),
                    "active": True,
                },
            )
    return users


def _first_value(row: dict[str, str], keys: tuple[str, ...]) -> str:
    for key, value in row.items():
        low = key.lower()
        if any(target.lower() in low for target in keys):
            return value.strip()
    return ""


def _safe_user_id(value: str) -> str:
    cleaned = "".join(ch.lower() if ch.isalnum() else "_" for ch in value.strip())
    return cleaned.strip("_")[:64] or "user"


def _role_for_title(title: str) -> str:
    if any(token in title for token in ("대표", "관리자", "CEO", "ceo")):
        return "owner"
    if any(token in title for token in ("팀장", "매니저", "manager", "Manager")):
        return "manager"
    return "staff"


def _build_chat_messages(
    container: Container, user_message: str, *, user_id: str = "default"
) -> list[LlmMessage]:
    memory = container.operations_memory.read().to_markdown()
    work_memory = container.work_memory.read().to_markdown()
    volatile_user = container.volatile_memory.read(scope="user", key=user_id).to_markdown()
    volatile_global = container.volatile_memory.read(scope="global", key="default").to_markdown()
    compressed = container.compressed_context.read(scope="user", key=user_id).to_markdown()
    permanent = container.permanent_memory.search(user_message, limit=5)
    permanent_md = "\n".join(
        f"- [{source.get('kind')}] {source.get('path')}: {source.get('title')}"
        for source in permanent
    )
    status_md = container.archive.status.read()
    recent = _recent_logs(container.settings.archive_dir, limit=5)
    recent_md = "\n".join(
        f"- {entry.get('created', '')} {entry.get('repo', '')} #{entry.get('external_id', '')} "
        f"status={entry.get('status', '')}"
        for entry in recent
    )
    system = render_prompt("office/chat_system.md.j2").strip()
    context = render_prompt(
        "office/chat_context.md.j2",
        memory=memory,
        work_memory=work_memory,
        permanent_md=permanent_md,
        compressed=compressed,
        volatile_user=volatile_user,
        volatile_global=volatile_global,
        status_md=status_md,
        recent_md=recent_md,
    ).strip()
    return [
        LlmMessage("system", system),
        LlmMessage("user", f"{context}\n\n질문:\n{user_message.strip()}"),
    ]


def _require(container: Container, credential: str | None, permission: str) -> str:
    user_id = _resolve_authenticated_user(container, credential)
    if user_id is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="login required")
    if not container.access_control.has_permission(user_id, permission):
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            detail=f"permission required: {permission}",
        )
    return user_id


def _resolve_authenticated_user(container: Container, credential: str | None) -> str | None:
    token = _extract_token(credential)
    if token:
        return container.auth_store.resolve_token(token)
    return None


def _extract_token(credential: str | None) -> str:
    if not credential:
        return ""
    value = credential.strip()
    if value.lower().startswith("bearer "):
        return value[7:].strip()
    return value


def _user_payload(container: Container, user_id: str) -> dict[str, object]:
    acl = container.access_control.read()
    user = next((entry for entry in acl["users"] if entry["id"] == user_id), None)
    if user is None:
        return {"id": user_id, "display_name": user_id, "role_id": "viewer", "permissions": []}
    role = next((entry for entry in acl["roles"] if entry["id"] == user["role_id"]), None)
    permissions = role["permissions"] if role else []
    return {**user, "permissions": permissions}


def _readable_source_payload(
    source: dict[str, object],
    *,
    selected: bool,
    order: int,
) -> ReadableContextSourcePayload:
    return ReadableContextSourcePayload(
        id=str(source.get("id") or source.get("path") or ""),
        kind=str(source.get("kind") or "unknown"),
        path=str(source.get("path") or source.get("id") or ""),
        title=str(source.get("title") or source.get("path") or "Untitled source"),
        excerpt=str(source.get("excerpt") or "")[:1200],
        content=str(source.get("content") or ""),
        selected=selected,
        order=order,
        sensitivity=str(source.get("sensitivity") or "internal"),
        origin=str(source.get("origin") or "archive"),
        updated_at=str(source.get("updated_at") or ""),
    )


def _readable_context_bundle(
    container: Container,
    payload: ReadableContextPreviewRequest,
) -> ReadableContextBundlePayload:
    limit = max(1, min(payload.source_limit, 50))
    warnings: list[str] = []
    sources = container.permanent_memory.resolve_sources(
        query=payload.query,
        limit=limit,
        source_ids=payload.source_ids if payload.source_ids else None,
    )
    if not sources:
        sources = container.permanent_memory.search(payload.query, limit=limit)
    used_sources: list[ReadableContextSourcePayload] = []
    for order, source in enumerate(sources):
        source_id = str(source.get("id") or source.get("path") or "")
        try:
            detailed = container.permanent_memory.read_source(source_id, max_chars=8000)
        except Exception as exc:
            detailed = source
            warnings.append(f"{source_id}: {exc}")
        used_sources.append(_readable_source_payload(detailed, selected=True, order=order))
    volatile_payloads: list[VolatileMemoryPayload] = []
    if payload.include_volatile:
        for raw in container.volatile_memory.list():
            if isinstance(raw, dict):
                volatile_payloads.append(
                    VolatileMemoryPayload.from_memory(VolatileMemory.from_mapping(raw))
                )
    markdown = _render_readable_context_markdown(
        query=payload.query,
        sources=used_sources,
        volatile_memories=volatile_payloads,
        token_budget=payload.token_budget,
    )
    return ReadableContextBundlePayload(
        query=payload.query,
        used_sources=used_sources,
        volatile_memories=volatile_payloads,
        estimated_tokens=_estimate_tokens(markdown),
        warnings=warnings,
        markdown=markdown,
    )


def _render_readable_context_markdown(
    *,
    query: str,
    sources: list[ReadableContextSourcePayload],
    volatile_memories: list[VolatileMemoryPayload],
    token_budget: int,
) -> str:
    lines = [
        "# AI 가독 정보 번들",
        "",
        f"- Query: {query or '(없음)'}",
        f"- Token budget: {token_budget}",
        f"- Sources: {len(sources)}",
        f"- Volatile memories: {len(volatile_memories)}",
        "",
    ]
    for source in sources:
        content = source.content or source.excerpt
        lines.extend(
            [
                f"## Source {source.order + 1}: {source.title}",
                f"- kind: {source.kind}",
                f"- path: {source.path}",
                "",
                content[:8000],
                "",
            ]
        )
    if volatile_memories:
        lines.append("## Volatile memories")
        lines.append("")
        for memory in volatile_memories:
            lines.extend(
                [
                    f"### {memory.scope}:{memory.key}",
                    f"- 요약: {memory.summary or '(없음)'}",
                    f"- 현재 의도: {memory.current_intent or '(없음)'}",
                    f"- 원천 참조: {', '.join(memory.relevant_sources) or '(없음)'}",
                    "",
                ]
            )
    return "\n".join(lines).strip()


def _estimate_tokens(text: str) -> int:
    return max(1, len(text) // 4) if text else 0


def _ai_job_payload(record: AiJobRecord) -> AiJobStatusPayload:
    return AiJobStatusPayload(**record.to_dict())


def _start_ai_job(
    container: Container,
    *,
    task: str,
    actor: str = "system",
    input_summary: str = "",
    used_sources: list[str] | None = None,
) -> AiJobRecord:
    job = container.ai_jobs.create(
        task=task,
        actor=actor,
        input_summary=input_summary,
        used_sources=used_sources,
    )
    running = job.with_status("running")
    return container.ai_jobs.update(running)


def _finish_ai_job(
    container: Container,
    job: AiJobRecord,
    *,
    status: Literal["succeeded", "failed"],
    result_path: str = "",
    error: str = "",
    used_sources: list[str] | None = None,
) -> AiJobRecord:
    return container.ai_jobs.update(
        job.with_status(
            status,
            result_path=result_path,
            error=error,
            used_sources=used_sources,
        )
    )


def _settings_api_key(container: Container, provider: str) -> str:
    if provider == "openai":
        return container.settings.llm.openai_api_key
    if provider == "anthropic":
        return container.settings.llm.anthropic_api_key
    if provider == "gemini":
        return container.settings.llm.gemini_api_key
    return ""


def _audit(
    container: Container,
    *,
    actor: str = "system",
    action: str,
    target: str,
    target_id: str = "",
    details: dict[str, object] | None = None,
) -> None:
    container.audit_log.record(
        actor=actor,
        action=action,
        target=target,
        target_id=target_id,
        details=details,
    )


def _memory_refresh_prompt(query: str, sources: list[dict[str, object]]) -> str:
    source_md = "\n\n".join(
        f"### {source.get('path')}\n{source.get('excerpt', '')}" for source in sources
    )
    return render_prompt("office/memory_refresh.md.j2", query=query, source_md=source_md).strip()


def _context_compression_prompt(
    query: str,
    token_budget: int,
    sources: list[dict[str, object]],
    *,
    volatile_appendix: str = "",
) -> str:
    source_md = "\n\n".join(
        f"### {source.get('path')}\n{source.get('excerpt', '')}" for source in sources
    )
    return render_prompt(
        "office/context_compression.md.j2",
        query=query,
        token_budget=token_budget,
        source_md=source_md,
        volatile_appendix=volatile_appendix,
    ).strip()


def _volatile_memories_markdown(container: Container) -> str:
    chunks: list[str] = []
    for raw in container.volatile_memory.list(scope=None):
        try:
            vm = VolatileMemory.from_mapping(raw)
            chunks.append(vm.to_markdown())
        except Exception:
            continue
    joined = "\n\n".join(chunks)
    return joined[:8000]


def _lines_from_markdown(markdown: str, *, prefix: str = "-") -> list[str]:
    lines: list[str] = []
    for line in markdown.splitlines():
        stripped = line.strip()
        if stripped.startswith(prefix):
            lines.append(stripped.lstrip(prefix).strip())
    return lines[:20]


def _agent_plan_steps(
    objective: str, schedule_refs: list[str], memory_refs: list[str]
) -> list[dict[str, object]]:
    return [
        {
            "id": "review-memory",
            "title": "영구 메모리와 압축 컨텍스트 검토",
            "requires_approval": False,
            "memory_refs": memory_refs,
        },
        {
            "id": "split-work",
            "title": f"작업 분할: {objective}",
            "requires_approval": True,
            "schedule_refs": schedule_refs,
        },
        {
            "id": "execute-approved",
            "title": "승인된 작업 실행",
            "requires_approval": True,
            "external_effects": ["files", "llm"],
        },
    ]


def _update_user_volatile_memory_after_chat(
    container: Container,
    *,
    actor: str,
    user_message: str,
    answer: str,
) -> None:
    existing = container.volatile_memory.read(scope="user", key=actor)
    summary = "\n".join(
        part
        for part in [
            existing.summary,
            f"최근 대화: 사용자={user_message[:240]} / 응답={answer[:240]}",
        ]
        if part
    )[-2000:]
    container.volatile_memory.write(
        VolatileMemory(
            scope="user",
            key=actor,
            summary=summary,
            current_intent=user_message[:500],
            active_context=existing.active_context,
            preferences=existing.preferences,
            open_questions=existing.open_questions,
            next_actions=existing.next_actions,
            relevant_sources=existing.relevant_sources,
        )
    )


def _masked_provider_payload(container: Container) -> list[dict[str, object]]:
    providers = container.secret_store.list_masked()
    metadata = {
        item["provider"]: item
        for item in provider_payload(vllm_base_url=container.settings.llm.vllm_base_url)
    }
    for provider in providers:
        provider_id = str(provider["provider"])
        provider["label"] = metadata.get(provider_id, {}).get("label", provider_id)
        provider["base_url"] = default_base_url(
            provider_id,
            vllm_base_url=container.settings.llm.vllm_base_url,
        )
        provider["base_url_source"] = "system"
    return providers


def _sync_local_llm_state(container: Container, *, enabled: bool) -> None:
    provider = container.embedded_vllm()
    if provider is None:
        return
    runtime = container.llm_runtime.read()
    provider.configure_model(runtime.local_model or container.settings.llm.vllm_model)
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
            state="unavailable",
            model=model,
            loaded=False,
            message=(
                "현재 백엔드는 로컬 GPU 임베드 모드가 아닙니다. Docker 백엔드에서는 모델을 직접 "
                "올릴 수 없으니 호스트에서 PM_VLLM_MODE=embedded 로 실행하세요."
            ),
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
    actor: str = "system",
    kind: str,
    instruction: str,
) -> GeneratedDocumentPayload:
    prompt = render_prompt(
        "office/hiring_document.md.j2",
        context=_office_context(container),
        role_title=payload.role_title,
        business_need=payload.business_need,
        priority=payload.priority,
        instruction=instruction,
    ).strip()
    job = _start_ai_job(
        container,
        task=f"hiring.{kind}",
        actor=actor,
        input_summary=f"{payload.role_title}: {payload.business_need}",
    )
    try:
        markdown = await _complete_office_task(container, prompt, task="hiring")
        path = _write_generated_doc(
            container.settings.archive_dir,
            folder="hr/interview_kits",
            slug=f"{kind}_{payload.role_title}",
            markdown=markdown,
        )
        job = _finish_ai_job(container, job, status="succeeded", result_path=path)
    except Exception as exc:
        _finish_ai_job(container, job, status="failed", error=str(exc))
        raise
    return GeneratedDocumentPayload(
        title=payload.role_title,
        markdown=markdown,
        path=path,
        ai_job=_ai_job_payload(job).model_dump(),
    )


def _resolve_runtime_task(container: Container, task: str) -> tuple[LlmProviderName, LlmRoute]:
    runtime = container.llm_runtime.read()
    task_route = runtime.route_for(task)
    if task_route.route == "local" and not runtime.local_enabled:
        task_route = runtime.route_for("chat")
    if task_route.route == "api" and not runtime.api_enabled:
        task_route = runtime.route_for("chat")
    route: LlmRoute = "local" if task_route.route == "local" else "cloud"
    return task_route.provider, route


async def _complete_office_task(
    container: Container, prompt: str, *, task: str = "document_generation"
) -> str:
    provider, route = _resolve_runtime_task(container, task)
    messages = [
        LlmMessage(
            "system",
            render_prompt("office/office_task_system.md.j2").strip(),
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
        task=task,
    )
    return response.text.strip() or "_(LLM 응답 없음)_"


async def _complete_patchops_task(
    container: Container, prompt: str, *, task: str = "patch_planning"
) -> str:
    provider, route = _resolve_runtime_task(container, task)
    messages = [
        LlmMessage(
            "system",
            (
                "당신은 PatchOps Agent입니다. 코드를 수정하기 전에 저장소를 조사하고, "
                "자가 질문, 증거 기반 계획, diff 초안, 검증 계획, 패치 메모리를 정형 출력합니다. "
                "민감정보와 secret은 절대 노출하지 마세요."
            ),
        ),
        LlmMessage("user", prompt),
    ]
    response = await _complete_with_provider(
        container,
        messages,
        provider=provider,
        route=route,
        temperature=0.1,
        max_tokens=2200,
        task=task,
    )
    return response.text.strip()


async def _complete_with_provider(
    container: Container,
    messages: list[LlmMessage],
    *,
    provider: LlmProviderName,
    route: LlmRoute,
    temperature: float,
    max_tokens: int,
    task: str = "chat",
    actor: str = "",
) -> LlmResponse:
    destination = _firewall_destination(provider=provider, route=route)
    policy = load_context_firewall_policy(container.settings.workspace_dir)
    messages, firewall_result = sanitize_llm_messages(
        messages,
        destination=destination,
        task_type=str(provider),
        policy=policy,
    )
    firewall_result = record_firewall_audit(
        container,
        firewall_result,
        destination=destination,
        task_type=str(provider),
    )
    if destination in {"frontier_llm", "cloud_llm", "api_llm", "openai", "anthropic", "gemini"}:
        if firewall_result.decision == "block":
            raise HTTPException(
                status.HTTP_403_FORBIDDEN,
                detail="Context Firewall blocked outbound frontier LLM context.",
            )
        if firewall_result.decision == "local_only":
            route = "local"
    try:
        container.token_usage.check_limits(attempted_tokens=max(0, int(max_tokens or 0)))
    except TokenLimitExceededError as exc:
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            detail=str(exc),
        ) from exc
    try:
        response: LlmResponse
        sanitized: LlmResponse
        if container.settings.llm.gateway_url:
            response = await _complete_via_gateway(
                container,
                messages,
                provider=provider,
                route=route,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            sanitized = sanitize_llm_response(
                response, destination=destination, task_type=str(provider)
            )
            _record_token_usage(
                container,
                provider=provider,
                model=sanitized.model,
                task=task,
                actor=actor,
                response=sanitized,
            )
            return sanitized
        saved = container.secret_store.read(provider)
        if saved and saved.api_key and provider == "openai" and route != "local":
            response = await OpenAiProvider(
                api_key=saved.api_key,
                model=saved.model or container.settings.llm.openai_model,
                base_url=default_base_url("openai"),
            ).complete(messages, route=route, temperature=temperature, max_tokens=max_tokens)
            sanitized = sanitize_llm_response(
                response, destination=destination, task_type=str(provider)
            )
            _record_token_usage(
                container,
                provider=provider,
                model=sanitized.model,
                task=task,
                actor=actor,
                response=sanitized,
            )
            return sanitized
        if saved and saved.api_key and provider == "anthropic" and route != "local":
            response = await AnthropicProvider(
                api_key=saved.api_key,
                model=saved.model or container.settings.llm.anthropic_model,
                base_url=default_base_url("anthropic"),
            ).complete(messages, route=route, temperature=temperature, max_tokens=max_tokens)
            sanitized = sanitize_llm_response(
                response, destination=destination, task_type=str(provider)
            )
            _record_token_usage(
                container,
                provider=provider,
                model=sanitized.model,
                task=task,
                actor=actor,
                response=sanitized,
            )
            return sanitized
        if saved and saved.api_key and provider == "gemini" and route != "local":
            response = await GeminiProvider(
                api_key=saved.api_key,
                model=saved.model or container.settings.llm.gemini_model,
                base_url=default_base_url("gemini"),
            ).complete(messages, route=route, temperature=temperature, max_tokens=max_tokens)
            sanitized = sanitize_llm_response(
                response, destination=destination, task_type=str(provider)
            )
            _record_token_usage(
                container,
                provider=provider,
                model=sanitized.model,
                task=task,
                actor=actor,
                response=sanitized,
            )
            return sanitized
        if saved and provider == "vllm" and container.settings.llm.vllm_mode != "embedded":
            response = await VllmProvider(
                base_url=saved.base_url or container.settings.llm.vllm_base_url,
                model=saved.model or container.settings.llm.vllm_model,
                api_key=saved.api_key or "EMPTY",
            ).complete(messages, route=route, temperature=temperature, max_tokens=max_tokens)
            sanitized = sanitize_llm_response(
                response, destination="local_llm", task_type=str(provider)
            )
            _record_token_usage(
                container,
                provider=provider,
                model=sanitized.model,
                task=task,
                actor=actor,
                response=sanitized,
            )
            return sanitized
        if isinstance(container.llm, LlmGateway):
            response = await container.llm.complete_with_provider(
                messages,
                provider_name=provider,
                route=route,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            sanitized = sanitize_llm_response(
                response, destination=destination, task_type=str(provider)
            )
            _record_token_usage(
                container,
                provider=provider,
                model=sanitized.model,
                task=task,
                actor=actor,
                response=sanitized,
            )
            return sanitized
        response = await container.llm.complete(
            messages,
            route=route,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        sanitized = sanitize_llm_response(response, destination=destination, task_type=str(provider))
        _record_token_usage(
            container,
            provider=provider,
            model=sanitized.model,
            task=task,
            actor=actor,
            response=sanitized,
        )
        return sanitized
    except VllmConnectionError as exc:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
    except VllmEmbeddedError as exc:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
    except HTTPException:
        raise
    except Exception as exc:
        raise _llm_provider_http_error(provider, exc) from exc


def _record_token_usage(
    container: Container,
    *,
    provider: LlmProviderName,
    model: str,
    task: str,
    actor: str,
    response: LlmResponse,
) -> None:
    try:
        container.token_usage.record(
            provider=str(provider),
            model=model,
            task=task,
            actor=actor,
            prompt_tokens=int(getattr(response, "prompt_tokens", 0) or 0),
            completion_tokens=int(getattr(response, "completion_tokens", 0) or 0),
        )
    except Exception:
        return


def _llm_provider_http_error(provider: LlmProviderName, exc: Exception) -> HTTPException:
    """Convert a third-party LLM client error into a user-friendly HTTPException."""

    status_code = getattr(exc, "status_code", None)
    detail = str(exc) or exc.__class__.__name__
    if isinstance(status_code, int):
        if status_code in {400, 401, 403, 404, 422}:
            return HTTPException(
                status.HTTP_400_BAD_REQUEST,
                detail=f"{provider} 요청이 거절되었습니다: {detail}",
            )
        if status_code in {408, 429, 500, 502, 503, 504}:
            return HTTPException(
                status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"{provider} 서비스 응답 실패: {detail}",
            )
    return HTTPException(
        status.HTTP_502_BAD_GATEWAY,
        detail=f"{provider} 호출 중 오류: {detail}",
    )


def _firewall_destination(*, provider: LlmProviderName, route: LlmRoute) -> str:
    if route == "local" or provider in {"vllm", "fake"}:
        return "local_llm"
    if provider in {"openai", "anthropic", "gemini"}:
        return "frontier_llm"
    return "cloud_llm"


async def _complete_via_gateway(
    container: Container,
    messages: list[LlmMessage],
    *,
    provider: LlmProviderName,
    route: LlmRoute,
    temperature: float,
    max_tokens: int,
) -> LlmResponse:
    payload = {
        "provider": provider,
        "route": route,
        "messages": [{"role": message.role, "content": message.content} for message in messages],
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    async with httpx.AsyncClient(timeout=120) as client:
        response = await client.post(
            f"{container.settings.llm.gateway_url.rstrip('/')}/v1/chat/completions",
            json=payload,
        )
        response.raise_for_status()
    data = response.json()
    return LlmResponse(
        text=str(data.get("text") or ""),
        prompt_tokens=int(data.get("prompt_tokens") or 0),
        completion_tokens=int(data.get("completion_tokens") or 0),
        route=route,
        model=str(data.get("model") or provider),
    )


def _office_context(container: Container) -> str:
    recent = _recent_logs(container.settings.archive_dir, limit=8)
    permanent = container.permanent_memory.recent(limit=8)
    permanent_md = "\n".join(
        f"- [{source.get('kind')}] {source.get('path')}: {source.get('title')}"
        for source in permanent
    )
    compressed = container.compressed_context.read(scope="global", key="default").to_markdown()
    volatile = container.volatile_memory.read(scope="global", key="default").to_markdown()
    recent_md = "\n".join(
        f"- {entry.get('repo', '')} #{entry.get('external_id', '')} status={entry.get('status', '')} path={entry.get('path', '')}"
        for entry in recent
    )
    return f"""
회사 메모리:
{container.operations_memory.read().to_markdown()}

현재 작업 메모리:
{container.work_memory.read().to_markdown()}

영구 원천 기록:
{permanent_md or "- 없음"}

압축 컨텍스트:
{compressed}

휘발성 메모리:
{volatile}

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
            f"- {item.get('summary') or item.get('title')} ({item.get('status')})"
            for item in rejected[:5]
        )
    else:
        lines.append("명시적인 실패 상태는 없습니다. 오래된 진행 항목과 담당자 공백을 확인하세요.")
    return "\n".join(lines)


def _resolve_github_runtime(
    container: Container,
) -> tuple[GitHubConnectorConfig, str, str]:
    config = container.integration_config.read().github
    saved_token = container.secret_store.read("github_app")
    token = (saved_token.api_key if saved_token else "") or container.settings.github.app_token
    trigger_label = config.trigger_label or container.settings.github.trigger_label
    return config, token, trigger_label


def _resolve_discord_runtime(
    container: Container,
) -> tuple[DiscordConnectorConfig, str]:
    config = container.integration_config.read().discord
    saved_token = container.secret_store.read("discord_bot")
    token = (saved_token.api_key if saved_token else "") or container.settings.discord.bot_token
    return config, token


def _save_github_secrets(container: Container, payload: GitHubConnectorPayload) -> None:
    if payload.app_token.strip():
        container.secret_store.upsert(
            ApiKeyRecord(
                provider="github_app",
                api_key=payload.app_token.strip(),
                model="",
                base_url="",
            )
        )
    if payload.webhook_secret.strip():
        container.secret_store.upsert(
            ApiKeyRecord(
                provider="github_webhook",
                api_key=payload.webhook_secret.strip(),
                model="",
                base_url="",
            )
        )


def _save_discord_secrets(container: Container, payload: DiscordConnectorPayload) -> None:
    if payload.bot_token.strip():
        container.secret_store.upsert(
            ApiKeyRecord(
                provider="discord_bot",
                api_key=payload.bot_token.strip(),
                model="",
                base_url="",
            )
        )


def _integration_config_payload(
    container: Container,
    *,
    config: IntegrationConfig | None = None,
) -> IntegrationConfigPayload:
    config = config or container.integration_config.read()
    github = config.github
    discord = config.discord
    return IntegrationConfigPayload(
        github=GitHubConnectorPayload(
            enabled=github.enabled,
            allowed_repos=list(github.allowed_repos),
            trigger_label=github.trigger_label,
            webhook_secret_present=container.secret_store.has_secret("github_webhook"),
            app_token_present=container.secret_store.has_secret("github_app"),
            event_forms=list(github.event_forms),
        ),
        discord=DiscordConnectorPayload(
            enabled=discord.enabled,
            bot_token_present=container.secret_store.has_secret("discord_bot"),
            guild_allowlist=list(discord.guild_allowlist),
            channel_bindings=[
                DiscordChannelBindingPayload(
                    guild_id=binding.guild_id,
                    channel_id=binding.channel_id,
                    channel_name=binding.channel_name,
                    repo=binding.repo,
                )
                for binding in discord.channel_bindings
            ],
            command_forms=list(discord.command_forms),
        ),
    )


def _read_archive_document(container: Container, raw_path: str) -> DocumentReadPayload:
    if not raw_path or not raw_path.strip():
        raise ValueError("path 는 필수입니다.")
    cleaned = raw_path.strip().lstrip("/")
    if "\x00" in cleaned:
        raise ValueError("path 에 잘못된 문자가 포함되어 있습니다.")
    archive_root = container.settings.archive_dir.resolve()
    candidate = (archive_root / cleaned).resolve()
    try:
        candidate.relative_to(archive_root)
    except ValueError as exc:
        raise ValueError("archive 외부 경로는 열람할 수 없습니다.") from exc
    if not candidate.exists() or not candidate.is_file():
        raise FileNotFoundError(f"문서를 찾을 수 없습니다: {cleaned}")
    if candidate.suffix.lower() not in {".md", ".markdown", ".txt", ".json", ".jsonl", ".yaml", ".yml"}:
        raise ValueError("열람 지원 파일 형식이 아닙니다.")
    text = candidate.read_text(encoding="utf-8")
    stat = candidate.stat()
    modified = datetime.fromtimestamp(stat.st_mtime, tz=UTC).isoformat()
    return DocumentReadPayload(
        path=str(candidate.relative_to(archive_root)).replace("\\", "/"),
        markdown=text,
        bytes=stat.st_size,
        modified_at=modified,
    )


def _token_limit_status(container: Container) -> TokenLimitStatusPayload:
    limits = container.token_usage.read_limits()
    summary = container.token_usage.summary()
    return TokenLimitStatusPayload(
        limits=TokenLimitPayload(**limits.to_dict()),
        usage=TokenUsageSummaryPayload(
            daily_total=summary.daily_total,
            monthly_total=summary.monthly_total,
            by_provider=dict(summary.by_provider),
            by_task=dict(summary.by_task),
            by_actor=dict(summary.by_actor),
            recent=[TokenUsageEntryPayload(**entry.to_dict()) for entry in summary.recent],
        ),
    )


def _patch_record_payload(record: PatchRecord) -> PatchRecordPayload:
    return PatchRecordPayload(**record.to_dict())


def _patch_record_detail_payload(record: PatchRecord, markdown: str) -> PatchRecordDetailPayload:
    return PatchRecordDetailPayload(markdown=markdown, **record.to_dict())


async def _fetch_github_status(container: Container) -> IntegrationStatusPayload:
    config, token, trigger_label = _resolve_github_runtime(container)
    if not config.enabled:
        return IntegrationStatusPayload(
            ok=False,
            configured=False,
            reason="GitHub 커넥터가 비활성 상태입니다. 설정 폼에서 활성화하세요.",
            items=[],
        )
    repos = config.allowed_repos or container.settings.github.allowed_repos
    if not repos:
        return IntegrationStatusPayload(
            ok=False,
            configured=False,
            reason="허용된 저장소가 없습니다. GitHub 설정에 repo를 추가하세요.",
            items=[],
        )
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
                        "labels": trigger_label,
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
                        "event_forms": list(config.event_forms),
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
    config, token = _resolve_discord_runtime(container)
    if not config.enabled:
        return IntegrationStatusPayload(
            ok=False,
            configured=False,
            reason="Discord 커넥터가 비활성 상태입니다. 설정 폼에서 활성화하세요.",
            items=[],
        )
    bindings: list[DiscordChannelBindingConfig] = list(config.channel_bindings)
    if not bindings:
        for legacy in container.discord.channel_map.bindings:
            bindings.append(
                DiscordChannelBindingConfig(
                    guild_id=legacy.guild_id,
                    channel_id=legacy.channel_id,
                    channel_name=legacy.channel_name,
                    repo=legacy.repo.full_name,
                )
            )
    if not bindings:
        return IntegrationStatusPayload(
            ok=False,
            configured=False,
            reason="채널 바인딩이 없습니다. Discord 설정 폼에서 채널을 등록하세요.",
            items=[],
        )
    items: list[dict[str, Any]] = []
    async with httpx.AsyncClient(timeout=10) as client:
        for binding in bindings:
            item: dict[str, Any] = {
                "guild_id": binding.guild_id,
                "channel_id": binding.channel_id,
                "channel_name": binding.channel_name,
                "repo": binding.repo,
                "live": False,
                "command_forms": list(config.command_forms),
            }
            if token and binding.channel_id:
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
            elif not token:
                item["reason"] = "Discord bot 토큰이 등록되지 않았습니다."
            items.append(item)
    return IntegrationStatusPayload(ok=True, configured=True, items=items)
