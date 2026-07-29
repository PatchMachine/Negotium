"""Automation API: config roundtrip, permissions, manual run, notifications."""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from negotium.adapters.llm.fake_adapter import FakeLlmProvider, ScriptedResponse
from negotium.app.container import Container
from negotium.app.main import create_app
from negotium.app.settings import Settings
from negotium.archive.access_control import UserRecord
from negotium.archive.llm_runtime import LlmRuntimeConfig


def _headers(container: Container, *, user_id: str, role_id: str) -> dict[str, str]:
    container.auth_store.create_user(
        user_id=user_id, display_name=user_id, password="password-1234"
    )
    container.access_control.upsert_user(
        UserRecord(id=user_id, display_name=user_id, title="직원", role_id=role_id)
    )
    token = container.auth_store.authenticate(user_id, "password-1234")
    assert token is not None
    return {"X-NG-User": f"Bearer {token}"}


def _container(tmp_path: Path) -> Container:
    return Container.build(
        Settings(
            env="test", archive_dir=tmp_path / "archive", workspace_dir=tmp_path / "workspaces"
        )
    )


def test_config_roundtrip_and_permissions(tmp_path: Path) -> None:
    container = _container(tmp_path)
    admin = _headers(container, user_id="owner", role_id="owner")
    viewer = _headers(container, user_id="viewer1", role_id="viewer")
    app = create_app(container)

    payload = {
        "weekly_report": {"enabled": True, "weekday": 4, "time": "17:30", "timezone": "Asia/Seoul"},
        "reminders": {"enabled": True, "time": "09:00", "stale_days": 5},
        "webhook_url": "https://hooks.example/negotium",
    }
    with TestClient(app) as client:
        assert client.get("/api/automation/config").status_code == 401
        assert client.get("/api/automation/config", headers=viewer).status_code == 403

        saved = client.put("/api/automation/config", headers=admin, json=payload)
        assert saved.status_code == 200
        fetched = client.get("/api/automation/config", headers=admin).json()
        bad_tz = client.put(
            "/api/automation/config",
            headers=admin,
            json={
                **payload,
                "weekly_report": {**payload["weekly_report"], "timezone": "Mars/Base"},
            },
        )

    assert fetched["config"]["weekly_report"]["weekday"] == 4
    assert fetched["config"]["reminders"]["stale_days"] == 5
    assert fetched["config"]["webhook_url"] == "https://hooks.example/negotium"
    assert bad_tz.status_code == 400


def test_manual_run_generates_report_and_notification(tmp_path: Path) -> None:
    container = _container(tmp_path)
    container.llm = FakeLlmProvider(
        responses=[ScriptedResponse(text="# 주간 업무 보고\n이번 주 요약입니다.")]
    )
    container.llm_runtime.write(
        LlmRuntimeConfig(
            default_route="api", default_provider="fake", local_enabled=True, api_enabled=True
        )
    )
    admin = _headers(container, user_id="owner", role_id="owner")
    app = create_app(container)

    with TestClient(app) as client:
        run = client.post("/api/automation/run", headers=admin, json={"jobs": ["weekly_report"]})
        assert run.status_code == 200
        assert run.json()["executed"] == ["weekly_report"]

        notifications = client.get("/api/notifications", headers=admin).json()
        assert notifications["unread"] >= 1
        weekly = next(item for item in notifications["items"] if item["kind"] == "weekly_report")
        assert weekly["link_path"].startswith("documents/")
        assert (tmp_path / "archive" / weekly["link_path"]).exists()

        marked = client.post("/api/notifications/read", headers=admin, json={"ids": [weekly["id"]]})
        assert marked.json()["marked"] == 1
        after = client.get("/api/notifications", headers=admin).json()
        assert after["unread"] == notifications["unread"] - 1

        unknown = client.post("/api/automation/run", headers=admin, json={"jobs": ["nope"]})
        assert unknown.status_code == 400


def test_notifications_require_login(tmp_path: Path) -> None:
    container = _container(tmp_path)
    app = create_app(container)
    with TestClient(app) as client:
        assert client.get("/api/notifications").status_code == 401
        assert client.post("/api/notifications/read", json={"ids": ["x"]}).status_code == 401
