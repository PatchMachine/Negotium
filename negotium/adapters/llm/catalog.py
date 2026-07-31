"""Provider metadata and model catalog helpers for external LLM APIs."""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from typing import Literal

import httpx

ProviderName = Literal["solar", "openai", "anthropic", "gemini", "together", "vllm"]


@dataclass(frozen=True)
class ProviderMetadata:
    id: ProviderName
    label: str
    default_base_url: str
    fallback_models: tuple[str, ...]


PROVIDERS: dict[str, ProviderMetadata] = {
    "solar": ProviderMetadata(
        id="solar",
        label="Upstage / Solar",
        default_base_url="https://api.upstage.ai/v1",
        fallback_models=(
            "solar-pro3",
            "solar-open2",
            "solar-pro2",
            "solar-mini",
        ),
    ),
    "openai": ProviderMetadata(
        id="openai",
        label="OpenAI / GPT",
        default_base_url="https://api.openai.com/v1",
        fallback_models=(
            "gpt-5.5-pro",
            "gpt-5.4",
            "gpt-5.4-mini",
            "gpt-5-nano",
            "gpt-4.1",
            "gpt-4.1-mini",
            "gpt-4o",
            "gpt-4o-mini",
            "o4-mini",
        ),
    ),
    "anthropic": ProviderMetadata(
        id="anthropic",
        label="Anthropic / Claude",
        default_base_url="https://api.anthropic.com/v1",
        fallback_models=(
            "claude-opus-4-7",
            "claude-sonnet-4-6",
            "claude-haiku-4-5",
            "claude-3-7-sonnet-latest",
            "claude-3-5-sonnet-latest",
            "claude-3-5-haiku-latest",
        ),
    ),
    "gemini": ProviderMetadata(
        id="gemini",
        label="Google / Gemini",
        default_base_url="https://generativelanguage.googleapis.com/v1beta",
        fallback_models=(
            "gemini-3.1-pro",
            "gemini-3-flash",
            "gemini-3-flash-lite",
            "gemini-2.0-flash",
            "gemini-1.5-pro",
            "gemini-1.5-flash",
        ),
    ),
    "together": ProviderMetadata(
        id="together",
        label="Together AI",
        default_base_url="https://api.together.ai/v1",
        fallback_models=(
            "openai/gpt-oss-20b",
            "meta-llama/Meta-Llama-3.1-8B-Instruct-Turbo",
            "meta-llama/Llama-3-8b-chat-hf",
            "mistralai/Mixtral-8x7B-Instruct-v0.1",
        ),
    ),
    "vllm": ProviderMetadata(
        id="vllm",
        label="vLLM / Local HTTP",
        default_base_url="http://localhost:8000/v1",
        fallback_models=("Qwen/Qwen3-4B",),
    ),
}


def require_provider(provider: str) -> ProviderMetadata:
    try:
        return PROVIDERS[provider]
    except KeyError as exc:
        raise ValueError(f"unsupported LLM provider: {provider}") from exc


# Substrings (case-insensitive) that mark a model as image/vision capable.
_VISION_MODEL_MARKERS: dict[str, tuple[str, ...]] = {
    "openai": ("gpt-4o", "gpt-4.1", "gpt-5", "gpt-6", "o3", "o4", "vision"),
    "anthropic": ("claude-3-5", "claude-3-7", "claude-sonnet-4", "claude-opus-4", "claude-haiku-4"),
    "gemini": ("gemini-1.5", "gemini-2", "gemini-3", "gemini-pro-vision", "flash"),
    "together": ("llama-3.2", "llava", "vision", "qwen2-vl", "qwen2.5-vl"),
    "vllm": ("vl", "llava", "vision", "qwen2-vl", "qwen2.5-vl"),
}


def model_supports_vision(provider: str, model: str) -> bool:
    """Best-effort check whether a provider/model accepts image input.

    This is intentionally conservative: when unsure we return ``False`` so the
    pipeline falls back to text/OCR rather than sending images a model cannot
    read. ``vllm`` defaults to text-only unless the model name hints vision.
    """

    name = (model or "").strip().lower()
    if not name:
        return False
    markers = _VISION_MODEL_MARKERS.get(provider, ())
    return any(marker in name for marker in markers)


