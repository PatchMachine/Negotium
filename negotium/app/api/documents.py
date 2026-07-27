"""Documents API routes (split from the former monolithic router)."""

from __future__ import annotations

from fastapi import APIRouter, Header

from negotium.app.api._shared import (
    HIRING_KIND_INSTRUCTIONS,
    _audit,
    _complete_office_task,
    _generate_hiring_document,
    _generate_office_document,
    _hr_evaluation_context,
    _hr_evaluation_markdown,
    _require,
    _write_generated_doc,
)
from negotium.app.container import Container
from negotium.app.schemas.core import (
    GeneratedDocumentPayload,
    HiringRequest,
    HrEvaluationDraftRequest,
    HrEvaluationSaveRequest,
    OfficeDocumentRequest,
)
from negotium.prompts import render as render_prompt


def create_documents_router(container: Container) -> APIRouter:
    """Routes for the documents domain."""
    router = APIRouter()

    @router.post("/hr/role-requirements")
    async def create_role_requirements(
        payload: HiringRequest,
        x_ng_user: str | None = Header(default=None, alias="X-NG-User"),
    ) -> GeneratedDocumentPayload:
        actor = _require(container, x_ng_user, "documents:write")
        result = await _generate_hiring_document(
            container,
            payload,
            actor=actor,
            kind="role_requirements",
            instruction=HIRING_KIND_INSTRUCTIONS["role_requirements"],
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
        x_ng_user: str | None = Header(default=None, alias="X-NG-User"),
    ) -> GeneratedDocumentPayload:
        actor = _require(container, x_ng_user, "documents:write")
        result = await _generate_hiring_document(
            container,
            payload,
            actor=actor,
            kind="interview_kit",
            instruction=HIRING_KIND_INSTRUCTIONS["interview_kit"],
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
        x_ng_user: str | None = Header(default=None, alias="X-NG-User"),
    ) -> GeneratedDocumentPayload:
        actor = _require(container, x_ng_user, "documents:write")
        result = await _generate_hiring_document(
            container,
            payload,
            actor=actor,
            kind="onboarding_plan",
            instruction=HIRING_KIND_INSTRUCTIONS["onboarding_plan"],
        )
        _audit(
            container,
            actor=actor,
            action="document.create",
            target="document",
            target_id=result.path,
        )
        return result

    @router.get("/hr/evaluation/context")
    async def hr_evaluation_context(
        user_id: str,
        x_ng_user: str | None = Header(default=None, alias="X-NG-User"),
    ) -> dict[str, object]:
        _require(container, x_ng_user, "admin:hr_evaluation")
        return _hr_evaluation_context(container, user_id=user_id)

    @router.post("/hr/evaluation/draft")
    async def hr_evaluation_draft(
        payload: HrEvaluationDraftRequest,
        x_ng_user: str | None = Header(default=None, alias="X-NG-User"),
    ) -> dict[str, object]:
        actor = _require(container, x_ng_user, "admin:hr_evaluation")
        context = _hr_evaluation_context(
            container, user_id=payload.user_id, work_item_ids=payload.work_item_ids
        )
        prompt = render_prompt(
            "office/hr_evaluation.md.j2",
            context=context,
            period=payload.period,
            criteria=payload.criteria,
            notes=payload.notes,
        ).strip()
        text = await _complete_office_task(container, prompt, task="hiring")
        _audit(
            container,
            actor=actor,
            action="hr.evaluation.draft",
            target="user",
            target_id=payload.user_id,
        )
        return {"ok": True, "draft": text, "context": context}

    @router.post("/hr/evaluation/save")
    async def hr_evaluation_save(
        payload: HrEvaluationSaveRequest,
        x_ng_user: str | None = Header(default=None, alias="X-NG-User"),
    ) -> dict[str, object]:
        actor = _require(container, x_ng_user, "admin:hr_evaluation")
        from negotium.archive.hr_evaluations import HrEvaluationRecord

        context = _hr_evaluation_context(
            container, user_id=payload.user_id, work_item_ids=payload.work_item_ids
        )
        draft_record = HrEvaluationRecord.create(
            user_id=payload.user_id,
            period=payload.period,
            work_item_ids=payload.work_item_ids,
            draft=payload.draft,
            final_text=payload.final_text,
            evidence=payload.evidence,
            created_by=actor,
            source_refs=payload.source_refs,
        )
        document_path = _write_generated_doc(
            container.settings.archive_dir,
            folder="hr/evaluations",
            slug=f"hr_evaluation_{payload.user_id}_{payload.period or draft_record.id[:8]}",
            markdown=_hr_evaluation_markdown(draft_record, context=context),
        )
        record = container.hr_evaluations.append(
            HrEvaluationRecord.from_mapping(
                {**draft_record.to_dict(), "document_path": document_path}
            )
        )
        _audit(
            container,
            actor=actor,
            action="hr.evaluation.save",
            target="user",
            target_id=payload.user_id,
            details={"document_path": document_path},
        )
        return {"ok": True, "record": record.to_dict(), "document_path": document_path}

    @router.get("/hr/evaluation/records")
    async def hr_evaluation_records(
        user_id: str = "",
        limit: int = 100,
        x_ng_user: str | None = Header(default=None, alias="X-NG-User"),
    ) -> dict[str, object]:
        _require(container, x_ng_user, "admin:hr_evaluation")
        return {"records": container.hr_evaluations.list_recent(user_id=user_id, limit=limit)}

    @router.post("/documents/generate")
    async def create_office_document(
        payload: OfficeDocumentRequest,
        x_ng_user: str | None = Header(default=None, alias="X-NG-User"),
    ) -> GeneratedDocumentPayload:
        actor = _require(container, x_ng_user, "documents:write")
        return await _generate_office_document(container, payload, actor=actor)

    return router
