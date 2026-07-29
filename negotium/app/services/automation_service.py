"""Scheduled office automation: weekly report generation and work reminders.

The scheduler loop in ``app/main.py`` calls :func:`run_due_jobs` once a minute;
all due-ness math lives here so tests can drive it with an injected ``now``.
State keys are marked at attempt start (one attempt per slot) so a failing LLM
is not hammered every tick; the admin "지금 실행" endpoint is the recovery path.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import UTC, date, datetime, timedelta
from typing import TYPE_CHECKING, Any
from zoneinfo import ZoneInfo

import httpx
import structlog

from negotium.archive.automation import (
    AutomationConfig,
    AutomationState,
    ReminderConfig,
    WeeklyReportConfig,
)
from negotium.archive.notifications import NotificationRecord

if TYPE_CHECKING:
    from negotium.app.container import Container

_log = structlog.get_logger(component="automation")

AUTOMATION_ACTOR = "automation"
WEEKLY_JOB = "weekly_report"
REMINDER_JOB = "reminders"
SEARCH_INDEX_JOB = "search_index"
BACKUP_JOB = "archive_backup"
_WEBHOOK_TIMEOUT_SECONDS = 10.0
_EMBED_REFRESH_MINUTES = 15


@dataclass
class OwnerDigest:
    owner_name: str = ""
    overdue: list[str] = field(default_factory=list)
    due_today: list[str] = field(default_factory=list)
    stale: list[str] = field(default_factory=list)

    @property
    def empty(self) -> bool:
        return not (self.overdue or self.due_today or self.stale)


async def run_due_jobs(container: Container, *, now: datetime | None = None) -> list[str]:
    """Run every job whose slot has arrived; returns the executed job names."""
    config = container.automation.read_config()
    state = container.automation.read_state()
    moment = now or datetime.now(UTC)
    local_now = moment.astimezone(ZoneInfo(config.weekly_report.timezone))

    due: list[str] = []
    if config.weekly_report.enabled and _is_weekly_due(config.weekly_report, state, local_now):
        due.append(WEEKLY_JOB)
    if config.reminders.enabled and _is_reminder_due(config.reminders, state, local_now):
        due.append(REMINDER_JOB)
    if config.search.embeddings_enabled and _is_embed_refresh_due(container, moment):
        due.append(SEARCH_INDEX_JOB)
    if config.backup.enabled and _is_backup_due(config, state, moment):
        due.append(BACKUP_JOB)
    if not due:
        return []
    return await run_jobs(container, due, now=moment)


async def run_jobs(
    container: Container, jobs: list[str], *, now: datetime | None = None
) -> list[str]:
    """Force-run the requested jobs (slot checks skipped); marks state keys."""
    config = container.automation.read_config()
    moment = now or datetime.now(UTC)
    local_now = moment.astimezone(ZoneInfo(config.weekly_report.timezone))

    executed: list[str] = []
    for job in jobs:
        if job == WEEKLY_JOB:
            # Mark before attempting: one attempt per slot, no retry storm.
            state = container.automation.read_state()
            container.automation.write_state(
                replace(state, last_weekly_run_key=_weekly_slot_key(local_now))
            )
            if await _run_weekly_report(container, config):
                executed.append(WEEKLY_JOB)
        elif job == REMINDER_JOB:
            state = container.automation.read_state()
            container.automation.write_state(
                replace(state, last_reminder_date=local_now.date().isoformat())
            )
            if await _run_reminders(container, config, today=local_now.date()):
                executed.append(REMINDER_JOB)
        elif job == BACKUP_JOB:
            state = container.automation.read_state()
            container.automation.write_state(replace(state, last_backup_attempt=moment.isoformat()))
            if await _run_backup_job(container):
                executed.append(BACKUP_JOB)
        elif job == SEARCH_INDEX_JOB:
            # Bookkeeping lives in the index manifest, not AutomationState —
            # marking first keeps the attempt-once-per-slot idiom.
            container.search_index.mark_embed_run(moment.isoformat())
            if await _run_search_index(container, config):
                executed.append(SEARCH_INDEX_JOB)
    return executed


async def deliver_webhook(container: Container, url: str, text: str) -> bool:
    """POST a Slack-incoming-webhook-style ``{"text": ...}``; never raises."""
    if not url.strip():
        return True
    try:
        async with httpx.AsyncClient(timeout=_WEBHOOK_TIMEOUT_SECONDS) as client:
            response = await client.post(url, json={"text": text})
        if response.status_code >= 400:
            raise RuntimeError(f"webhook status {response.status_code}")
    except Exception as exc:
        # The URL is a capability secret: log/audit only the failure, never it.
        _log.warning("automation.webhook_failed", error=str(exc))
        _audit_event(container, action="automation.webhook_failed", details={"error": str(exc)})
        return False
    return True


def _is_backup_due(config: AutomationConfig, state: AutomationState, moment: datetime) -> bool:
    if not state.last_backup_attempt:
        return True
    try:
        parsed = datetime.fromisoformat(state.last_backup_attempt)
    except ValueError:
        return True
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return (moment - parsed) >= timedelta(minutes=config.backup.interval_minutes)


async def _run_backup_job(container: Container) -> bool:
    from negotium.app.services.archive_backup_service import run_backup

    try:
        result = await run_backup(container)
    except Exception as exc:
        _log.warning("automation.backup_failed", error=str(exc))
        _audit_event(
            container,
            action="automation.job_failed",
            details={"job": BACKUP_JOB, "error": str(exc)},
        )
        return False
    # The remote URL may carry a token — audit only booleans/reasons.
    _audit_event(
        container,
        action="automation.archive_backup",
        details={"committed": result.get("committed"), "pushed": result.get("pushed")},
    )
    return True


def _is_embed_refresh_due(container: Container, moment: datetime) -> bool:
    last_run = str(container.search_index.stats().get("last_embed_run") or "")
    if not last_run:
        return True
    try:
        parsed = datetime.fromisoformat(last_run)
    except ValueError:
        return True
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return (moment - parsed) >= timedelta(minutes=_EMBED_REFRESH_MINUTES)


async def _run_search_index(container: Container, config: AutomationConfig) -> bool:
    from negotium.app.services.archive_search_service import refresh_embeddings

    try:
        if config.search.embeddings_enabled:
            result = await refresh_embeddings(container)
        else:
            # Manual "지금 재색인" with embeddings off still refreshes keywords.
            result = {"refresh": container.search_index.refresh()}
    except Exception as exc:
        _log.warning("automation.search_index_failed", error=str(exc))
        _audit_event(
            container,
            action="automation.job_failed",
            details={"job": SEARCH_INDEX_JOB, "error": str(exc)},
        )
        return False
    _audit_event(container, action="automation.search_index", details=dict(result))
    return True


async def _run_weekly_report(container: Container, config: AutomationConfig) -> bool:
    from negotium.app.api._shared import _generate_weekly_report

    try:
        result = await _generate_weekly_report(container, actor=AUTOMATION_ACTOR)
    except Exception as exc:
        _log.warning("automation.weekly_report_failed", error=str(exc))
        _audit_event(
            container,
            action="automation.job_failed",
            details={"job": WEEKLY_JOB, "error": str(exc)},
        )
        return False
    container.notifications.add(
        NotificationRecord.create(
            kind="weekly_report",
            title="주간 업무 보고가 생성되었습니다",
            body=f"자동 생성된 보고서: {result.title}",
            link_path=result.path,
        )
    )
    await deliver_webhook(
        container,
        config.webhook_url,
        f"[Negotium] 주간 업무 보고가 자동 생성되었습니다: {result.title} ({result.path})",
    )
    _audit_event(
        container,
        action="automation.weekly_report",
        details={"path": result.path},
    )
    return True


async def _run_reminders(container: Container, config: AutomationConfig, *, today: date) -> bool:
    try:
        rows = container.work_schedule.list()
    except Exception as exc:
        _log.warning("automation.reminders_failed", error=str(exc))
        _audit_event(
            container,
            action="automation.job_failed",
            details={"job": REMINDER_JOB, "error": str(exc)},
        )
        return False

    digests = _classify_work_items(rows, today=today, stale_days=config.reminders.stale_days)
    total_flagged = 0
    for owner_id, digest in digests.items():
        if digest.empty:
            continue
        total_flagged += len(digest.overdue) + len(digest.due_today) + len(digest.stale)
        container.notifications.add(
            NotificationRecord.create(
                user_id=owner_id,
                kind="reminder",
                title="업무 리마인더",
                body=_digest_body(digest),
            )
        )
    if total_flagged:
        await deliver_webhook(
            container,
            config.webhook_url,
            _webhook_summary(digests),
        )
    _audit_event(
        container,
        action="automation.reminders_sent",
        details={"flagged_items": total_flagged, "owners": len(digests)},
    )
    return True


def _digest_body(digest: OwnerDigest) -> str:
    lines: list[str] = []
    if digest.overdue:
        lines.append("마감 초과: " + ", ".join(digest.overdue[:5]))
    if digest.due_today:
        lines.append("오늘 마감: " + ", ".join(digest.due_today[:5]))
    if digest.stale:
        lines.append("오래 정체됨: " + ", ".join(digest.stale[:5]))
    return "\n".join(lines)


def _webhook_summary(digests: dict[str, OwnerDigest]) -> str:
    lines = ["[Negotium] 업무 리마인더"]
    for owner_id, digest in digests.items():
        if digest.empty:
            continue
        label = digest.owner_name or owner_id or "미배정"
        parts: list[str] = []
        if digest.overdue:
            parts.append(f"마감 초과 {len(digest.overdue)}건")
        if digest.due_today:
            parts.append(f"오늘 마감 {len(digest.due_today)}건")
        if digest.stale:
            parts.append(f"정체 {len(digest.stale)}건")
        lines.append(f"- {label}: {', '.join(parts)}")
    return "\n".join(lines)


def _classify_work_items(
    rows: list[dict[str, Any]], *, today: date, stale_days: int
) -> dict[str, OwnerDigest]:
    """Group open work items per owner into overdue / due-today / stale lists."""
    stale_cutoff = today - timedelta(days=stale_days)
    digests: dict[str, OwnerDigest] = {}
    for row in rows:
        status = str(row.get("status") or "")
        if status in {"done", "cancelled"}:
            continue
        owner_id = str(row.get("owner_id") or "")
        digest = digests.setdefault(
            owner_id, OwnerDigest(owner_name=str(row.get("owner_name") or ""))
        )
        title = str(row.get("title") or "(제목 없음)")
        due = _parse_date(str(row.get("due_date") or ""))
        if due is not None:
            if due < today:
                digest.overdue.append(title)
                continue
            if due == today:
                digest.due_today.append(title)
                continue
        if status in {"todo", "in_progress"}:
            updated = _parse_datetime(str(row.get("updated_at") or ""))
            if updated is not None and updated.date() < stale_cutoff:
                digest.stale.append(title)
    return digests


def _weekly_slot_key(moment: datetime) -> str:
    iso = moment.isocalendar()
    return f"{iso.year}-W{iso.week:02d}"


def _is_weekly_due(config: WeeklyReportConfig, state: AutomationState, now_local: datetime) -> bool:
    if state.last_weekly_run_key == _weekly_slot_key(now_local):
        return False
    slot_hour, slot_minute = _parse_hhmm(config.time)
    days_since_slot_day = (now_local.weekday() - config.weekday) % 7
    slot_date = now_local.date() - timedelta(days=days_since_slot_day)
    slot = datetime(
        slot_date.year,
        slot_date.month,
        slot_date.day,
        slot_hour,
        slot_minute,
        tzinfo=now_local.tzinfo,
    )
    # The slot must be in the current ISO week: a fully missed week is skipped
    # rather than fired retroactively.
    if _weekly_slot_key(slot) != _weekly_slot_key(now_local):
        return False
    return now_local >= slot


def _is_reminder_due(config: ReminderConfig, state: AutomationState, now_local: datetime) -> bool:
    if state.last_reminder_date == now_local.date().isoformat():
        return False
    hour, minute = _parse_hhmm(config.time)
    return (now_local.hour, now_local.minute) >= (hour, minute)


def _parse_hhmm(value: str) -> tuple[int, int]:
    try:
        hour_text, minute_text = value.split(":", 1)
        return int(hour_text), int(minute_text)
    except (ValueError, AttributeError):
        return 9, 0


def _parse_date(value: str) -> date | None:
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def _parse_datetime(value: str) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed


def _audit_event(container: Container, *, action: str, details: dict[str, Any]) -> None:
    from negotium.app.api._shared import _audit

    _audit(
        container,
        actor=AUTOMATION_ACTOR,
        action=action,
        target="automation",
        details=details,
    )
