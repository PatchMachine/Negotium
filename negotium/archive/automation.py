"""Automation config and scheduler state, persisted as one JSON document.

``archive/automation.json`` holds ``{"config": {...}, "state": {...}}``. The
config is what admins edit (schedules, webhook URL); the state records which
slots already ran so the scheduler stays idempotent across restarts.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from negotium.archive._store import read_json_file, write_json_file

DEFAULT_TIMEZONE = "Asia/Seoul"
_TIME_RE = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")


def _valid_time(value: object, default: str) -> str:
    text = str(value or "").strip()
    return text if _TIME_RE.fullmatch(text) else default


def _valid_timezone(value: object) -> str:
    text = str(value or "").strip() or DEFAULT_TIMEZONE
    try:
        ZoneInfo(text)
    except (KeyError, ValueError):
        return DEFAULT_TIMEZONE
    return text


@dataclass(frozen=True)
class WeeklyReportConfig:
    enabled: bool = False
    weekday: int = 0  # 0=Mon .. 6=Sun
    time: str = "09:00"
    timezone: str = DEFAULT_TIMEZONE

    @classmethod
    def from_mapping(cls, payload: dict[str, Any]) -> WeeklyReportConfig:
        try:
            weekday = int(payload.get("weekday", 0))
        except (TypeError, ValueError):
            weekday = 0
        return cls(
            enabled=bool(payload.get("enabled", False)),
            weekday=min(6, max(0, weekday)),
            time=_valid_time(payload.get("time"), "09:00"),
            timezone=_valid_timezone(payload.get("timezone")),
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "enabled": self.enabled,
            "weekday": self.weekday,
            "time": self.time,
            "timezone": self.timezone,
        }


@dataclass(frozen=True)
class ReminderConfig:
    enabled: bool = False
    time: str = "09:30"
    stale_days: int = 3

    @classmethod
    def from_mapping(cls, payload: dict[str, Any]) -> ReminderConfig:
        try:
            stale_days = int(payload.get("stale_days", 3))
        except (TypeError, ValueError):
            stale_days = 3
        return cls(
            enabled=bool(payload.get("enabled", False)),
            time=_valid_time(payload.get("time"), "09:30"),
            stale_days=max(1, stale_days),
        )

    def to_dict(self) -> dict[str, object]:
        return {"enabled": self.enabled, "time": self.time, "stale_days": self.stale_days}


@dataclass(frozen=True)
class SearchConfig:
    """Archive semantic search: chunks leave the machine only when enabled."""

    embeddings_enabled: bool = False

    @classmethod
    def from_mapping(cls, payload: dict[str, Any]) -> SearchConfig:
        return cls(embeddings_enabled=bool(payload.get("embeddings_enabled", False)))

    def to_dict(self) -> dict[str, object]:
        return {"embeddings_enabled": self.embeddings_enabled}


@dataclass(frozen=True)
class BackupConfig:
    """Nested-git archive backup; remote_url may embed a token — never log it."""

    enabled: bool = False
    interval_minutes: int = 30
    remote_url: str = ""

    @classmethod
    def from_mapping(cls, payload: dict[str, Any]) -> BackupConfig:
        try:
            interval = int(payload.get("interval_minutes", 30))
        except (TypeError, ValueError):
            interval = 30
        return cls(
            enabled=bool(payload.get("enabled", False)),
            interval_minutes=min(1440, max(5, interval)),
            remote_url=str(payload.get("remote_url") or "").strip(),
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "enabled": self.enabled,
            "interval_minutes": self.interval_minutes,
            "remote_url": self.remote_url,
        }


@dataclass(frozen=True)
class AutomationConfig:
    weekly_report: WeeklyReportConfig = field(default_factory=WeeklyReportConfig)
    reminders: ReminderConfig = field(default_factory=ReminderConfig)
    search: SearchConfig = field(default_factory=SearchConfig)
    backup: BackupConfig = field(default_factory=BackupConfig)
    webhook_url: str = ""

    @classmethod
    def from_mapping(cls, payload: dict[str, Any]) -> AutomationConfig:
        weekly = payload.get("weekly_report")
        reminders = payload.get("reminders")
        search = payload.get("search")
        backup = payload.get("backup")
        return cls(
            weekly_report=WeeklyReportConfig.from_mapping(
                weekly if isinstance(weekly, dict) else {}
            ),
            reminders=ReminderConfig.from_mapping(
                reminders if isinstance(reminders, dict) else {}
            ),
            search=SearchConfig.from_mapping(search if isinstance(search, dict) else {}),
            backup=BackupConfig.from_mapping(backup if isinstance(backup, dict) else {}),
            webhook_url=str(payload.get("webhook_url") or "").strip(),
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "weekly_report": self.weekly_report.to_dict(),
            "reminders": self.reminders.to_dict(),
            "search": self.search.to_dict(),
            "backup": self.backup.to_dict(),
            "webhook_url": self.webhook_url,
        }


@dataclass(frozen=True)
class AutomationState:
    last_weekly_run_key: str = ""  # ISO week key, e.g. "2026-W31"
    last_reminder_date: str = ""  # local date, "YYYY-MM-DD"
    last_backup_attempt: str = ""  # ISO timestamp

    @classmethod
    def from_mapping(cls, payload: dict[str, Any]) -> AutomationState:
        return cls(
            last_weekly_run_key=str(payload.get("last_weekly_run_key") or ""),
            last_reminder_date=str(payload.get("last_reminder_date") or ""),
            last_backup_attempt=str(payload.get("last_backup_attempt") or ""),
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "last_weekly_run_key": self.last_weekly_run_key,
            "last_reminder_date": self.last_reminder_date,
            "last_backup_attempt": self.last_backup_attempt,
        }


class AutomationStore:
    def __init__(self, archive_dir: Path) -> None:
        self._path = archive_dir / "automation.json"

    def read_config(self) -> AutomationConfig:
        return AutomationConfig.from_mapping(self._read_payload().get("config", {}))

    def write_config(self, config: AutomationConfig) -> AutomationConfig:
        payload = self._read_payload()
        payload["config"] = config.to_dict()
        write_json_file(self._path, payload)
        return config

    def read_state(self) -> AutomationState:
        return AutomationState.from_mapping(self._read_payload().get("state", {}))

    def write_state(self, state: AutomationState) -> AutomationState:
        payload = self._read_payload()
        payload["state"] = state.to_dict()
        write_json_file(self._path, payload)
        return state

    def _read_payload(self) -> dict[str, Any]:
        payload = read_json_file(self._path)
        return payload if isinstance(payload, dict) else {}
