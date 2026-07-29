"""Archive search end-to-end: deep keywords, MCP tool path, reindex job."""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from negotium.app.container import Container
from negotium.app.main import create_app
from negotium.app.services import mcp_hub_service
from negotium.app.settings import Settings
from negotium.archive.access_control import UserRecord


def _headers(container: Container) -> dict[str, str]:
    container.auth_store.create_user(
        user_id="owner", display_name="Owner", password="password-1234"
    )
    container.access_control.upsert_user(
        UserRecord(id="owner", display_name="Owner", title="대표", role_id="owner")
    )
    token = container.auth_store.authenticate("owner", "password-1234")
    assert token is not None
    return {"X-NG-User": f"Bearer {token}"}


def _container(tmp_path: Path) -> Container:
    return Container.build(
        Settings(
            env="test", archive_dir=tmp_path / "archive", workspace_dir=tmp_path / "workspaces"
        )
    )


def _write_long_minutes(container: Container) -> None:
    docs = container.settings.archive_dir / "documents"
    docs.mkdir(parents=True, exist_ok=True)
    filler = "일반적인 주간 업무 공유 내용입니다. " * 300  # keyword sits well past 600 chars
    (docs / "20260601_meeting.md").write_text(
        "# 6월 회의록\n" + filler + "\n청우식품과 납품 단가 5% 인하에 합의했다.",
        encoding="utf-8",
    )


def test_search_finds_keyword_beyond_the_old_600_char_limit(tmp_path: Path) -> None:
    container = _container(tmp_path)
    _write_long_minutes(container)
    headers = _headers(container)
    app = create_app(container)

    with TestClient(app) as client:
        response = client.get(
            "/api/memory/permanent/search", params={"q": "청우식품 합의"}, headers=headers
        )

    assert response.status_code == 200
    sources = response.json()["sources"]
    assert sources, "keyword past char 600 must be retrievable"
    top = sources[0]
    assert top["path"] == "documents/20260601_meeting.md"
    assert "합의" in top["excerpt"], "excerpt must be the matching snippet, not the file head"


def test_office_memory_search_tool_returns_snippets(tmp_path: Path) -> None:
    container = _container(tmp_path)
    _write_long_minutes(container)

    result = mcp_hub_service.call_tool(
        container, "office_memory.search", {"query": "단가 인하 합의"}, actor="owner"
    )

    sources = result.result["sources"]
    assert sources
    assert "합의" in str(sources[0]["excerpt"])


def test_manual_search_index_job_runs(tmp_path: Path) -> None:
    container = _container(tmp_path)
    _write_long_minutes(container)
    headers = _headers(container)
    app = create_app(container)

    with TestClient(app) as client:
        run = client.post("/api/automation/run", headers=headers, json={"jobs": ["search_index"]})
        stats = client.get("/api/automation/search-index", headers=headers)

    assert run.status_code == 200
    assert run.json()["executed"] == ["search_index"]
    assert stats.status_code == 200
    payload = stats.json()
    assert payload["files"] >= 1
    assert payload["chunks"] >= 1
    assert payload["embeddings_enabled"] is False
