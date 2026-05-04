"""Current work memory and worker scheduling stores."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal
from uuid import uuid4

import portalocker

WorkStatus = Literal["todo", "in_progress", "blocked", "done", "cancelled"]
WorkPriority = Literal["low", "normal", "high", "urgent"]


@dataclass(frozen=True)
class WorkMemory:
    goals: str = ""
    active_projects: str = ""
    current_focus: str = ""
    blockers: str = ""
    decisions: str = ""
    risks: str = ""
    next_actions: str = ""
    updated_at: str = ""

    @classmethod
    def from_mapping(cls, payload: dict[str, Any]) -> WorkMemory:
        return cls(
            goals=str(payload.get("goals") or ""),
            active_projects=str(payload.get("active_projects") or ""),
            current_focus=str(payload.get("current_focus") or ""),
            blockers=str(payload.get("blockers") or ""),
            decisions=str(payload.get("decisions") or ""),
            risks=str(payload.get("risks") or ""),
            next_actions=str(payload.get("next_actions") or ""),
            updated_at=str(payload.get("updated_at") or ""),
        )

    def to_dict(self) -> dict[str, str]:
        return {
            "goals": self.goals,
            "active_projects": self.active_projects,
            "current_focus": self.current_focus,
            "blockers": self.blockers,
            "decisions": self.decisions,
            "risks": self.risks,
            "next_actions": self.next_actions,
            "updated_at": self.updated_at,
        }

    def to_markdown(self) -> str:
        return "\n".join(
            [
                "## 현재 작업 메모리",
                f"- 목표: {self.goals or '(미설정)'}",
                f"- 진행 프로젝트: {self.active_projects or '(미설정)'}",
                f"- 현재 집중: {self.current_focus or '(미설정)'}",
                f"- 병목/블로커: {self.blockers or '(미설정)'}",
                f"- 결정사항: {self.decisions or '(미설정)'}",
                f"- 리스크: {self.risks or '(미설정)'}",
                f"- 다음 액션: {self.next_actions or '(미설정)'}",
            ]
        )


@dataclass(frozen=True)
class WorkScheduleItem:
    id: str
    title: str
    owner_id: str = ""
    owner_name: str = ""
    status: WorkStatus = "todo"
    priority: WorkPriority = "normal"
    start_date: str = ""
    due_date: str = ""
    dependencies: list[str] = field(default_factory=list)
    notes: str = ""
    source_architecture_id: str = ""
    created_at: str = ""
    updated_at: str = ""

    @classmethod
    def create(cls, **payload: Any) -> WorkScheduleItem:
        now = datetime.now(UTC).isoformat()
        return cls(
            id=str(payload.get("id") or uuid4()),
            title=str(payload.get("title") or "").strip(),
            owner_id=str(payload.get("owner_id") or "").strip(),
            owner_name=str(payload.get("owner_name") or "").strip(),
            status=_status(payload.get("status")),
            priority=_priority(payload.get("priority")),
            start_date=str(payload.get("start_date") or "").strip(),
            due_date=str(payload.get("due_date") or "").strip(),
            dependencies=[str(item).strip() for item in payload.get("dependencies", []) if str(item).strip()],
            notes=str(payload.get("notes") or "").strip(),
            source_architecture_id=str(payload.get("source_architecture_id") or "").strip(),
            created_at=str(payload.get("created_at") or now),
            updated_at=now,
        )

    @classmethod
    def from_mapping(cls, payload: dict[str, Any]) -> WorkScheduleItem:
        return cls.create(**payload)

    def to_dict(self) -> dict[str, object]:
        return {
            "id": self.id,
            "title": self.title,
            "owner_id": self.owner_id,
            "owner_name": self.owner_name,
            "status": self.status,
            "priority": self.priority,
            "start_date": self.start_date,
            "due_date": self.due_date,
            "dependencies": self.dependencies,
            "notes": self.notes,
            "source_architecture_id": self.source_architecture_id,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


class WorkMemoryStore:
    def __init__(self, archive_dir: Path) -> None:
        self._path = archive_dir / "work_memory.json"

    def read(self) -> WorkMemory:
        if not self._path.exists():
            return WorkMemory()
        raw = self._path.read_text(encoding="utf-8")
        if not raw.strip():
            return WorkMemory()
        payload = json.loads(raw)
        if not isinstance(payload, dict):
            raise ValueError("work memory must be a JSON object")
        return WorkMemory.from_mapping(payload)

    def write(self, memory: WorkMemory) -> WorkMemory:
        updated = WorkMemory(**{**memory.to_dict(), "updated_at": datetime.now(UTC).isoformat()})
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with portalocker.Lock(self._path, "w", encoding="utf-8", timeout=5) as fh:
            json.dump(updated.to_dict(), fh, ensure_ascii=False, indent=2)
            fh.write("\n")
        return updated


class WorkScheduleStore:
    def __init__(self, archive_dir: Path) -> None:
        self._path = archive_dir / "work_schedule.json"

    def list(self) -> list[dict[str, object]]:
        return [item.to_dict() for item in self._read_items()]

    def upsert(self, item: WorkScheduleItem) -> WorkScheduleItem:
        if not item.title:
            raise ValueError("schedule item title is required")
        items = [existing for existing in self._read_items() if existing.id != item.id]
        saved = WorkScheduleItem.create(**item.to_dict())
        items.append(saved)
        self._write_items(items)
        return saved

    def delete(self, item_id: str) -> bool:
        items = self._read_items()
        next_items = [item for item in items if item.id != item_id]
        self._write_items(next_items)
        return len(next_items) != len(items)

    def _read_items(self) -> list[WorkScheduleItem]:
        if not self._path.exists():
            return []
        raw = self._path.read_text(encoding="utf-8")
        if not raw.strip():
            return []
        payload = json.loads(raw)
        if not isinstance(payload, list):
            return []
        return [WorkScheduleItem.from_mapping(item) for item in payload if isinstance(item, dict)]

    def _write_items(self, items: list[WorkScheduleItem]) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with portalocker.Lock(self._path, "w", encoding="utf-8", timeout=5) as fh:
            json.dump([item.to_dict() for item in items], fh, ensure_ascii=False, indent=2)
            fh.write("\n")


def _status(value: object) -> WorkStatus:
    status = str(value or "todo")
    if status in {"todo", "in_progress", "blocked", "done", "cancelled"}:
        return status  # type: ignore[return-value]
    return "todo"


def _priority(value: object) -> WorkPriority:
    priority = str(value or "normal")
    if priority in {"low", "normal", "high", "urgent"}:
        return priority  # type: ignore[return-value]
    return "normal"
