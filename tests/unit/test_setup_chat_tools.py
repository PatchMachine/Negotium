"""Setup chat: scoped tools, draft validation, tier-aware route recommendation."""

from __future__ import annotations

from pathlib import Path

import pytest

from negotium.app.container import Container
from negotium.app.schemas.core import InitialOfficeSetupResult
from negotium.app.services import mcp_hub_service
from negotium.app.services.setup_chat_service import SETUP_TOOL_NAMES, propose_setup_result
from negotium.app.services.task_routing_service import (
    AGENTIC_TASKS,
    GENERATION_TASKS,
    recommend_task_routes,
    route_recommendation,
)
from negotium.app.services.ui_surface_service import (
    OFFICE_SURFACE_IDS,
    SETUP_SURFACE_IDS,
    UI_SURFACES,
    open_surface,
)
from negotium.app.settings import Settings


def _container(tmp_path: Path) -> Container:
    return Container.build(
        Settings(
            env="test",
            archive_dir=tmp_path / "archive",
            workspace_dir=tmp_path / "workspaces",
        )
    )


def test_setup_tools_are_all_non_mutating() -> None:
    """Nothing in the setup scope changes state.

    ``setup.propose_result`` only builds a draft; applying it is a separate
    explicit user action with its own permission check and audit record. Gating
    the proposal itself forced the user to re-approve every time the model
    repaired a validation error, for no safety benefit.
    """

    writes = [name for name in SETUP_TOOL_NAMES if not mcp_hub_service.is_read_tool(name)]
    assert writes == []
    # The assistant must not be able to run arbitrary skills or mutate work.
    assert "skills.run" not in SETUP_TOOL_NAMES
    assert "hf.set_local_model" not in SETUP_TOOL_NAMES
    assert "public_reference.capture_case" not in SETUP_TOOL_NAMES


def test_setup_surfaces_are_hidden_from_the_office_assistant() -> None:
    assert set(SETUP_SURFACE_IDS).isdisjoint(OFFICE_SURFACE_IDS)
    for surface_id in SETUP_SURFACE_IDS:
        assert surface_id in UI_SURFACES
        assert UI_SURFACES[surface_id].required_permission == "admin:users"


def test_propose_result_validates_and_returns_a_review_surface(tmp_path: Path) -> None:
    container = _container(tmp_path)

    payload = propose_setup_result(
        container,
        {
            "operations_memory": {"company_name": "청우식품"},
            "roles": [{"id": "owner", "name": "대표", "level": 100, "permissions": ["*"]}],
            "users": [{"id": "kim", "display_name": "김민수", "title": "과장"}],
            "company_profile": {"company_name": "청우식품", "industry": "food"},
        },
    )

    assert payload["ok"] is True
    # The draft must validate as the same model the deterministic path emits,
    # so POST /setup/office/apply keeps its contract unchanged.
    result = InitialOfficeSetupResult.model_validate(payload["result"])
    assert result.operations_memory["company_name"] == "청우식품"
    assert [user.id for user in result.users] == ["kim"]
    # Curated package recommendations are merged in.
    assert result.recommended_package
    assert result.first_14_days

    ui = payload["ui"]
    assert ui["component"] == "setup-review"
    assert ui["props"]["result"]["operations_memory"]["company_name"] == "청우식품"


def test_propose_result_rejects_a_malformed_draft(tmp_path: Path) -> None:
    container = _container(tmp_path)

    with pytest.raises(ValueError, match="초기 설정안"):
        propose_setup_result(container, {})

    with pytest.raises(ValueError, match="형식"):
        propose_setup_result(container, {"roles": "not-a-list"})


def test_propose_result_rejects_an_empty_draft(tmp_path: Path) -> None:
    """A blank draft would propose applying nothing while looking successful."""

    container = _container(tmp_path)

    with pytest.raises(ValueError) as excinfo:
        propose_setup_result(container, {"notes": ["아직 정보를 못 모았습니다"]})

    message = str(excinfo.value)
    # The message is the model's recovery path, so it must name what is missing.
    assert "company_name" in message
    assert "users" in message
    assert "roles" in message


def test_proposal_states_it_is_not_yet_applied(tmp_path: Path) -> None:
    """Without this the model announces "설정이 적용되었습니다" prematurely."""

    container = _container(tmp_path)
    payload = propose_setup_result(
        container,
        {
            "operations_memory": {"company_name": "청우식품"},
            "roles": [{"id": "owner", "name": "대표", "level": 100, "permissions": ["*"]}],
            "users": [{"id": "kim", "display_name": "김민수", "title": "과장"}],
        },
    )

    assert payload["status"] == "proposed_awaiting_review"
    assert "적용되지 않았습니다" in str(payload["note"])


def test_setup_surfaces_open_only_for_admins(tmp_path: Path) -> None:
    from negotium.archive.access_control import UserRecord

    container = _container(tmp_path)
    container.access_control.upsert_user(
        UserRecord(id="owner", display_name="Owner", title="대표", role_id="owner")
    )
    container.access_control.upsert_user(
        UserRecord(id="viewer", display_name="Viewer", title="사원", role_id="viewer")
    )

    opened = open_surface(container, surface="setup-profile", actor="owner")
    assert opened["ui"]["component"] == "setup-profile"

    with pytest.raises(PermissionError):
        open_surface(container, surface="setup-profile", actor="viewer")


def test_unknown_surface_error_lists_the_valid_ids(tmp_path: Path) -> None:
    """The error is the model's recovery path, so it must be actionable."""

    container = _container(tmp_path)
    with pytest.raises(ValueError) as excinfo:
        open_surface(container, surface="upload_file", actor="")
    assert "uploads" in str(excinfo.value)


def test_route_recommendation_sends_tool_work_to_an_agent_tier_model() -> None:
    models = ["solar-mini", "solar-pro2", "solar-pro3"]

    routes = recommend_task_routes("solar", models)

    # Tool-driven tasks need a tool-capable, agent-tier model...
    for task in AGENTIC_TASKS:
        assert routes[task]["model"] == "solar-pro3"
    # ...single-shot generation prefers the reasoning-tier model over the
    # slower, pricier agent model.
    for task in GENERATION_TASKS:
        assert routes[task]["model"] == "solar-pro2"


def test_route_recommendation_degrades_and_explains_without_tool_support() -> None:
    result = route_recommendation("anthropic", ["claude-opus-4-7", "claude-3-5-haiku-latest"])

    assert result["task_routes"]
    # Anthropic tool translation is not implemented, so the wizard must say so.
    assert any("제한" in note for note in result["notes"])


def test_route_recommendation_is_empty_without_models() -> None:
    assert recommend_task_routes("solar", []) == {}
    assert route_recommendation("solar", [])["task_routes"] == {}
