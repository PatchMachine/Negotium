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

AclPayload = dict[str, list[Any]]


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
    department: str = ""
    position_id: str = ""

    @classmethod
    def from_mapping(cls, payload: dict[str, Any]) -> UserRecord:
        return cls(
            id=str(payload.get("id") or ""),
            display_name=str(payload.get("display_name") or ""),
            title=str(payload.get("title") or ""),
            role_id=str(payload.get("role_id") or "viewer"),
            active=bool(payload.get("active", True)),
            department=str(payload.get("department") or ""),
            position_id=str(payload.get("position_id") or ""),
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "id": self.id,
            "display_name": self.display_name,
            "title": self.title,
            "role_id": self.role_id,
            "active": self.active,
            "department": self.department,
            "position_id": self.position_id,
        }


@dataclass(frozen=True)
class DepartmentRecord:
    id: str
    name: str
    description: str = ""
    lead_user_id: str = ""
    parent_id: str = ""

    @classmethod
    def from_mapping(cls, payload: dict[str, Any]) -> DepartmentRecord:
        return cls(
            id=str(payload.get("id") or ""),
            name=str(payload.get("name") or ""),
            description=str(payload.get("description") or ""),
            lead_user_id=str(payload.get("lead_user_id") or ""),
            parent_id=str(payload.get("parent_id") or ""),
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "lead_user_id": self.lead_user_id,
            "parent_id": self.parent_id,
        }


@dataclass(frozen=True)
class PositionRecord:
    id: str
    name: str
    level: int = 0
    description: str = ""

    @classmethod
    def from_mapping(cls, payload: dict[str, Any]) -> PositionRecord:
        return cls(
            id=str(payload.get("id") or ""),
            name=str(payload.get("name") or ""),
            level=int(payload.get("level") or 0),
            description=str(payload.get("description") or ""),
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "id": self.id,
            "name": self.name,
            "level": self.level,
            "description": self.description,
        }


