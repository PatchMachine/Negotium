"""Payload models for the automation and notification API."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from negotium.archive.automation import AutomationConfig


class WeeklyReportConfigPayload(BaseModel):
    enabled: bool = False
    weekday: int = Field(0, ge=0, le=6)
    time: str = Field("09:00", pattern=r"^\d{2}:\d{2}$")
    timezone: str = "Asia/Seoul"


class ReminderConfigPayload(BaseModel):
    enabled: bool = False
    time: str = Field("09:30", pattern=r"^\d{2}:\d{2}$")
    stale_days: int = Field(3, ge=1, le=90)


class SearchConfigPayload(BaseModel):
    embeddings_enabled: bool = False


class AutomationConfigPayload(BaseModel):
    weekly_report: WeeklyReportConfigPayload = Field(default_factory=WeeklyReportConfigPayload)
    reminders: ReminderConfigPayload = Field(default_factory=ReminderConfigPayload)
    search: SearchConfigPayload = Field(default_factory=SearchConfigPayload)
    webhook_url: str = ""

    def to_config(self) -> AutomationConfig:
        return AutomationConfig.from_mapping(self.model_dump())


class AutomationStatusPayload(BaseModel):
    config: AutomationConfigPayload
    state: dict[str, str] = Field(default_factory=dict)


class RunJobsPayload(BaseModel):
    jobs: list[str] = Field(default_factory=list)


class RunResultPayload(BaseModel):
    executed: list[str] = Field(default_factory=list)


class NotificationsPayload(BaseModel):
    items: list[dict[str, Any]] = Field(default_factory=list)
    unread: int = 0


class MarkReadPayload(BaseModel):
    ids: list[str] = Field(default_factory=list)
