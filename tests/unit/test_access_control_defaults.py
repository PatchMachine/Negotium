from __future__ import annotations

import json
from pathlib import Path

from patch_machine.archive.access_control import ALL_PERMISSIONS, AccessControlStore


def test_admin_permissions_include_local_mcp_and_hr_controls() -> None:
    assert "admin:local_llm" in ALL_PERMISSIONS
    assert "admin:hr_evaluation" in ALL_PERMISSIONS
    assert "admin:mcp" in ALL_PERMISSIONS


def test_existing_owner_role_user_suppresses_synthetic_local_owner(tmp_path: Path) -> None:
    path = tmp_path / "access_control.json"
    path.write_text(
        json.dumps(
            {
                "roles": [
                    {"id": "owner", "name": "대표/관리자", "level": 100, "permissions": ["*"]},
                    {"id": "viewer", "name": "조회자", "level": 10, "permissions": ["work:read"]},
                ],
                "users": [
                    {
                        "id": "ceo",
                        "display_name": "대표 계정",
                        "title": "대표",
                        "role_id": "owner",
                        "active": True,
                    },
                ],
            },
        ),
        encoding="utf-8",
    )

    payload = AccessControlStore(tmp_path).read()
    user_ids = [str(user["id"]) for user in payload["users"]]
    display_names = [str(user["display_name"]) for user in payload["users"]]

    assert "ceo" in user_ids
    assert "owner" not in user_ids
    assert "Local Owner" not in display_names


def test_fresh_store_has_no_default_owner_account(tmp_path: Path) -> None:
    # No phantom owner account is fabricated; only the initial setup designer
    # should exist as administrator.
    payload = AccessControlStore(tmp_path).read()
    assert payload["users"] == []


def test_persisted_local_owner_is_normalized(tmp_path: Path) -> None:
    path = tmp_path / "access_control.json"
    path.write_text(
        json.dumps(
            {
                "roles": [
                    {"id": "owner", "name": "대표/관리자", "level": 100, "permissions": ["*"]}
                ],
                "users": [
                    {
                        "id": "owner",
                        "display_name": "Local Owner",
                        "title": "대표",
                        "role_id": "owner",
                        "active": True,
                    },
                ],
            },
        ),
        encoding="utf-8",
    )

    payload = AccessControlStore(tmp_path).read()
    owner = next(user for user in payload["users"] if user["id"] == "owner")
    assert owner["display_name"] == "시스템 관리자"
    assert owner["title"] == "시스템 관리자"
