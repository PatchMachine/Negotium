"""Tier-aware per-task LLM route recommendations.

The six ``LlmTaskName`` routes split cleanly along the model tiers:

* ``agent_planning``/``chat`` drive the tool loop, so they want an agent-tier
  (tool-capable) model;
* the four generation tasks are single-shot and only need reasoning quality;
* a general-tier model can still serve chat, just without tools.

Kept in Python rather than duplicated in the wizard's TypeScript: the tier
table already lives here, and two copies of this policy would drift.
"""

from __future__ import annotations

from typing import Any

from negotium.adapters.llm.catalog import (
    TIER_LABELS,
    ModelTier,
    model_profile,
    model_tier,
)

# Tool-driven tasks first: these are the ones that degrade without tool support.
AGENTIC_TASKS = ("agent_planning", "chat")
GENERATION_TASKS = ("memory_summary", "document_generation", "hiring", "handover")
ALL_TASKS = (*GENERATION_TASKS, *AGENTIC_TASKS)

_TIER_RANK: dict[ModelTier, int] = {"agent": 3, "reasoning": 2, "general": 1, "unknown": 0}


def _best(models: list[str], provider: str, *, prefer: tuple[ModelTier, ...]) -> str:
    """Pick the highest-ranked model, preferring the given tiers in order."""

    if not models:
        return ""
    for tier in prefer:
        matches = [model for model in models if model_tier(provider, model) == tier]
        if matches:
            return matches[0]
    return max(models, key=lambda model: _TIER_RANK[model_tier(provider, model)])


def recommend_task_routes(
    provider: str,
    models: list[str],
    *,
    route: str = "api",
) -> dict[str, dict[str, str]]:
    """Suggest a ``task -> {route, provider, model}`` mapping for a provider.

    Generation tasks go to the strongest non-agent model available (agent-tier
    models tend to be slower and pricier for single-shot work); the tool-driven
    tasks go to a tool-capable model.
    """

    if not models:
        return {}
    agentic_model = _best(models, provider, prefer=("agent", "reasoning"))
    generation_model = _best(models, provider, prefer=("reasoning", "general", "agent"))
    routes: dict[str, dict[str, str]] = {}
    for task in GENERATION_TASKS:
        routes[task] = {"route": route, "provider": provider, "model": generation_model}
    for task in AGENTIC_TASKS:
        routes[task] = {"route": route, "provider": provider, "model": agentic_model}
    return routes


def route_recommendation(provider: str, models: list[str], *, route: str = "api") -> dict[str, Any]:
    """Recommendation plus the Korean rationale the wizard shows the user."""

    routes = recommend_task_routes(provider, models, route=route)
    if not routes:
        return {"provider": provider, "route": route, "task_routes": {}, "notes": []}

    agentic_model = routes[AGENTIC_TASKS[0]]["model"]
    generation_model = routes[GENERATION_TASKS[0]]["model"]
    agentic_profile = model_profile(provider, agentic_model)
    notes: list[str] = [
        f"도구를 쓰는 작업(에이전트 실행계획·AI 어시스턴트)은 "
        f"{agentic_model}({TIER_LABELS[agentic_profile.tier]})에 배정했습니다.",
        f"단발성 문서 생성 작업은 "
        f"{generation_model}({TIER_LABELS[model_tier(provider, generation_model)]})에 "
        f"배정했습니다.",
    ]
    if not agentic_profile.supports_tools:
        notes.append(
            "선택한 provider에 도구 호출이 가능한 모델이 없어 조직·엑셀 자동 조회와 "
            "챗에서 화면 자동 호출 기능이 제한됩니다."
        )
    return {
        "provider": provider,
        "route": route,
        "task_routes": routes,
        "notes": notes,
    }
