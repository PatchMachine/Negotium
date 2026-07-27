"""Organisation and personnel reads.

Lives in ``app/services`` rather than ``app/api/_shared`` so the MCP tool
dispatcher can use it without importing the HTTP layer — that direction would
be a layering inversion and risks an import cycle. ``_shared`` re-exports
``render_org_roster_markdown`` under its old name so existing prompt callers are
unchanged.
"""

from __future__ import annotations

from typing import Any


def _as_int(value: Any, default: int = 0) -> int:
    try:
        return int(float(str(value)))
    except (TypeError, ValueError):
        return default


def render_org_roster_markdown(container: Any) -> str:
    """Korean markdown rendering of departments, positions and active staff."""

    acl = container.access_control.read()
    users = acl.get("users", [])
    departments = acl.get("departments", [])
    roles_by_id = {
        str(role.get("id")): str(role.get("name") or role.get("id"))
        for role in acl.get("roles", [])
    }
    positions = acl.get("positions", [])
    positions_by_id = {
        str(position.get("id")): str(position.get("name") or position.get("id"))
        for position in positions
    }
    lines: list[str] = []
    if departments:
        children_by_parent: dict[str, list[dict[str, Any]]] = {}
        dept_ids = {str(dept.get("id")) for dept in departments}
        for dept in departments:
            parent_id = str(dept.get("parent_id") or "")
            # Treat references to missing parents as roots.
            key = parent_id if parent_id in dept_ids else ""
            children_by_parent.setdefault(key, []).append(dept)

        def _render(dept: dict[str, Any], depth: int) -> None:
            dept_id = str(dept.get("id"))
            members = [
                str(user.get("display_name") or user.get("id"))
                for user in users
                if str(user.get("department") or "") == dept_id
            ]
            lead_id = str(dept.get("lead_user_id") or "")
            lead = next(
                (
                    str(user.get("display_name") or user.get("id"))
                    for user in users
                    if str(user.get("id")) == lead_id
                ),
                "",
            )
            member_text = ", ".join(members) if members else "구성원 미지정"
            lead_text = f" · 리드 {lead}" if lead else ""
            indent = "  " * depth
            lines.append(f"{indent}- {dept.get('name')}{lead_text}: {member_text}")
            for child in children_by_parent.get(dept_id, []):
                _render(child, depth + 1)

        lines.append("부서(조직도):")
        for root in children_by_parent.get("", []):
            _render(root, 0)
    else:
        lines.append("부서: 등록된 부서 없음")
    if positions:
        ordered = sorted(positions, key=lambda item: _as_int(item.get("level")), reverse=True)
        lines.append("직급:")
        for position in ordered:
            lines.append(f"- {position.get('name')} (level {_as_int(position.get('level'))})")
    active_users = [user for user in users if user.get("active", True)]
    lines.append("사원:")
    if active_users:
        for user in active_users:
            dept_id = str(user.get("department") or "")
            dept_name = next(
                (str(dept.get("name")) for dept in departments if str(dept.get("id")) == dept_id),
                "부서 미배정",
            )
            role_name = roles_by_id.get(
                str(user.get("role_id") or ""), str(user.get("role_id") or "")
            )
            position_name = positions_by_id.get(str(user.get("position_id") or ""), "")
            position_text = f" · 직급 {position_name}" if position_name else ""
            title = str(user.get("title") or "")
            title_text = f" ({title})" if title else ""
            lines.append(
                f"- {user.get('display_name')}{title_text} · {dept_name}"
                f"{position_text} · 권한 {role_name}"
            )
    else:
        lines.append("- 등록된 사원 없음")
    return "\n".join(lines)


def _decorate_user(
    user: dict[str, Any],
    *,
    departments_by_id: dict[str, str],
    positions_by_id: dict[str, str],
    roles_by_id: dict[str, str],
) -> dict[str, Any]:
    return {
        "id": str(user.get("id") or ""),
        "display_name": str(user.get("display_name") or ""),
        "title": str(user.get("title") or ""),
        "department": departments_by_id.get(str(user.get("department") or ""), ""),
        "department_id": str(user.get("department") or ""),
        "position": positions_by_id.get(str(user.get("position_id") or ""), ""),
        "position_id": str(user.get("position_id") or ""),
        "role": roles_by_id.get(str(user.get("role_id") or ""), str(user.get("role_id") or "")),
        "active": bool(user.get("active", True)),
    }


def roster_json(
    container: Any, *, department: str = "", include_inactive: bool = False
) -> dict[str, Any]:
    """Structured roster for tool consumption."""

    acl = container.access_control.read()
    departments = acl.get("departments", [])
    positions = acl.get("positions", [])
    departments_by_id = {str(item.get("id")): str(item.get("name") or "") for item in departments}
    positions_by_id = {str(item.get("id")): str(item.get("name") or "") for item in positions}
    roles_by_id = {
        str(item.get("id")): str(item.get("name") or item.get("id"))
        for item in acl.get("roles", [])
    }

    wanted = department.strip().lower()
    users: list[dict[str, Any]] = []
    for user in acl.get("users", []):
        if not include_inactive and not user.get("active", True):
            continue
        decorated = _decorate_user(
            user,
            departments_by_id=departments_by_id,
            positions_by_id=positions_by_id,
            roles_by_id=roles_by_id,
        )
        if wanted and wanted not in {
            decorated["department"].lower(),
            decorated["department_id"].lower(),
        }:
            continue
        users.append(decorated)

    return {
        "users": users,
        "departments": [
            {
                "id": str(item.get("id") or ""),
                "name": str(item.get("name") or ""),
                "parent_id": str(item.get("parent_id") or ""),
                "lead_user_id": str(item.get("lead_user_id") or ""),
            }
            for item in departments
        ],
        "positions": [
            {
                "id": str(item.get("id") or ""),
                "name": str(item.get("name") or ""),
                "level": _as_int(item.get("level")),
            }
            for item in sorted(positions, key=lambda item: _as_int(item.get("level")), reverse=True)
        ],
        "total_users": len(users),
    }


def find_people(
    container: Any,
    query: str,
    *,
    department: str = "",
    position: str = "",
    limit: int = 20,
) -> dict[str, Any]:
    """Substring search over name/title/department/position."""

    roster = roster_json(container, department=department, include_inactive=False)
    needle = query.strip().lower()
    position_filter = position.strip().lower()
    matches = []
    for user in roster["users"]:
        if position_filter and position_filter != user["position"].lower():
            continue
        haystack = " ".join(
            [user["display_name"], user["title"], user["department"], user["position"]]
        ).lower()
        if not needle or needle in haystack:
            matches.append(user)
    return {"query": query, "matches": matches[: max(1, limit)], "total": len(matches)}
