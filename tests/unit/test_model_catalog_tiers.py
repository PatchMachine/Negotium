"""Model tier catalog: curated entries, name inference, and payload shape."""

from __future__ import annotations

import pytest

from negotium.adapters.llm.catalog import (
    CAPABILITY_LABELS,
    TIER_LABELS,
    capability_matrix,
    infer_model_tier,
    model_hidden_reasoning,
    model_profile,
    model_supports_tools,
    model_tier,
    profile_payload,
    provider_payload,
    restricted_capabilities,
    solar_reasoning_effort,
    tier_index,
)


@pytest.mark.parametrize(
    ("provider", "model", "tier"),
    [
        ("solar", "solar-pro3", "agent"),
        ("solar", "solar-open2", "agent"),
        ("solar", "solar-pro2", "reasoning"),
        ("solar", "solar-mini", "general"),
        ("openai", "gpt-5.5-pro", "agent"),
        ("openai", "o4-mini", "reasoning"),
        ("openai", "gpt-4o-mini", "general"),
        ("anthropic", "claude-opus-4-7", "agent"),
        ("anthropic", "claude-3-5-haiku-latest", "general"),
        ("gemini", "gemini-3.1-pro", "reasoning"),
        ("gemini", "gemini-1.5-flash", "general"),
        ("together", "openai/gpt-oss-20b", "reasoning"),
        ("vllm", "Qwen/Qwen3-4B", "general"),
    ],
)
def test_known_models_carry_curated_tiers(provider: str, model: str, tier: str) -> None:
    assert model_tier(provider, model) == tier
    assert model_profile(provider, model).source == "catalog"


def test_solar_pro2_is_not_a_hidden_reasoning_model() -> None:
    """Pins the office token budget.

    ``solar-pro2`` is reasoning-tier but returns content directly. If this ever
    flips to True the chat first-attempt budget jumps 1024 -> 16000 tokens and
    the office default gets slower and more expensive for no benefit.
    """

    assert model_hidden_reasoning("solar", "solar-pro2") is False
    assert model_hidden_reasoning("solar", "solar-open2") is True


def test_hidden_reasoning_without_provider_matches_legacy_name_rules() -> None:
    # The pre-tier implementation classified purely on the model name; callers
    # that have no provider in scope must keep getting the same answers.
    assert model_hidden_reasoning("", "solar-open2") is True
    assert model_hidden_reasoning("", "o3-mini") is True
    assert model_hidden_reasoning("", "gpt-5.4") is True
    assert model_hidden_reasoning("", "solar-pro2") is False
    assert model_hidden_reasoning("", "gpt-4o-mini") is False
    assert model_hidden_reasoning("", "") is False


@pytest.mark.parametrize(
    ("model", "tier"),
    [
        ("Qwen/Qwen3-Coder-30B", "agent"),
        ("some-vendor/my-agent-v2", "agent"),
        ("deepseek-r1-distill", "reasoning"),
        ("o3-pro", "reasoning"),
        ("QwQ-32B", "reasoning"),
        ("meta-llama/Llama-4-Instruct", "general"),
        ("random/model-x", "unknown"),
        ("", "unknown"),
    ],
)
def test_unknown_models_are_inferred_from_the_name(model: str, tier: str) -> None:
    assert infer_model_tier(model) == tier


def test_inferred_profile_is_marked_and_labelled_as_unclassified() -> None:
    profile = model_profile("solar", "solar-pro9-experimental")
    assert profile.source == "inferred"
    assert profile.tier == "unknown"
    assert TIER_LABELS[profile.tier] == "미분류"
    # Solar's endpoint accepts the OpenAI tools parameter, so an unreleased
    # Solar model is still assumed tool-capable.
    assert profile.supports_tools is True


def test_tool_support_follows_the_provider_not_the_tier() -> None:
    # General-tier but fully tool-capable — deriving capabilities from the tier
    # alone would tell the user gpt-4o cannot use tools, which is wrong.
    assert model_supports_tools("openai", "gpt-4o") is True
    # Agent-tier but we have not implemented Anthropic tool translation.
    assert model_supports_tools("anthropic", "claude-opus-4-7") is False
    # Local vLLM tool calling needs server launch flags, so unknown local
    # models stay conservative.
    assert model_supports_tools("vllm", "some-org/some-local-model") is False