# Substrings (case-insensitive) that mark a model as audio-input capable.
_AUDIO_MODEL_MARKERS: dict[str, tuple[str, ...]] = {
    "openai": ("gpt-4o-audio", "gpt-4o-realtime", "audio-preview", "gpt-audio"),
    # Gemini 1.5+/2.x/3.x natively accept inline audio.
    "gemini": ("gemini-1.5", "gemini-2", "gemini-3", "flash", "pro"),
    "together": ("audio", "whisper"),
    "vllm": ("audio", "qwen2-audio", "qwen2.5-omni"),
}


def model_supports_audio(provider: str, model: str) -> bool:
    """Best-effort check whether a provider/model accepts audio input.

    Anthropic has no audio-input support, so it always returns ``False``.
    """

    name = (model or "").strip().lower()
    if not name:
        return False
    markers = _AUDIO_MODEL_MARKERS.get(provider, ())
    return any(marker in name for marker in markers)


# ---------------------------------------------------------------------------
# Model tiers
#
# Selectable models are grouped into three user-facing tiers so the setup wizard
# can explain what a given choice can and cannot do:
#
#   agent     (에이전트형) — built for multi-step tool-driven work
#   reasoning (추론형)     — strong analysis, tool-capable
#   general   (일반형)     — fast chat/summarization
#   unknown   (미분류)     — not in the catalog; inferred from the name
#
# ``tier`` and ``hidden_reasoning`` are deliberately independent. ``solar-pro2``
# is a reasoning-tier model that nonetheless returns content directly, so it must
# keep the small fast first-attempt token budget; deriving the budget from the
# tier would silently regress the office default from 1024 to 16000 tokens.
# ---------------------------------------------------------------------------

ModelTier = Literal["agent", "reasoning", "general", "unknown"]

TIER_ORDER: tuple[ModelTier, ...] = ("agent", "reasoning", "general", "unknown")

TIER_LABELS: dict[ModelTier, str] = {
    "agent": "에이전트형",
    "reasoning": "추론형",
    "general": "일반형",
    "unknown": "미분류",
}

# Capability keys surfaced to the wizard so a user picking a weaker (typically
# local) model is told exactly which product features go dark.
CAPABILITY_LABELS: dict[str, str] = {
    "tool_use": "AI 도구 사용 (조직·엑셀 자동 조회)",
    "chat_first_ui": "챗에서 화면 자동 호출",
    "excel_auto": "엑셀 자율 분석",
    "setup_chat": "대화형 설치 마법사",
    "multi_step_agent": "다단계 자율 실행",
    "deep_reasoning": "심층 추론",
    "long_context": "장문 컨텍스트 (128k+)",
}

_LONG_CONTEXT_THRESHOLD = 128_000


@dataclass(frozen=True)
class ModelProfile:
    """Per-model metadata backing the tier UI and the tool-calling gate."""

    id: str
    tier: ModelTier
    label: str = ""
    strength: str = ""
    context_window: int = 0
    # 0 means "fall back to the caller's legacy budget logic".
    max_output_tokens: int = 0
    supports_tools: bool = False
    supports_parallel_tool_calls: bool = False
    # True when the model burns invisible tokens before emitting any content.
    hidden_reasoning: bool = False
    # ``reasoning_effort`` values, which are per-model vocabularies rather than a
    # single provider-wide enum: solar-pro3/pro2 accept high|medium|low|minimal
    # while the open-weights solar-open2 accepts only high|none. Empty on both
    # sides means the model has no reasoning_effort parameter at all.
    reasoning_effort_agent: str = ""
    reasoning_effort_direct: str = ""
    source: str = "catalog"  # catalog | inferred


def _profile(
    model_id: str,
    tier: ModelTier,
    *,
    label: str = "",
    strength: str = "",
    context_window: int = 0,
    max_output_tokens: int = 0,
    supports_tools: bool = False,
    supports_parallel_tool_calls: bool = False,
    hidden_reasoning: bool = False,
    reasoning_effort_agent: str = "",
    reasoning_effort_direct: str = "",
) -> ModelProfile:
    return ModelProfile(
        id=model_id,
        tier=tier,
        label=label,
        strength=strength,
        context_window=context_window,
        max_output_tokens=max_output_tokens,
        supports_tools=supports_tools,
        supports_parallel_tool_calls=supports_parallel_tool_calls,
        hidden_reasoning=hidden_reasoning,
        reasoning_effort_agent=reasoning_effort_agent,
        reasoning_effort_direct=reasoning_effort_direct,
    )


