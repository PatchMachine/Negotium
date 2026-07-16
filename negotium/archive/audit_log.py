"""Append-only audit log for administrative and state-changing actions."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

import portalocker


@dataclass(frozen=True)
class AuditRecord:
    id: str
    actor: str
    action: str
    target: str
    target_id: str
    timestamp: str
    details: dict[str, object]

    @classmethod
    def create(
        cls,
        *,
        actor: str,
        action: str,
        target: str,
        target_id: str = "",
        details: dict[str, object] | None = None,
    ) -> AuditRecord:
        return cls(
            id=str(uuid4()),
            actor=actor or "anonymous",
            action=action,
            target=target,
            target_id=target_id,
            timestamp=datetime.now(UTC).isoformat(),
            details=details or {},
        )

    @classmethod
    def from_mapping(cls, payload: dict[str, Any]) -> AuditRecord:
        details = payload.get("details") if isinstance(payload.get("details"), dict) else {}
        return cls(
            id=str(payload.get("id") or ""),
            actor=str(payload.get("actor") or "anonymous"),
            action=str(payload.get("action") or ""),
            target=str(payload.get("target") or ""),
            target_id=str(payload.get("target_id") or ""),
            timestamp=str(payload.get("timestamp") or ""),
            details={str(key): value for key, value in details.items()},
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "id": self.id,
            "actor": self.actor,
            "action": self.action,
            "target": self.target,
            "target_id": self.target_id,
            "timestamp": self.timestamp,
            "details": self.details,
        }


class AuditLogStore:
    def __init__(self, archive_dir: Path) -> None:
        self._path = archive_dir / "audit_log.jsonl"

    @property
    def path(self) -> Path:
        return self._path

    def record(
        self,
        *,
        actor: str,
        action: str,
        target: str,
        target_id: str = "",
        details: dict[str, object] | None = None,
    ) -> AuditRecord:
        record = AuditRecord.create(
            actor=actor,
            action=action,
            target=target,
            target_id=target_id,
            details=details,
        )
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with portalocker.Lock(self._path, "a", encoding="utf-8", timeout=5) as fh:
            fh.write(json.dumps(record.to_dict(), ensure_ascii=False, sort_keys=True))
            fh.write("\n")
        return record

    def list_recent(self, *, limit: int = 100) -> list[dict[str, object]]:
        if not self._path.exists():
            return []
        records: list[AuditRecord] = []
        for line in self._path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(payload, dict):
                records.append(AuditRecord.from_mapping(payload))
        return [record.to_dict() for record in records[-limit:]][::-1]
