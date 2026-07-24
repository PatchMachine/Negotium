"""Agent API routes (split from the former monolithic router)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Header, HTTPException, status

from negotium.app.api._shared import (
    _ai_job_payload,
    _audit,
    _complete_office_task,
    _generate_agent_plan_steps,
    _render_agent_plan_markdown,
    _require,
    _write_generated_doc,
)
from negotium.app.container import Container
from negotium.app.schemas.core import (
    AgentPlanRequest,
    AiJobStatusPayload,
    SkillCreateRequest,
    SkillRunRequest,
)
from negotium.app.services.skill_registry import (
    Skill,
    SkillInput,
    get_skill,
    get_skills,
    register_skill,
)
from negotium.app.services.skill_runtime import SkillError, run_skill
from negotium.archive.agent_execution import AgentPlan


def create_agent_router(container: Container) -> APIRouter:
    """Routes for the agent domain."""
    router = APIRouter()

    @router.get("/ai-jobs/recent")
    async def list_ai_jobs(
        limit: int = 30,
        x_ng_user: str | None = Header(default=None, alias="X-NG-User"),
    ) -> dict[str, object]:
        _require(container, x_ng_user, "work:read")
        return {
            "jobs": [
                _ai_job_payload(record).model_dump()
                for record in container.ai_jobs.recent(limit=max(1, min(limit, 200)))
            ]
        }

    @router.get("/ai-jobs/{job_id}")
    async def read_ai_job(
        job_id: str,
        x_ng_user: str | None = Header(default=None, alias="X-NG-User"),
    ) -> AiJobStatusPayload:
        _require(container, x_ng_user, "work:read")
        record = container.ai_jobs.get(job_id)
        if record is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail="AI job not found")
        return _ai_job_payload(record)

    @router.post("/agent/plans/generate")
    async def generate_agent_plan(
        payload: AgentPlanRequest,
        x_ng_user: str | None = Header(default=None, alias="X-NG-User"),
    ) -> dict[str, object]:
        actor = _require(container, x_ng_user, "memory:write")
        memory_refs = payload.memory_refs or [
            str(source["path"]) for source in container.permanent_memory.recent(limit=5)
        ]
        schedule_refs = payload.schedule_refs or [
            str(item["id"]) for item in container.work_schedule.list()[:10]
        ]
        steps = await _generate_agent_plan_steps(
            container,
            objective=payload.objective,
            context=payload.context,
            schedule_refs=schedule_refs,
            memory_refs=memory_refs,
        )
        plan_title = payload.title or payload.objective
        markdown = _render_agent_plan_markdown(
            title=plan_title,
            objective=payload.objective,
            steps=steps,
            context=payload.context,
        )
        markdown_path = _write_generated_doc(
            container.settings.archive_dir,
            folder="plans",
            slug=f"plan_{plan_title}",
            markdown=markdown,
        )
        plan = container.agent_execution.save_plan(
            AgentPlan.create(
                title=plan_title,
                objective=payload.objective,
                mode=payload.mode,
                schedule_refs=schedule_refs,
                memory_refs=memory_refs,
                steps=steps,
                created_by=actor,
                plan_markdown_path=markdown_path,
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
        x_ng_user: str | None = Header(default=None, alias="X-NG-User"),
    ) -> dict[str, object]:
        _require(container, x_ng_user, "work:read")
        return {"plans": container.agent_execution.list_plans()}

    @router.post("/agent/plans/{plan_id}/approve")
    async def approve_agent_plan(
        plan_id: str,
        x_ng_user: str | None = Header(default=None, alias="X-NG-User"),
    ) -> dict[str, object]:
        actor = _require(container, x_ng_user, "admin:users")
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
        x_ng_user: str | None = Header(default=None, alias="X-NG-User"),
    ) -> dict[str, object]:
        actor = _require(container, x_ng_user, "memory:write")
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
        x_ng_user: str | None = Header(default=None, alias="X-NG-User"),
    ) -> dict[str, object]:
        actor = _require(container, x_ng_user, "admin:users")
        _audit(
            container,
            actor=actor,
            action="agent.run.step_approved",
            target="agent_run",
            target_id=run_id,
        )
        return {"ok": True, "run_id": run_id, "approved_by": actor}

    @router.get("/skills")
    async def list_skills(
        x_ng_user: str | None = Header(default=None, alias="X-NG-User"),
    ) -> dict[str, object]:
        _require(container, x_ng_user, "work:read")
        return {"skills": [skill.to_descriptor() for skill in get_skills().values()]}

    @router.post("/skills")
    async def create_skill(
        payload: SkillCreateRequest,
        x_ng_user: str | None = Header(default=None, alias="X-NG-User"),
    ) -> dict[str, object]:
        actor = _require(container, x_ng_user, "admin:users")
        skill = Skill(
            id=payload.id.strip(),
            name=payload.name.strip(),
            description=payload.description.strip(),
            executor=payload.executor,
            category=payload.category.strip() or "general",
            required_permission=payload.required_permission.strip(),
            risk=payload.risk.strip() or "low",
            tool=payload.tool.strip(),
            output_format=payload.output_format.strip() or "auto",
            output_folder=payload.output_folder.strip() or "documents",
            task=payload.task.strip() or "document_generation",
            inputs=[
                SkillInput(
                    name=item.name.strip(),
                    type=item.type.strip() or "string",
                    required=item.required,
                    description=item.description.strip(),
                )
                for item in payload.inputs
                if item.name.strip()
            ],
            instructions=payload.instructions.strip(),
        )
        if skill.executor == "prompt" and not skill.instructions:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                detail="prompt 스킬은 본문(instructions)이 필요합니다.",
            )
        if skill.executor == "tool" and not skill.tool:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST, detail="tool 스킬은 tool 이름이 필요합니다."
            )
        try:
            register_skill(skill)
        except ValueError as exc:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
        _audit(
            container,
            actor=actor,
            action="skill.create",
            target="skill",
            target_id=skill.id,
        )
        return {
            "ok": True,
            "skill": skill.to_descriptor(),
            "skills": [item.to_descriptor() for item in get_skills().values()],
        }

    @router.post("/skills/{skill_id}/run")
    async def run_skill_endpoint(
        skill_id: str,
        payload: SkillRunRequest,
        x_ng_user: str | None = Header(default=None, alias="X-NG-User"),
    ) -> dict[str, object]:
        skill = get_skill(skill_id)
        if skill is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail="해당 스킬을 찾을 수 없습니다.")
        actor = _require(container, x_ng_user, skill.required_permission or "work:read")

        async def _completion(prompt: str, image_parts: list[dict[str, Any]] | None) -> str:
            return await _complete_office_task(
                container, prompt, task=skill.task, image_parts=image_parts
            )

        try:
            result = await run_skill(
                container, skill_id, dict(payload.inputs), actor=actor, completion=_completion
            )
        except SkillError as exc:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
        _audit(
            container,
            actor=actor,
            action="skill.run",
            target="skill",
            target_id=skill_id,
            details={"status": result.status},
        )
        return {"ok": result.status == "succeeded", "result": result.to_dict()}

    return router