def _by_id(profiles: tuple[ModelProfile, ...]) -> dict[str, ModelProfile]:
    return {profile.id: profile for profile in profiles}


_MODEL_PROFILES: dict[str, dict[str, ModelProfile]] = {
    # Verified against the Upstage console API reference (console.upstage.ai).
    # reasoning_effort defaults to "minimal" on solar-pro3/pro2, so both return
    # content directly unless we ask for reasoning — hence hidden_reasoning is
    # False for them and the fast office token budget is preserved.
    "solar": _by_id(
        (
            _profile(
                "solar-pro3",
                "agent",
                label="Solar Pro 3",
                strength="에이전트 특화 최신 플래그십 (102B MoE). 도구 병렬 호출을 기본 지원합니다",
                context_window=128_000,
                supports_tools=True,
                supports_parallel_tool_calls=True,
                # "high" cost ~32s for a single 279-token setup-chat turn, which
                # reads as a hang in the wizard. One step down keeps tool-call
                # quality while cutting the hidden-reasoning stall.
                reasoning_effort_agent="medium",
                reasoning_effort_direct="minimal",
            ),
            _profile(
                "solar-open2",
                "agent",
                label="Solar Open 2",
                strength="자체 호스팅용 오픈 웨이트 에이전트 모델 (vLLM 서빙)",
                context_window=1_000_000,
                max_output_tokens=32_000,
                supports_tools=True,
                hidden_reasoning=True,
                # The open-weights model only accepts high|none, not the
                # console API's four-level scale.
                reasoning_effort_agent="high",
                reasoning_effort_direct="none",
            ),
            _profile(
                "solar-pro2",
                "reasoning",
                label="Solar Pro 2",
                strength="한국어 오피스워크 기본 모델. 응답을 바로 반환해 빠릅니다",
                context_window=65_000,
                supports_tools=True,
                reasoning_effort_agent="high",
                reasoning_effort_direct="minimal",
            ),
            _profile(
                "solar-mini",
                "general",
                label="Solar Mini",
                strength="빠른 응답이 필요한 요약/분류 작업 후보 (reasoning 미지원)",
                context_window=32_000,
                supports_tools=True,
            ),
            _profile(
                "syn-pro",
                "general",
                label="Syn Pro",
                strength="합성 데이터 최적화 모델 (reasoning 미지원)",
                supports_tools=True,
            ),
            _profile(
                "solar-pro",
                "general",
                label="Solar Pro",
                strength="이전 세대 범용 모델",
                context_window=32_000,
            ),
            _profile("solar-1-mini-chat", "general", label="Solar 1 Mini Chat"),
        )
    ),
    "openai": _by_id(
        (
            _profile(
                "gpt-5.5-pro",
                "agent",
                supports_tools=True,
                hidden_reasoning=True,
                context_window=400_000,
            ),
            _profile(
                "gpt-5.4",
                "agent",
                supports_tools=True,
                hidden_reasoning=True,
                context_window=400_000,
            ),
            _profile("gpt-5.4-mini", "reasoning", supports_tools=True, hidden_reasoning=True),
            _profile("gpt-5-nano", "reasoning", supports_tools=True, hidden_reasoning=True),
            _profile("o4-mini", "reasoning", supports_tools=True, hidden_reasoning=True),
            _profile("gpt-4.1", "general", supports_tools=True, context_window=1_000_000),
            _profile("gpt-4.1-mini", "general", supports_tools=True, context_window=1_000_000),
            _profile("gpt-4o", "general", supports_tools=True, context_window=128_000),
            _profile("gpt-4o-mini", "general", supports_tools=True, context_window=128_000),
        )
    ),
    # Anthropic/Gemini tool translation is not implemented in this codebase yet,
    # so supports_tools stays False even for agent-grade models.
    "anthropic": _by_id(
        (
            _profile("claude-opus-4-7", "agent", context_window=200_000),
            _profile("claude-sonnet-4-6", "agent", context_window=200_000),
            _profile("claude-haiku-4-5", "general", context_window=200_000),
            _profile("claude-3-7-sonnet-latest", "general", context_window=200_000),
            _profile("claude-3-5-sonnet-latest", "general", context_window=200_000),
            _profile("claude-3-5-haiku-latest", "general", context_window=200_000),
        )
    ),
    "gemini": _by_id(
        (
            _profile("gemini-3.1-pro", "reasoning", context_window=1_000_000),
            _profile("gemini-3-flash", "general", context_window=1_000_000),
            _profile("gemini-3-flash-lite", "general", context_window=1_000_000),
            _profile("gemini-2.0-flash", "general", context_window=1_000_000),
            _profile("gemini-1.5-pro", "general", context_window=2_000_000),
            _profile("gemini-1.5-flash", "general", context_window=1_000_000),
        )
    ),
    "together": _by_id(
        (
            _profile(
                "openai/gpt-oss-20b",
                "reasoning",
                strength="오픈 모델 기반 문서 생성/요약 후보",
                supports_tools=True,
            ),
            _profile(
                "meta-llama/Meta-Llama-3.1-8B-Instruct-Turbo",
                "general",
                strength="빠른 응답과 비용 효율이 좋은 기본 업무 자동화 후보",
                supports_tools=True,
            ),
            _profile("meta-llama/Llama-3-8b-chat-hf", "general", supports_tools=True),
            _profile(
                "mistralai/Mixtral-8x7B-Instruct-v0.1",
                "general",
                strength="긴 문서와 범용 지시 처리 실험 후보",
                supports_tools=True,
            ),
        )
    ),
    # Local vLLM tool calling additionally requires the server to be started with
    # ``--enable-auto-tool-choice`` (and a matching ``--tool-call-parser``), so we
    # only claim tool support for models we ship a documented recipe for.
    "vllm": _by_id(
        (
            _profile(
                "Qwen/Qwen3-4B",
                "general",
                strength="가벼운 기본 로컬 에이전트 후보",
                supports_tools=True,
                context_window=32_768,
            ),
            _profile(
                "Qwen/Qwen3-8B",
                "general",
                strength="업무 문서/추론 품질을 높인 Qwen 후보",
                supports_tools=True,
                context_window=32_768,
            ),
            _profile(
                "Qwen/Qwen2.5-7B-Instruct",
                "general",
                strength="검증된 instruct 텍스트 모델",
                context_window=32_768,
            ),
            _profile(
                "upstage/SOLAR-10.7B-Instruct-v1.0",
                "general",
                strength="한국어 업무/문서 자동화 실험 후보",
            ),
        )
    ),
}

