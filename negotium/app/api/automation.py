"""Automation and notification API routes."""

from __future__ import annotations

from zoneinfo import ZoneInfo

from fastapi import APIRouter, Header, HTTPException, status

from negotium.app.api._shared import _audit, _require, _require_user
from negotium.app.container import Container
from negotium.app.schemas.automation import (
    AutomationConfigPayload,
    AutomationStatusPayload,
    MarkReadPayload,
    NotificationsPayload,
    RunJobsPayload,
    RunResultPayload,
)
from negotium.app.services.automation_service import (
    REMINDER_JOB,
    SEARCH_INDEX_JOB,
    WEEKLY_JOB,
    run_due_jobs,
    run_jobs,
)

_KNOWN_JOBS = {WEEKLY_JOB, REMINDER_JOB, SEARCH_INDEX_JOB}


def create_automation_router(container: Container) -> APIRouter:
    """Routes for scheduled automation config and in-app notifications."""
    router = APIRouter()

    def _status_payload() -> AutomationStatusPayload:
        config = container.automation.read_config()
        state = container.automation.read_state()
        return AutomationStatusPayload(
            config=AutomationConfigPayload.model_validate(config.to_dict()),
            state={key: str(value) for key, value in state.to_dict().items()},
        )

    @router.get("/automation/config")
    async def read_automation_config(
        x_ng_user: str | None = Header(default=None, alias="X-NG-User"),
    ) -> AutomationStatusPayload:
        _require(container, x_ng_user, "admin:integrations")
        return _status_payload()

    @router.put("/automation/config")
    async def write_automation_config(
        payload: AutomationConfigPayload,
        x_ng_user: str | None = Header(default=None, alias="X-NG-User"),
    ) -> AutomationStatusPayload:
        actor = _require(container, x_ng_user, "admin:integrations")
        try:
            ZoneInfo(payload.weekly_report.timezone)
        except (KeyError, ValueError) as exc:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                detail=f"unknown timezone: {payload.weekly_report.timezone}",
            ) from exc
        config = container.automation.write_config(payload.to_config())
        _audit(
            container,
            actor=actor,
            action="automation.config_update",
            target="automation",
            # The webhook URL is a capability secret — audit only its presence.
            details={
                "weekly_enabled": config.weekly_report.enabled,
                "reminders_enabled": config.reminders.enabled,
                "search_embeddings_enabled": config.search.embeddings_enabled,
                "webhook_url_set": bool(config.webhook_url),
            },
        )
        return _status_payload()

    @router.post("/automation/run")
    async def run_automation(
        payload: RunJobsPayload,
        x_ng_user: str | None = Header(default=None, alias="X-NG-User"),
    ) -> RunResultPayload:
        actor = _require(container, x_ng_user, "admin:integrations")
        jobs = [job for job in payload.jobs if job in _KNOWN_JOBS]
        if payload.jobs and not jobs:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                detail=f"unknown jobs; expected any of {sorted(_KNOWN_JOBS)}",
            )
        executed = await run_jobs(container, jobs) if jobs else await run_due_jobs(container)
        _audit(
            container,
            actor=actor,
            action="automation.manual_run",
            target="automation",
            details={"requested": jobs, "executed": executed},
        )
        return RunResultPayload(executed=executed)

    @router.get("/automation/search-index")
    async def read_search_index_stats(
        x_ng_user: str | None = Header(default=None, alias="X-NG-User"),
    ) -> dict[str, object]:
        _require(container, x_ng_user, "admin:integrations")
        config = container.automation.read_config()
        return {
            **container.search_index.stats(),
            "embeddings_enabled": config.search.embeddings_enabled,
        }

    @router.get("/notifications")
    async def read_notifications(
        x_ng_user: str | None = Header(default=None, alias="X-NG-User"),
    ) -> NotificationsPayload:
        actor = _require_user(container, x_ng_user)
        items = container.notifications.list_for(actor)
        unread = 0
        for item in items:
            read_by = item.get("read_by")
            if not isinstance(read_by, list) or actor not in read_by:
                unread += 1
        return NotificationsPayload(items=items, unread=unread)

    @router.post("/notifications/read")
    async def mark_notifications_read(
        payload: MarkReadPayload,
        x_ng_user: str | None = Header(default=None, alias="X-NG-User"),
    ) -> dict[str, int]:
        actor = _require_user(container, x_ng_user)
        changed = container.notifications.mark_read(payload.ids, actor)
        return {"marked": changed}

    return router
