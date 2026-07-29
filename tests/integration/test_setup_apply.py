"""Setup apply issues one-time logins for wizard-created users."""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from negotium.app.container import Container
from negotium.app.main import create_app
from negotium.app.settings import Settings
from negotium.archive.access_control import UserRecord


def _admin_headers(container: Container) -> dict[str, str]:
    container.auth_store.create_user(
        user_id="owner", display_name="Local Owner", password="password-1234"
    )
    container.access_control.upsert_user(
        UserRecord(id="owner", display_name="Local Owner", title="대표", role_id="owner")
    )
    token = container.auth_store.authenticate("owner", "password-1234")
    assert token is not None
    return {"X-NG-User": f"Bearer {token}"}


def _apply_payload() -> dict[str, object]:
    return {
        "users": [
            {"id": "kim.cs", "display_name": "김철수", "title": "과장", "role_id": "manager"},
            {"id": "lee.yh", "display_name": "이영희", "title": "사원", "role_id": "staff"},
            # The acting admin appears in wizard rosters too; their login
            # already exists and must not be touched.
            {"id": "owner", "display_name": "Local Owner", "title": "대표", "role_id": "owner"},
        ],
    }


def test_setup_apply_issues_logins_once(tmp_path: Path) -> None:
    container = Container.build(
        Settings(
            env="test", archive_dir=tmp_path / "archive", workspace_dir=tmp_path / "workspaces"
        )
    )
    headers = _admin_headers(container)
    app = create_app(container)

    with TestClient(app) as client:
        first = client.post("/api/setup/office/apply", headers=headers, json=_apply_payload())
        assert first.status_code == 200
        issued = first.json()["issued_credentials"]
        assert sorted(issued) == ["kim.cs", "lee.yh"], "existing admin must be skipped"

        # The issued passwords work immediately.
        login = client.post(
            "/api/auth/login", json={"user_id": "kim.cs", "password": issued["kim.cs"]}
        )
        assert login.status_code == 200

        # Re-applying must not rotate anyone's password.
        second = client.post("/api/setup/office/apply", headers=headers, json=_apply_payload())
        assert second.status_code == 200
        assert second.json()["issued_credentials"] == {}
        again = client.post(
            "/api/auth/login", json={"user_id": "kim.cs", "password": issued["kim.cs"]}
        )
        assert again.status_code == 200

    # Passwords must never land in the audit log.
    audit_text = (tmp_path / "archive" / "audit_log.jsonl").read_text(encoding="utf-8")
    assert issued["kim.cs"] not in audit_text
    assert issued["lee.yh"] not in audit_text


def test_setup_apply_can_skip_login_issuance(tmp_path: Path) -> None:
    container = Container.build(
        Settings(
            env="test", archive_dir=tmp_path / "archive", workspace_dir=tmp_path / "workspaces"
        )
    )
    headers = _admin_headers(container)
    app = create_app(container)

    payload = {**_apply_payload(), "create_logins": False}
    with TestClient(app) as client:
        response = client.post("/api/setup/office/apply", headers=headers, json=payload)

    assert response.status_code == 200
    assert response.json()["issued_credentials"] == {}
    assert container.auth_store.has_user("kim.cs") is False