# Providers whose endpoints accept the OpenAI ``tools`` parameter, so an unknown
# (inferred) model there is assumed tool-capable. vLLM is excluded on purpose:
# tool support there depends on server launch flags, not the model name.
_TOOL_CAPABLE_INFERRED_PROVIDERS = frozenset({"solar", "openai", "together"})

# Name markers used when a model is not in the catalog. Ordered: the first
# matching tier wins, so agent beats reasoning beats general.
_TIER_PREFIX_MARKERS: tuple[tuple[ModelTier, tuple[str, ...]], ...] = (
    ("reasoning", ("o1", "o3", "o4", "o5")),
)
_TIER_KEYWORD_MARKERS: tuple[tuple[ModelTier, tuple[str, ...]], ...] = (
    ("agent", ("open2", "agent", "-coder", "coder-", "devstral", "swe-")),
    ("reasoning", ("reasoning", "thinking", "-r1", "qwq", "deepseek-r")),
    ("general", ("instruct", "-chat", "chat-", "mini", "flash", "lite", "nano", "turbo")),
)

# Hidden-reasoning inference. Moved here from ``app/api/_shared.py`` so the
# token-budget decision and the tier catalog share one source of truth.
_REASONING_MODEL_PREFIXES = ("o1", "o3", "o4", "o5", "gpt-5", "gpt-6")
_REASONING_MODEL_KEYWORDS = ("reasoning", "solar-open")


def _infer_hidden_reasoning(model: str) -> bool:
    name = (model or "").strip().lower()
    if not name:
        return False
    if name.startswith(_REASONING_MODEL_PREFIXES):
        return True
    return any(keyword in name for keyword in _REASONING_MODEL_KEYWORDS)


def infer_model_tier(model: str) -> ModelTier:
    """Guess a tier from the model name when the catalog has no entry."""

    name = (model or "").strip().lower()
    if not name:
        return "unknown"
    bare = name.rsplit("/", 1)[-1]
    for tier, prefixes in _TIER_PREFIX_MARKERS:
        if bare.startswith(prefixes):
            return tier
    for tier, keywords in _TIER_KEYWORD_MARKERS:
        if any(keyword in name for keyword in keywords):
            return tier
    return "unknown"


