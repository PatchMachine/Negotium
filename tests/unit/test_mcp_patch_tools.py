"""Unit tests for MCP patch/agent tools."""

from __future__ import annotations

from pathlib import Path

from patch_machine.app.container import Container
from patch_machine.app.services.mcp_hub_service import call_tool
from patch_machine.app.settings import Settings


def test_agent_generate_plan_tool(tmp_path: Path) -> None:
    container = Container.build(
        Settings(env="test", archive_dir=tmp_path / "archive", workspace_dir=tmp_path / "work")
    )
    result = call_tool(
        container,
        "agent.generate_plan",
        {"objective": "주간 보고서 정리", "title": "주간 보고"},
    )
    assert result.result["ok"] is True
    assert result.result["plan"]["objective"] == "주간 보고서 정리"
    assert len(result.result["plan"]["steps"]) >= 2


def test_patch_create_run_tool(tmp_path: Path) -> None:
    container = Container.build(
        Settings(env="test", archive_dir=tmp_path / "archive", workspace_dir=tmp_path / "work")
    )
    result = call_tool(
        container,
        "patch.create_run",
        {"request": "로그인 버튼 문구 수정", "repo_id": "local"},
    )
    assert result.result["ok"] is True
    assert result.result["patch_run"]["request"] == "로그인 버튼 문구 수정"


def test_patch_apply_diff_defaults_to_dry_policy_check(tmp_path: Path) -> None:
    container = Container.build(
        Settings(env="test", archive_dir=tmp_path / "archive", workspace_dir=tmp_path / "work")
    )
    created = call_tool(
        container,
        "patch.create_run",
        {"request": "테스트 패치", "repo_id": "local"},
    )
    run_id = created.result["patch_run"]["id"]
    result = call_tool(container, "patch.apply_diff", {"patch_run_id": run_id})
    assert result.result["ok"] is True
    assert result.result["apply"] is False
