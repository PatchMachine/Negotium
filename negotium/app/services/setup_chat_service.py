"""Solar-driven first-run setup conversation.

The wizard's deterministic steps stay deterministic:

* admin creation — there is no session yet, so there is no LLM either;
* API key entry — a secret must never be typed into a chat box, because chat
  turns are persisted to ``archive/conversations/*.jsonl``.

Everything after that (company profile → organisation → file analysis →
proposed setup) becomes one conversation driven by the configured model, which
pulls the relevant form into the chat with ``ui.open_surface`` instead of
telling the user which step to click.

``POST /setup/office/analyze`` is left untouched as the non-chat fallback for
models without tool support.
"""

from __future__ import annotations

from typing import Any

from negotium.app.services.setup_catalog import recommend_patchnote_setup

# Read tools plus exactly one write tool. Scoped deliberately: the setup
# assistant must not be able to run arbitrary skills or mutate work items.
SETUP_TOOL_NAMES: tuple[str, ...] = (
    "sheets.list_files",
    "sheets.describe",
    "sheets.read_range",
    "sheets.aggregate",
    "org.roster",
    "public_reference.search_cases",
    "ui.open_surface",
    "setup.propose_result",
)


def propose_setup_result(container: Any, raw_result: dict[str, Any]) -> dict[str, Any]:
    """Validate a proposed setup draft and return it as a review surface.

    The draft is validated against the same ``InitialOfficeSetupResult`` model
    the deterministic path produces, so ``POST /setup/office/apply`` keeps its
    contract, its audit record and its permission check unchanged — only the
    way the draft is *authored* changes.
    """

    # Imported here: schemas.core imports the container, so a module-level
    # import would create a cycle.
    from negotium.app.schemas.core import CompanyProfilePayload, InitialOfficeSetupResult

    if not isinstance(raw_result, dict) or not raw_result:
        raise ValueError("result 는 초기 설정안 객체여야 합니다.")

    try:
        result = InitialOfficeSetupResult.model_validate(raw_result)
    except Exception as exc:
        raise ValueError(f"초기 설정안 형식이 올바르지 않습니다: {exc}") from exc

    # An empty draft would propose applying nothing, which looks like success
    # and wastes the admin's review. Reject it with an actionable message the
    # model can recover from on the next turn.
    missing: list[str] = []
    if not str(result.operations_memory.get("company_name") or "").strip():
        missing.append("operations_memory.company_name")
    if not result.users:
        missing.append("users")
    if not result.roles:
        missing.append("roles")
    if missing:
        raise ValueError(
            "초기 설정안이 비어 있습니다. 다음 항목을 채운 뒤 다시 호출하세요: "
            + ", ".join(missing)
            + ". 회사 정보를 사용자에게 묻거나 업로드된 파일을 sheets 도구로 읽어 채우세요."
        )

    profile_raw = raw_result.get("company_profile")
    profile = (
        CompanyProfilePayload.model_validate(profile_raw)
        if isinstance(profile_raw, dict)
        else CompanyProfilePayload()
    )
    # Merge the curated package recommendation so the chat path and the
    # deterministic path propose the same shape of setup.
    recommendation = recommend_patchnote_setup(profile, sensitive_hint=result.sensitive_hint)
    for field in (
        "recommended_package",
        "agent_packs",
        "templates",
        "workflows",
        "security_defaults",
        "integration_priorities",
        "first_14_days",
        "human_review_required",
    ):
        if not getattr(result, field, None) and recommendation.get(field):
            setattr(result, field, recommendation[field])

    payload = result.model_dump()
    return {
        "ok": True,
        # Explicit: the draft is only *proposed*. Without this the model tends
        # to tell the user "설정이 적용되었습니다" before anything was applied.
        "status": "proposed_awaiting_review",
        "note": "설정안을 제안했습니다. 아직 적용되지 않았습니다. "
        "사용자에게 검토 화면에서 내용을 확인하고 적용 버튼을 눌러달라고 안내하세요.",
        "result": payload,
        "ui": {
            "component": "setup-review",
            "title": "초기 설정 검토",
            "mode": "inline",
            "props": {"result": payload},
            "reason": "제안된 초기 설정안을 확인하고 적용하세요.",
        },
    }