# Providers pin dated snapshots of a model (``solar-pro2-251215``,
# ``solar-mini-250422``). Without stripping the suffix the snapshot and its base
# model get classified differently — the snapshot falls through to inference and
# can end up claiming capabilities the curated base entry denies.
_DATE_SUFFIX_RE = re.compile(r"-(?:\d{6}|\d{8})$")


def _base_model_name(model: str) -> str:
    return _DATE_SUFFIX_RE.sub("", model)


def _lookup_profile(provider: str, name: str) -> ModelProfile | None:
    catalog = _MODEL_PROFILES.get(provider, {})
    known = catalog.get(name)
    if known is not None:
        return known
    lowered = name.lower()
    return next((entry for key, entry in catalog.items() if key.lower() == lowered), None)


def model_profile(provider: str, model: str) -> ModelProfile:
    """Return catalog metadata for a model, inferring one when it is unknown."""

    name = (model or "").strip()
    if not name:
        return ModelProfile(id="", tier="unknown", source="inferred")
    known = _lookup_profile(provider, name)
    if known is not None:
        return known
    base = _base_model_name(name)
    if base != name:
        # A dated snapshot inherits its base model's profile, keeping the
        # requested id so the UI still shows what the user selected.
        inherited = _lookup_profile(provider, base)
        if inherited is not None:
            return replace(inherited, id=name)
    return ModelProfile(
        id=name,
        tier=infer_model_tier(name),
        supports_tools=provider in _TOOL_CAPABLE_INFERRED_PROVIDERS,
        hidden_reasoning=_infer_hidden_reasoning(name),
        source="inferred",
    )


def model_tier(provider: str, model: str) -> ModelTier:
    return model_profile(provider, model).tier


def model_supports_tools(provider: str, model: str) -> bool:
    """Return True when the provider/model pair can be given tool definitions."""

    return model_profile(provider, model).supports_tools


def model_hidden_reasoning(provider: str, model: str) -> bool:
    """Return True when the model reasons (hidden tokens) before emitting content."""

    return model_profile(provider, model).hidden_reasoning


def model_supports_parallel_tool_calls(provider: str, model: str) -> bool:
    return model_profile(provider, model).supports_parallel_tool_calls


def solar_reasoning_effort(provider: str, model: str, *, mode: str = "chat") -> str:
    """Return the Solar ``reasoning_effort`` value for a call, or "" to omit it.

    Agent loops want the model to actually think; plain chat and office document
    generation want content immediately. The value is model-specific because the
    hosted API (high|medium|low|minimal) and the open-weights model (high|none)
    use different vocabularies.
    """

    if provider != "solar":
        return ""
    profile = model_profile(provider, model)
    return profile.reasoning_effort_agent if mode == "agent" else profile.reasoning_effort_direct


def capability_matrix(provider: str, model: str) -> dict[str, bool]:
    """Map capability keys to whether this provider/model pair supports them.

    Derived from the model's own flags rather than from the tier alone: several
    general-tier models (``gpt-4o``) are fully tool-capable, and claiming
    otherwise would make the wizard's guidance wrong.
    """

    profile = model_profile(provider, model)
    tools = profile.supports_tools
    return {
        "tool_use": tools,
        "chat_first_ui": tools,
        "excel_auto": tools,
        "setup_chat": tools,
        "multi_step_agent": tools and profile.tier == "agent",
        "deep_reasoning": profile.tier in {"agent", "reasoning"},
        "long_context": profile.context_window >= _LONG_CONTEXT_THRESHOLD,
    }


def restricted_capabilities(provider: str, model: str) -> list[str]:
    """Korean labels for the features this provider/model pair cannot do."""

    matrix = capability_matrix(provider, model)
    return [CAPABILITY_LABELS[key] for key in CAPABILITY_LABELS if not matrix.get(key, False)]


def profile_payload(provider: str, model: str) -> dict[str, object]:
    """Serialize a model profile for the HTTP API / frontend."""

    profile = model_profile(provider, model)
    return {
        "id": profile.id,
        "tier": profile.tier,
        "tier_label": TIER_LABELS[profile.tier],
        "label": profile.label,
        "strength": profile.strength,
        "context_window": profile.context_window,
        "max_output_tokens": profile.max_output_tokens,
        "supports_tools": profile.supports_tools,
        "supports_parallel_tool_calls": profile.supports_parallel_tool_calls,
        "hidden_reasoning": profile.hidden_reasoning,
        "reasoning_effort": profile.reasoning_effort_agent,
        "source": profile.source,
        "capabilities": capability_matrix(provider, model),
        "restricted": restricted_capabilities(provider, model),
    }


