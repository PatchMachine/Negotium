"""In-app notifications: per-user or broadcast, capped, file-backed."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal
from uuid import uuid4

from negotium.archive._store import read_json_file, write_json_file

NotificationKind = Literal["weekly_report", "reminder", "system"]

_KINDS: set[str] = {"weekly_report", "reminder", "system"}


def _kind(value: object) -> NotificationKind:
    text = str(value or "").strip()
    if text in _KINDS:
        return text  # type: ignore[return-value]
    return "system"


@dataclass(frozen=True)
class NotificationRecord:
    id: str
    user_id: str = ""  # "" => broadcast to everyone
    kind: NotificationKind = "system"
    title: str = ""
    body: str = ""
    link_path: str = ""
    created_at: str = ""
    read_by: list[str] = field(default_factory=list)

    @classmethod
    def create(cls, **payload: Any) -> NotificationRecord:
        now = datetime.now(UTC).isoformat()
        read_by_raw = payload.get("read_by", [])
        read_by = (
            [str(item) for item in read_by_raw if str(item).strip()]
            if isinstance(read_by_raw, list)
            else []
        )
        return cls(
            id=str(payload.get("id") or uuid4()),
            user_id=str(payload.get("user_id") or "").strip(),
            kind=_kind(payload.get("kind")),
            title=str(payload.get("title") or "").strip(),
            body=str(payload.get("body") or "").strip(),
            link_path=str(payload.get("link_path") or "").strip(),
            # Preserve stored timestamps/read state: records round-trip through
            # create() on every read.
            created_at=str(payload.get("created_at") or now),
            read_by=read_by,
        )

    @classmethod
    def from_mapping(cls, payload: dict[str, Any]) -> NotificationRecord:
        return cls.create(**payload)

    def to_dict(self) -> dict[str, object]:
        return {
            "id": self.id,
            "user_id": self.user_id,
            "kind": self.kind,
            "title": self.title,
            "body": self.body,
            "link_path": self.link_path,
            "created_at": self.created_at,
            "read_by": self.read_by,
        }


class NotificationStore:
    MAX_RECORDS = 500

    def __init__(self, archive_dir: Path) -> None:
        self._path = archive_dir / "notifications.json"

    def add(self, record: NotificationRecord) -> NotificationRecord:
        records = self._read_records()
        records.append(record)
        if len(records) > self.MAX_RECORDS:
            records.sort(key=lambda item: item.created_at)
            records = records[-self.MAX_RECORDS :]
        self._write_records(records)
        return record

    def list_for(self, user_id: str, *, limit: int = 50) -> list[dict[str, object]]:
        """The user's own notifications plus broadcasts, newest first."""
        visible = [
            record
            for record in self._read_records()
            if record.user_id == "" or record.user_id == user_id
        ]
        visible.sort(key=lambda item: item.created_at, reverse=True)
        return [record.to_dict() for record in visible[: max(1, limit)]]

    def mark_read(self, ids: list[str], user_id: str) -> int:
        wanted = {str(item) for item in ids if str(item).strip()}
        if not wanted or not user_id:
            return 0
        records = self._read_records()
        changed = 0
        updated: list[NotificationRecord] = []
        for record in records:
            if record.id in wanted and user_id not in record.read_by:
                updated.append(
                    NotificationRecord.create(
                        **{**record.to_dict(), "read_by": [*record.read_by, user_id]}
                    )
                )
                changed += 1
            else:
                updated.append(record)
        if changed:
            self._write_records(updated)
        return changed

    def _read_records(self) -> list[NotificationRecord]:
        payload: object = read_json_file(self._path, default=list)
        if not isinstance(payload, list):
            return []
        return [NotificationRecord.from_mapping(item) for item in payload if isinstance(item, dict)]

    def _write_records(self, records: list[NotificationRecord]) -> None:
        write_json_file(self._path, [record.to_dict() for record in records])
