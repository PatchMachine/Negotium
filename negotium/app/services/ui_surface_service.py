"""Registry of UI surfaces the assistant can summon into the chat.

One registry, three consumers:

* the ``ui.open_surface`` tool enum (what the model may ask for),
* ``GET /api/ui/surfaces`` (what the frontend renders inline),
* the permission check applied before a surface is returned.

``id`` matches the frontend ``Page`` id so the existing lazy-loaded component
can be mounted unchanged — the surface only changes *where* it renders, from a
full page to a card inside the chat thread.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

# inline — rendered as a card in the chat thread (the default)
# panel  — docked beside the thread; still no navigation
# route  — genuinely replaces the view (escape hatch for dense admin screens)
SurfaceMode = str


@dataclass(frozen=True)
class UiSurface:
    id: str
    title: str
    group: str
    required_permission: str = ""
    mode: SurfaceMode = "inline"
    summary: str = ""
    prop_schema: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "group": self.group,
            "required_permission": self.required_permission,
            "mode": self.mode,
            "summary": self.summary,
            "prop_schema": self.prop_schema,
        }


# Deliberately not every page. Dense admin tables (인사관리, 접근제어) are worse
# inside a chat bubble than on their own screen, so they stay routed.
UI_SURFACES: dict[str, UiSurface] = {
    "work-schedule": UiSurface(
        id="work-schedule",
        title="업무 배정",
        group="오피스워크",
        required_permission="memory:write",
        summary="업무를 담당자에게 배정하고 순서/의존성을 확인하는 화면",
    ),
    "work": UiSurface(
        id="work",
        title="업무 현황 · 주간보고",
        group="오피스워크",
        summary="진행 중인 업무 현황과 주간보고 생성 화면",
    ),
    "documents": UiSurface(
        id="documents",
        title="문서 자동화 · 회의록",
        group="오피스워크",
        summary="회의록을 올려 문서와 업무 배정을 자동 생성하는 화면",
    ),
    "documents-viewer": UiSurface(
        id="documents-viewer",
        title="문서 열람",
        group="오피스워크",
        required_permission="documents:read",
        summary="생성된 문서를 찾아 읽는 화면",
    ),
    "handover": UiSurface(
        id="handover",
        title="인수인계",
        group="오피스워크",
        summary="담당자 변경 시 인수인계 자료를 만드는 화면",
    ),
    "hiring": UiSurface(
        id="hiring",
        title="채용/면접",
        group="오피스워크",
        summary="직무 요구사항·면접 질문·온보딩 문서를 만드는 화면",
    ),
    "uploads": UiSurface(
        id="uploads",
        title="업로드",
        group="시스템 관리",
        required_permission="uploads:write",
        summary="엑셀·문서 파일을 올리는 화면. 파일이 필요할 때 이 화면을 띄우세요.",
    ),
    "progress": UiSurface(
        id="progress",
        title="진행 로그",
        group="회사 업무 운영",
        summary="최근 작업 로그를 시간순으로 보는 화면",
    ),
    "skills": UiSurface(
        id="skills",
        title="스킬 실행",
        group="AI 에이전트",
        required_permission="work:read",
        summary="등록된 오피스 스킬을 직접 실행하는 화면",
    ),
    "dashboard": UiSurface(
        id="dashboard",
        title="회사 운영 설정",
        group="조직·운영 관리",
        required_permission="memory:write",
        mode="panel",
        summary="회사 기본 정보와 운영 메모리를 설정하는 화면",
    ),
    "workflow-status": UiSurface(
        id="workflow-status",
        title="워크플로우 상태",
        group="시스템 관리",
        required_permission="admin:users",
        mode="panel",
        summary="자동화 워크플로우의 현재 상태를 보는 화면",
    ),
    # Setup-only surfaces. Scoped to the setup chat so the office assistant
    # cannot pull first-run screens into an ordinary conversation.
    "setup-profile": UiSurface(
        id="setup-profile",
        title="회사 프로필 입력",
        group="초기 설정",
        required_permission="admin:users",
        summary="회사명·업종·규모·조직 형태를 입력받는 폼. 사용자에게 회사 정보를 "
        "말로 물어보는 대신 이 폼을 띄우세요.",
        prop_schema={
            "type": "object",
            "properties": {"prefill": {"type": "object"}},
        },
    ),
    "setup-files": UiSurface(
        id="setup-files",
        title="회사 자료 업로드",
        group="초기 설정",
        required_permission="admin:users",
        summary="조직도·인적사항·운영 규정 파일을 올리는 화면",
    ),
    "setup-review": UiSurface(
        id="setup-review",
        title="초기 설정 검토",
        group="초기 설정",
        required_permission="admin:users",
        summary="제안된 초기 설정안을 검토하고 적용하는 화면. "
        "setup.propose_result 도구가 자동으로 띄웁니다.",
        prop_schema={"type": "object", "properties": {"result": {"type": "object"}}},
    ),
    "setup-routes": UiSurface(
        id="setup-routes",
        title="작업별 LLM 배정",
        group="초기 설정",
        required_permission="admin:users",
        summary="업무 종류별로 어떤 모델을 쓸지 확인하는 화면",
    ),
}

# Surfaces the first-run setup assistant may open. Kept separate so the office
# chat assistant never offers setup screens mid-conversation.
SETUP_SURFACE_IDS = ("setup-profile", "setup-files", "setup-review", "setup-routes")
OFFICE_SURFACE_IDS = tuple(key for key in UI_SURFACES if key not in SETUP_SURFACE_IDS)


def surface_payload(
    container: Any, actor: str = "", *, include_setup: bool = False
) -> list[dict[str, Any]]:
    """Surfaces the caller may open, for the frontend registry."""

    payload: list[dict[str, Any]] = []
    for key, surface in UI_SURFACES.items():
        if not include_setup and key in SETUP_SURFACE_IDS:
            continue
        if (
            actor
            and surface.required_permission
            and not container.access_control.has_permission(actor, surface.required_permission)
        ):
            continue
        payload.append(surface.to_dict())
    return payload


def open_surface(
    container: Any,
    *,
    surface: str,
    title: str = "",
    props: dict[str, Any] | None = None,
    reason: str = "",
    actor: str = "",
) -> dict[str, Any]:
    """Resolve a surface request into a UI descriptor for the chat thread.

    Purely presentational — it mutates nothing, which is why it is classified
    as a read tool and auto-executes.
    """

    key = (surface or "").strip()
    known = UI_SURFACES.get(key)
    if known is None:
        raise ValueError(
            f"'{key}' 화면을 찾을 수 없습니다. 사용 가능: {', '.join(sorted(UI_SURFACES))}"
        )
    if (
        actor
        and known.required_permission
        and not container.access_control.has_permission(actor, known.required_permission)
    ):
        raise PermissionError(f"'{known.title}' 화면을 열 권한이 없습니다.")
    return {
        "ok": True,
        "ui": {
            "component": known.id,
            "title": title.strip() or known.title,
            "mode": known.mode,
            "props": props or {},
            "reason": reason,
        },
    }