def model_entries(provider: str, models: Sequence[str]) -> list[dict[str, object]]:
    """Profile payloads index-aligned with ``models``."""

    return [profile_payload(provider, model) for model in models]


def tier_index(provider: str, models: Sequence[str]) -> dict[str, list[str]]:
    """Group model ids by tier, preserving the incoming order within each tier."""

    grouped: dict[str, list[str]] = {tier: [] for tier in TIER_ORDER}
    for model in models:
        grouped[model_tier(provider, model)].append(model)
    return grouped


def default_base_url(provider: str, *, vllm_base_url: str = "") -> str:
    metadata = require_provider(provider)
    if provider == "vllm" and vllm_base_url.strip():
        return vllm_base_url.strip().rstrip("/")
    return metadata.default_base_url


async def list_models(
    provider: str,
    *,
    api_key: str = "",
    base_url: str = "",
) -> dict[str, object]:
    metadata = require_provider(provider)
    refreshed_at = datetime.now(UTC).isoformat()
    requires_api_key = provider in {"solar", "openai", "anthropic", "gemini", "together"}
    if not api_key and requires_api_key:
        return _fallback_payload(
            metadata,
            reason="api key is not configured",
            refreshed_at=refreshed_at,
            configured=False,
            requires_api_key=requires_api_key,
        )
    try:
        if provider == "openai":
            models = await _openai_models(
                api_key=api_key, base_url=base_url or metadata.default_base_url
            )
        elif provider == "anthropic":
            models = await _anthropic_models(
                api_key=api_key, base_url=base_url or metadata.default_base_url
            )
        elif provider == "gemini":
            models = await _gemini_models(
                api_key=api_key, base_url=base_url or metadata.default_base_url
            )
        elif provider in {"solar", "together", "vllm"}:
            models = await _openai_compatible_models(
                base_url=base_url or metadata.default_base_url, api_key=api_key
            )
        else:
            models = []
        if models:
            return {
                "provider": provider,
                "models": models,
                "source": "live",
                "refreshed_at": refreshed_at,
                "reason": "",
                "configured": bool(api_key) or not requires_api_key,
                "requires_api_key": requires_api_key,
                "model_profiles": model_entries(provider, models),
                "tiers": tier_index(provider, models),
            }
    except (httpx.HTTPError, KeyError, TypeError, ValueError) as exc:
        return _fallback_payload(
            metadata,
            reason=str(exc),
            refreshed_at=refreshed_at,
            configured=bool(api_key) or not requires_api_key,
            requires_api_key=requires_api_key,
        )
    return _fallback_payload(
        metadata,
        reason="live model list is unavailable",
        refreshed_at=refreshed_at,
        configured=bool(api_key) or not requires_api_key,
        requires_api_key=requires_api_key,
    )


def provider_payload(*, vllm_base_url: str = "") -> list[dict[str, object]]:
    return [
        {
            "provider": provider,
            "label": metadata.label,
            "base_url": default_base_url(provider, vllm_base_url=vllm_base_url),
            "base_url_source": "system",
            "fallback_models": list(metadata.fallback_models),
            "fallback_model_profiles": model_entries(provider, metadata.fallback_models),
            "tiers": tier_index(provider, metadata.fallback_models),
        }
        for provider, metadata in PROVIDERS.items()
    ]


def _fallback_payload(
    metadata: ProviderMetadata,
    *,
    reason: str,
    refreshed_at: str,
    configured: bool = False,
    requires_api_key: bool = True,
) -> dict[str, object]:
    models = list(metadata.fallback_models)
    return {
        "provider": metadata.id,
        "models": models,
        "source": "fallback",
        "refreshed_at": refreshed_at,
        "reason": reason,
        "configured": configured,
        "requires_api_key": requires_api_key,
        "model_profiles": model_entries(metadata.id, models),
        "tiers": tier_index(metadata.id, models),
    }


