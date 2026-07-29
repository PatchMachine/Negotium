"""Automation service: slot math, idempotency, classification, webhook contract."""

from __future__ import annotations

from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any, ClassVar

import httpx
import pytest

from negotium.app.api import _shared
from negotium.app.container import Container
from negotium.app.services import automation_service
from negotium.app.services.automation_service import (
    _classify_work_items,
    deliver_webhook,
    run_due_jobs,
    run_jobs,
)
from negotium.app.settings import Settings
from negotium.archive.automation import (
    AutomationConfig,
    ReminderConfig,
    WeeklyReportConfig,
)
from negotium.archive.work_memory import WorkScheduleItem

# 2026-07-27 is a Monday. KST = UTC+9.
_MONDAY_0930_KST = datetime(2026, 7, 27, 0, 30, tzinfo=UTC)
_MONDAY_0859_KST = datetime(2026, 7, 26, 23, 59, tzinfo=UTC)
_WEDNESDAY_KST = datetime(2026, 7, 29, 3, 0, tzinfo=UTC)


def _container(tmp_path: Path) -> Container:
    return Container.build(
        Settings(
            env="test", archive_dir=tmp_path / "archive", workspace_dir=tmp_path / "workspaces"
        )
    )


def _enable_weekly(container: Container, *, weekday: int = 0, time: str = "09:00") -> None:
    container.automation.write_config(
        AutomationConfig(
            weekly_report=WeeklyReportConfig(enabled=True, weekday=weekday, time=time),
        )
    )


class _FakeReport:
    title = "주간 업무 보고"
    path = "documents/20260727_weekly.md"


