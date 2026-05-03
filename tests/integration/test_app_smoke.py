"""Smoke test: FastAPI app factory + /health returns bus metrics."""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from patch_machine.adapters.llm.fake_adapter import FakeLlmProvider, ScriptedResponse
from patch_machine.app.container import Container
from patch_machine.app.main import create_app
from patch_machine.app.settings import Settings
from patch_machine.archive.llm_runtime import LlmRuntimeConfig
from patch_machine.archive.operations_memory import OperationsMemory


def test_health_endpoint_reports_queue_state() -> None:
    container = Container.build()
    app = create_app(container)
    with TestClient(app) as client:
        response = client.get("/health")
        assert response.status_code == 200
        payload = response.json()
        assert payload["ok"] is True
        assert payload["queue_capacity"] == container.bus.capacity
        assert "metrics" in payload


def test_contributor_site_routes_are_served(tmp_path: Path) -> None:
    container = Container.build(
        Settings(env="test", archive_dir=tmp_path / "archive", workspace_dir=tmp_path / "workspaces")
    )
    app = create_app(container)
    with TestClient(app) as client:
        home = client.get("/")
        join = client.get("/join")
        operations = client.get("/operations")
        styles = client.get("/site.css")

    assert home.status_code == 200
    assert "패치 머신은 외부 기여와 함께 더 똑똑해집니다" in home.text
    assert join.status_code == 200
    assert "좋은 제보 하나가 자동 패치의 출발점입니다" in join.text
    assert operations.status_code == 200
    assert "패치머신이 지금 운영할 회사를 기억하게 합니다" in operations.text
    assert styles.status_code == 200
    assert "text/css" in styles.headers["content-type"]


def test_operations_memory_can_be_saved_from_ui(tmp_path: Path) -> None:
    archive_dir = tmp_path / "archive"
    container = Container.build(
        Settings(env="test", archive_dir=archive_dir, workspace_dir=tmp_path / "workspaces")
    )
    app = create_app(container)

    with TestClient(app) as client:
        response = client.post(
            "/operations",
            data={
                "company_name": "Acme Retail",
                "office_project": "환불 자동화",
                "active_plan": "중복 환불 방지 계획",
            },
            follow_redirects=False,
        )
        saved = client.get("/operations")

    assert response.status_code == 303
    assert container.operations_memory.read().company_name == "Acme Retail"
    assert "Acme Retail" in saved.text
    assert (archive_dir / "operations_memory.json").exists()


def test_operations_memory_api_round_trips(tmp_path: Path) -> None:
    archive_dir = tmp_path / "archive"
    container = Container.build(
        Settings(env="test", archive_dir=archive_dir, workspace_dir=tmp_path / "workspaces")
    )
    app = create_app(container)

    with TestClient(app) as client:
        empty = client.get("/api/operations-memory")
        saved = client.put(
            "/api/operations-memory",
            json={
                "company_name": "Acme Retail",
                "office_project": "오피스 운영",
                "active_plan": "프론트엔드 로컬 검증",
            },
        )
        status = client.get("/api/status")

    assert empty.status_code == 200
    assert empty.json()["company_name"] == ""
    assert saved.status_code == 200
    assert saved.json()["company_name"] == "Acme Retail"
    assert container.operations_memory.read().active_plan == "프론트엔드 로컬 검증"
    assert status.status_code == 200
    assert status.json()["operations_memory_configured"] is True


def test_llm_chat_uses_operations_memory_context(tmp_path: Path) -> None:
    archive_dir = tmp_path / "archive"
    container = Container.build(
        Settings(env="test", archive_dir=archive_dir, workspace_dir=tmp_path / "workspaces")
    )
    fake = FakeLlmProvider(responses=[ScriptedResponse(text="청우식품 문서 자동화 상태입니다.")])
    container.llm = fake
    container.operations_memory.write(
        OperationsMemory(
            company_name="청우식품",
            office_project="회사 서류 자동화 시스템",
            active_plan="입력받는 디스코드 문서를 자동화한다.",
        )
    )
    app = create_app(container)

    with TestClient(app) as client:
        runtime = client.get("/api/llm/runtime")
        response = client.post(
            "/api/llm/chat",
            json={"message": "현재 업무 요약해줘", "route": "api", "provider": "fake"},
        )

    assert runtime.status_code == 200
    assert response.status_code == 200
    assert "청우식품" in response.json()["answer"]
    assert any("청우식품" in message.content for call in fake.calls for message in call)