async def _openai_models(*, api_key: str, base_url: str) -> list[str]:
    async with httpx.AsyncClient(timeout=20) as client:
        response = await client.get(
            f"{base_url.rstrip('/')}/models",
            headers={"Authorization": f"Bearer {api_key}"},
        )
        response.raise_for_status()
    ids = [
        model["id"]
        for model in response.json().get("data", [])
        if isinstance(model, dict) and isinstance(model.get("id"), str)
    ]
    return _chat_model_order(
        "openai", [model_id for model_id in ids if _is_openai_chat_model(model_id)]
    )


def _is_openai_chat_model(model_id: str) -> bool:
    """Return True for OpenAI models suitable for chat/responses-style text generation."""

    blocked_prefixes = (
        "babbage",
        "davinci",
        "text-",
        "dall-e",
        "tts",
        "whisper",
        "omni-moderation",
        "text-embedding",
    )
    if model_id.startswith(blocked_prefixes):
        return False
    if "embedding" in model_id or "moderation" in model_id or "audio" in model_id:
        return False
    return model_id.startswith(("gpt-", "o1", "o3", "o4"))


def _chat_model_order(provider: str, models: list[str]) -> list[str]:
    metadata = require_provider(provider)
    seen: set[str] = set()
    ordered: list[str] = []
    for preferred in metadata.fallback_models:
        if preferred in models and preferred not in seen:
            ordered.append(preferred)
            seen.add(preferred)
    for model in sorted(models):
        if model not in seen:
            ordered.append(model)
            seen.add(model)
    return ordered


async def _openai_compatible_models(*, base_url: str, api_key: str) -> list[str]:
    headers = {"Authorization": f"Bearer {api_key or 'EMPTY'}"}
    async with httpx.AsyncClient(timeout=20) as client:
        response = await client.get(f"{base_url.rstrip('/')}/models", headers=headers)
        response.raise_for_status()
    return sorted(
        model["id"]
        for model in response.json().get("data", [])
        if isinstance(model, dict) and isinstance(model.get("id"), str)
    )


async def _anthropic_models(*, api_key: str, base_url: str) -> list[str]:
    async with httpx.AsyncClient(timeout=20) as client:
        response = await client.get(
            f"{base_url.rstrip('/')}/models",
            params={"limit": 100},
            headers={
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
            },
        )
        response.raise_for_status()
    return sorted(
        model["id"]
        for model in response.json().get("data", [])
        if isinstance(model, dict) and isinstance(model.get("id"), str)
    )


async def _gemini_models(*, api_key: str, base_url: str) -> list[str]:
    async with httpx.AsyncClient(timeout=20) as client:
        response = await client.get(f"{base_url.rstrip('/')}/models", params={"key": api_key})
        response.raise_for_status()
    models: list[str] = []
    for item in response.json().get("models", []):
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "").removeprefix("models/")
        methods = item.get("supportedGenerationMethods") or []
        if name and "generateContent" in methods:
            models.append(name)
    return sorted(models)


async def search_huggingface_models(query: str, *, limit: int = 12) -> list[dict[str, object]]:
    term = query.strip()
    if not term:
        return [
            {
                "id": model_id,
                "downloads": 0,
                "likes": 0,
                "tags": ["recommended"],
                "pipeline_tag": "text-generation",
            }
            for model_id in (
                "Qwen/Qwen3-4B",
                "Qwen/Qwen3-8B",
                "Qwen/Qwen2.5-7B-Instruct",
                "LGAI-EXAONE/EXAONE-4.5-33B",
                "LGAI-EXAONE/EXAONE-4.0-1.2B",
                "LGAI-EXAONE/EXAONE-3.0-7.8B-Instruct",
                "upstage/SOLAR-10.7B-Instruct-v1.0",
            )
        ]
    async with httpx.AsyncClient(timeout=20) as client:
        response = await client.get(
            "https://huggingface.co/api/models",
            params={
                "search": term,
                "filter": "text-generation",
                "sort": "downloads",
                "direction": "-1",
                "limit": limit,
            },
        )
        response.raise_for_status()
    results: list[dict[str, object]] = []
    for item in response.json():
        if not isinstance(item, dict):
            continue
        model_id = item.get("modelId") or item.get("id")
        if not isinstance(model_id, str) or not model_id:
            continue
        results.append(
            {
                "id": model_id,
                "downloads": int(item.get("downloads") or 0),
                "likes": int(item.get("likes") or 0),
                "tags": [str(tag) for tag in item.get("tags", [])[:8]],
                "pipeline_tag": str(item.get("pipeline_tag") or ""),
            }
        )
    return results