@pytest.fixture()
def fake_weekly(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    calls: list[str] = []

    async def fake(container: Any, *, actor: str) -> _FakeReport:
        calls.append(actor)
        return _FakeReport()

    monkeypatch.setattr(_shared, "_generate_weekly_report", fake)
    return calls


async def test_weekly_fires_once_per_slot(tmp_path: Path, fake_weekly: list[str]) -> None:
    container = _container(tmp_path)
    _enable_weekly(container)

    first = await run_due_jobs(container, now=_MONDAY_0930_KST)
    second = await run_due_jobs(container, now=_MONDAY_0930_KST)

    assert first == ["weekly_report"]
    assert second == []
    assert fake_weekly == ["automation"]
    notes = container.notifications.list_for("anyone")
    assert notes and notes[0]["kind"] == "weekly_report"


async def test_weekly_not_due_before_slot_time(tmp_path: Path, fake_weekly: list[str]) -> None:
    container = _container(tmp_path)
    _enable_weekly(container)
    assert await run_due_jobs(container, now=_MONDAY_0859_KST) == []
    assert fake_weekly == []


async def test_weekly_fires_late_in_the_same_week(tmp_path: Path, fake_weekly: list[str]) -> None:
    """Server down through Monday: the Wednesday tick still runs this week's slot."""
    container = _container(tmp_path)
    _enable_weekly(container)
    assert await run_due_jobs(container, now=_WEDNESDAY_KST) == ["weekly_report"]


async def test_weekly_slot_from_previous_iso_week_is_skipped(
    tmp_path: Path, fake_weekly: list[str]
) -> None:
    """Friday slot; on Wednesday the most recent Friday is last week — not due."""
    container = _container(tmp_path)
    _enable_weekly(container, weekday=4)
    assert await run_due_jobs(container, now=_WEDNESDAY_KST) == []


async def test_disabled_jobs_never_fire(tmp_path: Path, fake_weekly: list[str]) -> None:
    container = _container(tmp_path)
    assert await run_due_jobs(container, now=_MONDAY_0930_KST) == []
    assert fake_weekly == []


async def test_weekly_failure_marks_slot_and_does_not_retry(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    container = _container(tmp_path)
    _enable_weekly(container)
    attempts: list[int] = []

    async def failing(container: Any, *, actor: str) -> _FakeReport:
        attempts.append(1)
        raise RuntimeError("llm down")

    monkeypatch.setattr(_shared, "_generate_weekly_report", failing)

    assert await run_due_jobs(container, now=_MONDAY_0930_KST) == []
    assert await run_due_jobs(container, now=_MONDAY_0930_KST) == []
    assert len(attempts) == 1, "one attempt per slot even on failure"


async def test_reminders_fire_once_per_day(tmp_path: Path) -> None:
    container = _container(tmp_path)
    container.automation.write_config(
        AutomationConfig(reminders=ReminderConfig(enabled=True, time="09:00", stale_days=3))
    )
    container.work_schedule.upsert(
        WorkScheduleItem.create(
            title="지연 업무", owner_id="alice", owner_name="앨리스", due_date="2026-07-01"
        )
    )

    first = await run_due_jobs(container, now=_MONDAY_0930_KST)
    second = await run_due_jobs(container, now=_MONDAY_0930_KST)

    assert first == ["reminders"]
    assert second == []
    alice_notes = container.notifications.list_for("alice")
    assert any("마감 초과" in str(note["body"]) for note in alice_notes)


def test_classification_matrix() -> None:
    today = date(2026, 7, 27)
    rows: list[dict[str, Any]] = [
        {"title": "지남", "owner_id": "a", "status": "todo", "due_date": "2026-07-20"},
        {"title": "오늘", "owner_id": "a", "status": "in_progress", "due_date": "2026-07-27"},
        {
            "title": "정체",
            "owner_id": "b",
            "status": "in_progress",
            "due_date": "",
            "updated_at": "2026-07-10T00:00:00+00:00",
        },
        {"title": "완료", "owner_id": "a", "status": "done", "due_date": "2026-07-01"},
        {"title": "취소", "owner_id": "a", "status": "cancelled", "due_date": "2026-07-01"},
        {"title": "깨진날짜", "owner_id": "a", "status": "todo", "due_date": "언젠가"},
        {
            "title": "신선",
            "owner_id": "b",
            "status": "todo",
            "updated_at": "2026-07-26T00:00:00+00:00",
        },
    ]
    digests = _classify_work_items(rows, today=today, stale_days=3)

    assert digests["a"].overdue == ["지남"]
    assert digests["a"].due_today == ["오늘"]
    assert digests["b"].stale == ["정체"]
    assert "완료" not in digests["a"].overdue
    assert all("깨진날짜" not in bucket for bucket in (digests["a"].overdue, digests["a"].stale))
    assert "신선" not in digests["b"].stale


class _FakeWebhookClient:
    posts: ClassVar[list[tuple[str, dict[str, Any]]]] = []
    fail: ClassVar[Exception | None] = None
    status_code: ClassVar[int] = 200

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        pass

    async def __aenter__(self) -> _FakeWebhookClient:
        return self

    async def __aexit__(self, *args: Any) -> None:
        return None

    async def post(self, url: str, **kwargs: Any) -> httpx.Response:
        if type(self).fail is not None:
            raise type(self).fail
        type(self).posts.append((url, kwargs["json"]))
        return httpx.Response(type(self).status_code, request=httpx.Request("POST", url))


@pytest.fixture()
def fake_webhook(monkeypatch: pytest.MonkeyPatch) -> type[_FakeWebhookClient]:
    _FakeWebhookClient.posts = []
    _FakeWebhookClient.fail = None
    _FakeWebhookClient.status_code = 200
    monkeypatch.setattr(httpx, "AsyncClient", _FakeWebhookClient)
    return _FakeWebhookClient


async def test_webhook_payload_shape(
    tmp_path: Path, fake_webhook: type[_FakeWebhookClient]
) -> None:
    container = _container(tmp_path)
    ok = await deliver_webhook(container, "https://hooks.example/x", "테스트 메시지")
    assert ok is True
    assert fake_webhook.posts == [("https://hooks.example/x", {"text": "테스트 메시지"})]


async def test_webhook_failure_never_raises(
    tmp_path: Path, fake_webhook: type[_FakeWebhookClient]
) -> None:
    container = _container(tmp_path)
    fake_webhook.fail = httpx.ConnectError("refused")
    assert await deliver_webhook(container, "https://hooks.example/x", "x") is False

    fake_webhook.fail = None
    fake_webhook.status_code = 500
    assert await deliver_webhook(container, "https://hooks.example/x", "x") is False


async def test_empty_webhook_url_is_a_noop(
    tmp_path: Path, fake_webhook: type[_FakeWebhookClient]
) -> None:
    container = _container(tmp_path)
    assert await deliver_webhook(container, "", "x") is True
    assert fake_webhook.posts == []


async def test_run_jobs_forces_execution_regardless_of_slot(
    tmp_path: Path, fake_weekly: list[str]
) -> None:
    container = _container(tmp_path)
    _enable_weekly(container)
    executed = await run_jobs(container, ["weekly_report"], now=_MONDAY_0859_KST)
    assert executed == ["weekly_report"]
    assert automation_service is not None  # keep the module import referenced
