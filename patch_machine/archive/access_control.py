"""Local user, title and permission registry."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import portalocker

ALL_PERMISSIONS = [
    "admin:api_keys",
    "admin:users",
    "admin:local_llm",
    "admin:hr_evaluation",
    "admin:mcp",
    "admin:integrations",
    "admin:token_limits",
    "memory:write",
    "llm:chat",
    "documents:write",
    "documents:read",
    "uploads:write",
    "work:read",
    "patch_records:read",
    "patch_records:write",
]


@dataclass(frozen=True)
class RoleRecord:
    id: str
    name: str
    level: int
    permissions: list[str] = field(default_factory=list)

    @classmethod
    def from_mapping(cls, payload: dict[str, Any]) -> RoleRecord:
        return cls(
            id=str(payload.get("id") or ""),
            name=str(payload.get("name") or ""),
            level=int(payload.get("level") or 0),
            permissions=[str(p) for p in payload.get("permissions", [])],
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "id": self.id,
            "name": self.name,
            "level": self.level,
            "permissions": self.permissions,
        }


@dataclass(frozen=True)
class UserRecord:
    id: str
    display_name: str
    title: str
    role_id: str
    active: bool = True

    @classmethod
    def from_mapping(cls, payload: dict[str, Any]) -> UserRecord:
        return cls(
            id=str(payload.get("id") or ""),
            display_name=str(payload.get("display_name") or ""),
            title=str(payload.get("title") or ""),
            role_id=str(payload.get("role_id") or "viewer"),
            active=bool(payload.get("active", True)),
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "id": self.id,
            "display_name": self.display_name,
            "title": self.title,
            "role_id": self.role_id,
            "active": self.active,
        }


class AccessControlStore:
    def __init__(self, archive_dir: Path) -> None:
        self._path = archive_dir / "access_control.json"

    def read(self) -> dict[str, list[dict[str, object]]]:
        payload = self._read_payload()
        return {
            "roles": [role.to_dict() for role in payload["roles"]],
            "users": [user.to_dict() for user in payload["users"]],
        }

    def upsert_role(self, role: RoleRecord) -> None:
        payload = self._read_payload()
        roles = [existing for existing in payload["roles"] if existing.id != role.id]
        roles.append(role)
        payload["roles"] = roles
        self._write_payload(payload)

    def delete_role(self, role_id: str) -> None:
        payload = self._read_payload()
        if role_id in {"owner", "manager", "staff", "viewer"}:
            raise ValueError("default roles cannot be deleted")
        payload["roles"] = [role for role in payload["roles"] if role.id != role_id]
        self._write_payload(payload)

    def upsert_user(self, user: UserRecord) -> None:
        payload = self._read_payload()
        users = [existing for existing in payload["users"] if existing.id != user.id]
        users.append(user)
        payload["users"] = users
        self._write_payload(payload)

    def delete_user(self, user_id: str) -> None:
        payload = self._read_payload()
        payload["users"] = [user for user in payload["users"] if user.id != user_id]
        self._write_payload(payload)

    def has_permission(self, user_id: str | None, permission: str) -> bool:
        payload = self._read_payload()
        user = self._resolve_user(payload, user_id)
        if user is None or not user.active:
            return False
        role = next((role for role in payload["roles"] if role.id == user.role_id), None)
        if role is None:
            return False
        return "*" in role.permissions or permission in role.permissions

    def _read_payload(self) -> dict[str, list[RoleRecord] | list[UserRecord]]:
        if not self._path.exists():
            return _default_payload()
        raw = json.loads(self._path.read_text(encoding="utf-8"))
        roles = [RoleRecord.from_mapping(item) for item in raw.get("roles", [])]
        users = [_normalize_user(UserRecord.from_mapping(item)) for item in raw.get("users", [])]
        if not roles:
            return _default_payload()
        default_payload = _default_payload()
        default_roles = default_payload["roles"]
        assert all(isinstance(role, RoleRecord) for role in default_roles)
        for default_role in default_roles:
            if all(role.id != default_role.id for role in roles):
                roles.append(default_role)
        has_owner_role_user = any(user.role_id == "owner" for user in users)
        if not has_owner_role_user and all(user.id != "owner" for user in users):
            default_users = default_payload["users"]
            assert all(isinstance(user, UserRecord) for user in default_users)
            owner = next(user for user in default_users if user.id == "owner")
            users.append(owner)
        return {"roles": roles, "users": users}

    def _write_payload(self, payload: dict[str, list[RoleRecord] | list[UserRecord]]) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        rendered = {
            "roles": [role.to_dict() for role in payload["roles"]],  # type: ignore[union-attr]
            "users": [user.to_dict() for user in payload["users"]],  # type: ignore[union-attr]
        }
        with portalocker.Lock(self._path, "w", encoding="utf-8", timeout=5) as fh:
            json.dump(rendered, fh, ensure_ascii=False, indent=2)
            fh.write("\n")

    @staticmethod
    def _resolve_user(
        payload: dict[str, list[RoleRecord] | list[UserRecord]],
        user_id: str | None,
    ) -> UserRecord | None:
        users = payload["users"]
        assert all(isinstance(user, UserRecord) for user in users)
        if user_id:
            return next((user for user in users if user.id == user_id), None)
        return None


def _default_payload() -> dict[str, list[RoleRecord] | list[UserRecord]]:
    return {
        "roles": [
            RoleRecord(id="owner", name="대표/관리자", level=100, permissions=["*"]),
            RoleRecord(
                id="manager",
                name="매니저",
                level=70,
                permissions=[
                    "memory:write",
                    "llm:chat",
                    "documents:write",
                    "documents:read",
                    "uploads:write",
                    "work:read",
                    "patch_records:read",
                    "patch_records:write",
                ],
            ),
            RoleRecord(
                id="staff",
                name="직원",
                level=40,
                permissions=[
                    "llm:chat",
                    "uploads:write",
                    "work:read",
                    "documents:read",
                    "patch_records:read",
                ],
            ),
            RoleRecord(
                id="viewer",
                name="조회자",
                level=10,
                permissions=["work:read", "documents:read", "patch_records:read"],
            ),
        ],
        "users": [
            UserRecord(id="owner", display_name="시스템 관리자", title="대표", role_id="owner"),
        ],
    }


def _normalize_user(user: UserRecord) -> UserRecord:
    if user.id == "owner" and user.display_name == "Local Owner":
        return UserRecord(
            id=user.id,
            display_name="시스템 관리자",
            title="시스템 관리자",
            role_id=user.role_id,
            active=user.active,
        )
    return user