def test_progress_and_integrations_degrade_without_external_config(tmp_path: Path) -> None:
    container = Container.build(
        Settings(env="test", archive_dir=tmp_path / "archive", workspace_dir=tmp_path / "workspaces")
    )
    app = create_app(container)

    with TestClient(app) as client:
        progress = client.get("/api/progress")
        work_items = client.get("/api/work-items")
        github = client.get("/api/integrations/github")
        discord = client.get("/api/integrations/discord")

    assert progress.status_code == 200
    assert "current_status" in progress.json()["current_status_md"]
    assert work_items.status_code == 200
    assert github.status_code == 200
    assert github.json()["configured"] is False
    assert discord.status_code == 200
    assert discord.json()["configured"] is False


def test_ai_office_generation_endpoints_write_archive_docs(tmp_path: Path) -> None:
    archive_dir = tmp_path / "archive"
    container = Container.build(
        Settings(env="test", archive_dir=archive_dir, workspace_dir=tmp_path / "workspaces")
    )
    container.llm = FakeLlmProvider(
        responses=[
            ScriptedResponse(text="## 직무 요구사항\n- 문서 자동화 역량"),
            ScriptedResponse(text="## 인수인계\n- 현재 업무 요약"),
            ScriptedResponse(text="## 회의록\n- 결정사항"),
        ]
    )
    container.llm_runtime.write(
        LlmRuntimeConfig(default_route="api", default_provider="fake", local_enabled=True, api_enabled=True)
    )
    container.operations_memory.write(
        OperationsMemory(
            company_name="청우식품",
            office_project="회사 서류 자동화 시스템",
            organization="대표-관리팀",
            office_tools="Discord, Excel",
            sensitive_policy="민감 문서는 로컬 LLM 우선",
        )
    )
    app = create_app(container)

    with TestClient(app) as client:
        hiring = client.post(
            "/api/hr/role-requirements",
            json={
                "role_title": "문서 자동화 담당자",
                "business_need": "Discord 문서 자동화",
                "priority": "high",
            },
        )
        handover = client.post(
            "/api/handover/brief",
            json={
                "work_title": "Discord 문서 접수 자동화",
                "outgoing_owner": "A",
                "incoming_owner": "B",
                "notes": "분류 규칙 확인 필요",
            },
        )
        document = client.post(
            "/api/documents/generate",
            json={
                "document_type": "meeting_minutes",
                "title": "자동화 회의",
                "source_text": "문서 자동화를 도입하기로 함",
                "audience": "대표",
            },
        )

    assert hiring.status_code == 200
    assert hiring.json()["path"].startswith("hr/interview_kits/")
    assert handover.status_code == 200
    assert handover.json()["path"].startswith("handover/")
    assert document.status_code == 200
    assert document.json()["path"].startswith("documents/")
    assert (archive_dir / hiring.json()["path"]).exists()


def test_secure_admin_and_upload_endpoints(tmp_path: Path) -> None:
    archive_dir = tmp_path / "archive"
    container = Container.build(
        Settings(
            env="test",
            archive_dir=archive_dir,
            workspace_dir=tmp_path / "workspaces",
            secret_key="test-master-key",
        )
    )
    app = create_app(container)

    with TestClient(app) as client:
        denied = client.put(
            "/api/admin/api-keys/openai",
            headers={"X-PM-User": "missing"},
            json={"provider": "openai", "api_key": "sk-test-1234567890"},
        )
        saved_key = client.put(
            "/api/admin/api-keys/openai",
            json={"provider": "openai", "api_key": "sk-test-1234567890", "model": "gpt-test"},
        )
        acl = client.get("/api/admin/access-control")
        uploaded = client.post(
            "/api/uploads",
            files={"file": ("hello.txt", b"hello", "text/plain")},
            data={"description": "demo", "tags": "office", "work_title": "test"},
        )
        uploads = client.get("/api/uploads")

    assert denied.status_code == 403
    assert saved_key.status_code == 200
    assert saved_key.json()["providers"][0]["masked_value"] == "sk-t...7890"
    assert acl.status_code == 200
    assert "owner" in {user["id"] for user in acl.json()["users"]}
    assert uploaded.status_code == 200
    assert uploads.json()["uploads"][0]["filename"] == "hello.txt"