class AccessControlStore:
    def __init__(self, archive_dir: Path) -> None:
        self._path = archive_dir / "access_control.json"

    def read(self) -> dict[str, list[dict[str, object]]]:
        payload = self._read_payload()
        roles = payload["roles"]
        users = payload["users"]
        departments = payload["departments"]
        positions = payload["positions"]
        return {
            "roles": [role.to_dict() for role in roles if isinstance(role, RoleRecord)],
            "users": [user.to_dict() for user in users if isinstance(user, UserRecord)],
            "departments": [
                dept.to_dict() for dept in departments if isinstance(dept, DepartmentRecord)
            ],
            "positions": [
                position.to_dict()
                for position in positions
                if isinstance(position, PositionRecord)
            ],
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

    def upsert_department(self, department: DepartmentRecord) -> None:
        if not department.id.strip():
            raise ValueError("department id is required")
        payload = self._read_payload()
        existing_departments = [
            existing
            for existing in payload["departments"]
            if isinstance(existing, DepartmentRecord)
        ]
        if department.parent_id:
            if department.parent_id == department.id:
                raise ValueError("department cannot be its own parent")
            others = {dept.id: dept for dept in existing_departments if dept.id != department.id}
            if department.parent_id not in others:
                raise ValueError("parent department does not exist")
            # Walk up the parent chain to ensure no cycle is introduced.
            visited: set[str] = {department.id}
            cursor = department.parent_id
            while cursor:
                if cursor in visited:
                    raise ValueError("department hierarchy cannot contain a cycle")
                visited.add(cursor)
                parent = others.get(cursor)
                cursor = parent.parent_id if parent else ""
        departments = [dept for dept in existing_departments if dept.id != department.id]
        departments.append(department)
        payload["departments"] = departments
        self._write_payload(payload)

    def delete_department(self, department_id: str) -> None:
        payload = self._read_payload()
        remaining: list[DepartmentRecord] = []
        for dept in payload["departments"]:
            if not isinstance(dept, DepartmentRecord) or dept.id == department_id:
                continue
            if dept.parent_id == department_id:
                # Re-parent orphaned children to the deleted node's parent (or root).
                remaining.append(_replace_parent(dept, ""))
            else:
                remaining.append(dept)
        payload["departments"] = remaining
        self._write_payload(payload)

    def upsert_position(self, position: PositionRecord) -> None:
        if not position.id.strip():
            raise ValueError("position id is required")
        payload = self._read_payload()
        positions = [
            existing
            for existing in payload["positions"]
            if isinstance(existing, PositionRecord) and existing.id != position.id
        ]
        positions.append(position)
        payload["positions"] = positions
        self._write_payload(payload)

    def delete_position(self, position_id: str) -> None:
        payload = self._read_payload()
        payload["positions"] = [
            position
            for position in payload["positions"]
            if isinstance(position, PositionRecord) and position.id != position_id
        ]
        self._write_payload(payload)

    def has_permission(self, user_id: str | None, permission: str) -> bool:
        payload = self._read_payload()
        user = self._resolve_user(payload, user_id)
        if user is None or not user.active:
            return False
        roles = [role for role in payload["roles"] if isinstance(role, RoleRecord)]
        role = next((role for role in roles if role.id == user.role_id), None)
        if role is None:
            return False
        return "*" in role.permissions or permission in role.permissions

    def _read_payload(self) -> AclPayload:
        if not self._path.exists():
            return _default_payload()
        raw = json.loads(self._path.read_text(encoding="utf-8"))
        roles: list[RoleRecord] = [RoleRecord.from_mapping(item) for item in raw.get("roles", [])]
        users: list[UserRecord] = [
            _normalize_user(UserRecord.from_mapping(item)) for item in raw.get("users", [])
        ]
        departments: list[DepartmentRecord] = [
            DepartmentRecord.from_mapping(item) for item in raw.get("departments", [])
        ]
        positions: list[PositionRecord] = [
            PositionRecord.from_mapping(item) for item in raw.get("positions", [])
        ]
        if not roles:
            return _default_payload()
        default_payload = _default_payload()
        for default_role in default_payload["roles"]:
            if isinstance(default_role, RoleRecord) and all(role.id != default_role.id for role in roles):
                roles.append(default_role)
        # Lockout recovery only: if no active admin remains, restore the owner role
        # on an existing "owner" user. We intentionally do NOT fabricate a default
        # owner account — only the initial setup designer exists as administrator.
        if not _has_active_admin_user(users, roles):
            users = [
                _restore_default_owner(user) if user.id == "owner" else user
                for user in users
            ]
        return {
            "roles": roles,
            "users": users,
            "departments": departments,
            "positions": positions,
        }

    def _write_payload(self, payload: AclPayload) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        rendered = {
            "roles": [role.to_dict() for role in payload["roles"] if isinstance(role, RoleRecord)],
            "users": [user.to_dict() for user in payload["users"] if isinstance(user, UserRecord)],
            "departments": [
                dept.to_dict()
                for dept in payload["departments"]
                if isinstance(dept, DepartmentRecord)
            ],
            "positions": [
                position.to_dict()
                for position in payload.get("positions", [])
                if isinstance(position, PositionRecord)
            ],
        }
        with portalocker.Lock(self._path, "w", encoding="utf-8", timeout=5) as fh:
            json.dump(rendered, fh, ensure_ascii=False, indent=2)
            fh.write("\n")

    @staticmethod
    def _resolve_user(
        payload: AclPayload,
        user_id: str | None,
    ) -> UserRecord | None:
        users = [user for user in payload["users"] if isinstance(user, UserRecord)]
        if user_id:
            return next((user for user in users if user.id == user_id), None)
        return None


def _default_payload() -> AclPayload:
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
        "users": [],
        "departments": [],
        "positions": [],
    }


def _replace_parent(department: DepartmentRecord, parent_id: str) -> DepartmentRecord:
    return DepartmentRecord(
        id=department.id,
        name=department.name,
        description=department.description,
        lead_user_id=department.lead_user_id,
        parent_id=parent_id,
    )


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


def _restore_default_owner(user: UserRecord) -> UserRecord:
    return UserRecord(
        id=user.id,
        display_name=user.display_name or "시스템 관리자",
        title=user.title or "대표",
        role_id="owner",
        active=True,
        department=user.department,
        position_id=user.position_id,
    )


def _has_active_admin_user(users: list[UserRecord], roles: list[RoleRecord]) -> bool:
    admin_role_ids = {
        role.id for role in roles if "*" in role.permissions or "admin:users" in role.permissions
    }
    return any(user.active and user.role_id in admin_role_ids for user in users)