def test_capability_matrix_and_restricted_labels() -> None:
    matrix = capability_matrix("solar", "solar-open2")
    assert matrix["tool_use"] is True
    assert matrix["multi_step_agent"] is True
    assert matrix["long_context"] is True
    assert restricted_capabilities("solar", "solar-open2") == []

    # A local general-tier model without tool support: the wizard must be able
    # to list exactly what stops working.
    restricted = restricted_capabilities("vllm", "some-org/some-local-model")
    assert CAPABILITY_LABELS["tool_use"] in restricted
    assert CAPABILITY_LABELS["setup_chat"] in restricted
    assert CAPABILITY_LABELS["excel_auto"] in restricted


def test_solar_reasoning_effort_uses_the_per_model_vocabulary() -> None:
    # The hosted API takes high|medium|low|minimal ...
    assert solar_reasoning_effort("solar", "solar-pro3", mode="agent") == "high"
    assert solar_reasoning_effort("solar", "solar-pro3", mode="chat") == "minimal"
    assert solar_reasoning_effort("solar", "solar-pro2", mode="chat") == "minimal"
    # ... while the open-weights model only accepts high|none. Sending
    # "minimal" to solar-open2 (or "none" to solar-pro3) would be rejected.
    assert solar_reasoning_effort("solar", "solar-open2", mode="agent") == "high"
    assert solar_reasoning_effort("solar", "solar-open2", mode="chat") == "none"
    # solar-mini has no reasoning_effort parameter at all.
    assert solar_reasoning_effort("solar", "solar-mini", mode="agent") == ""
    # Never emitted for other providers.
    assert solar_reasoning_effort("openai", "gpt-5.5-pro", mode="agent") == ""


def test_dated_snapshots_inherit_the_base_model_profile() -> None:
    """A pinned snapshot must not be classified differently from its base.

    The live Solar model list returns ids like ``solar-pro2-251215``. Falling
    through to name inference gave these different tiers and tool answers than
    the curated base entry, so a snapshot could claim capabilities the base
    model denies.
    """

    snapshot = model_profile("solar", "solar-pro2-251215")
    base = model_profile("solar", "solar-pro2")
    assert snapshot.tier == base.tier
    assert snapshot.supports_tools == base.supports_tools
    assert snapshot.reasoning_effort_agent == base.reasoning_effort_agent
    assert snapshot.source == "catalog"
    # The requested id is preserved so the UI shows what the user picked.
    assert snapshot.id == "solar-pro2-251215"

    mini = model_profile("solar", "solar-mini-250422")
    assert mini.tier == "general"
    assert mini.supports_tools == model_profile("solar", "solar-mini").supports_tools


def test_parallel_tool_calls_flag_is_solar_pro3_only() -> None:
    assert model_profile("solar", "solar-pro3").supports_parallel_tool_calls is True
    assert model_profile("solar", "solar-pro2").supports_parallel_tool_calls is False


def test_tier_index_groups_and_preserves_order() -> None:
    grouped = tier_index("solar", ["solar-mini", "solar-open2", "solar-pro2", "mystery-model"])
    assert grouped["agent"] == ["solar-open2"]
    assert grouped["reasoning"] == ["solar-pro2"]
    assert grouped["general"] == ["solar-mini"]
    assert grouped["unknown"] == ["mystery-model"]


def test_http_schema_carries_every_catalog_profile_field() -> None:
    """Guards against Pydantic silently dropping a newly added catalog field.

    ``ModelProfilePayload`` ignores unknown keys, so a field added to
    ``profile_payload()`` but not to the schema vanishes between the catalog and
    the frontend with no error anywhere.
    """

    from negotium.app.schemas.core import ModelProfilePayload

    catalog_keys = set(profile_payload("solar", "solar-pro3"))
    schema_keys = set(ModelProfilePayload.model_fields)
    assert catalog_keys - schema_keys == set(), (
        f"catalog fields missing from ModelProfilePayload: {sorted(catalog_keys - schema_keys)}"
    )


def test_provider_payload_keeps_fallback_models_as_plain_strings() -> None:
    """Tier metadata is additive; existing consumers must be unaffected."""

    entries = {str(item["provider"]): item for item in provider_payload()}
    solar = entries["solar"]
    assert solar["fallback_models"] == ["solar-pro3", "solar-open2", "solar-pro2", "solar-mini"]
    profiles = solar["fallback_model_profiles"]
    assert isinstance(profiles, list)
    # Index-aligned with fallback_models.
    assert [profile["id"] for profile in profiles] == solar["fallback_models"]
    assert profiles[0]["tier_label"] == "에이전트형"
