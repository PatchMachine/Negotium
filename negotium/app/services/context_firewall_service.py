"""Local Context Firewall policy, scanning, redaction, and audit helpers."""

from __future__ import annotations

import fnmatch
import hashlib
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal, cast

import yaml

from negotium.domain.ports import LlmMessage, LlmResponse

Sensitivity = Literal["S0", "S1", "S2", "S3", "S4", "S5"]
FirewallDecision = Literal["allow", "allow_redacted", "local_only", "approval_required", "block"]

SENSITIVITY_RANK: dict[str, int] = {"S0": 0, "S1": 1, "S2": 2, "S3": 3, "S4": 4, "S5": 5}
FRONTIER_DESTINATIONS = {
    "frontier_llm",
    "cloud_llm",
    "api_llm",
    "solar",
    "openai",
    "anthropic",
    "gemini",
    "together",
}
LOCAL_DESTINATIONS = {"local_llm", "vllm", "fake", "local"}
CONTEXT_HEADER = (
    "You are receiving a redacted and abstracted technical context. "
    "Do not request secrets, raw logs, raw code, customer identifiers, internal repository names, "
    "or environment variables. Provide general reasoning, test scenarios, and architectural considerations only."
)


@dataclass(frozen=True)
class FirewallFinding:
    detector: str
    item_type: str
    sensitivity: Sensitivity
    count: int = 1


@dataclass(frozen=True)
class ContextFirewallPolicy:
    default_action: FirewallDecision = "local_only"
    unknown_data_action: FirewallDecision = "local_only"
    allow_frontier_api: bool = True
    blocked_paths: list[str] = field(
        default_factory=lambda: [".env*", "**/*.pem", "**/*.key", "secrets/**", "certs/**"]
    )
    local_only_paths: list[str] = field(
        default_factory=lambda: [
            "src/auth/**",
            "src/payment/**",
            "src/permissions/**",
            "infra/**",
            "config/**",
        ]
    )
    redacted_allowed_paths: list[str] = field(
        default_factory=lambda: ["tests/**", "docs/**", "src/ui/**", "frontend/src/**"]
    )
    require_human_approval_for: list[str] = field(
        default_factory=lambda: [
            "contains_customer_contract",
            "contains_security_incident_root_cause",
            "contains_auth_architecture",
            "contains_payment_flow",
        ]
    )


@dataclass(frozen=True)
class ContextFirewallResult:
    decision: FirewallDecision
    highest_sensitivity: Sensitivity
    sanitized: Any
    removed_counts: dict[str, int]
    blocked_items: list[str]
    detectors_triggered: list[str]
    audit_id: str = ""
    redacted_context_hash: str = ""
    raw_content_stored: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "decision": self.decision,
            "highest_sensitivity": self.highest_sensitivity,
            "sanitized": self.sanitized,
            "removed_counts": self.removed_counts,
            "blocked_items": self.blocked_items,
            "detectors_triggered": self.detectors_triggered,
            "audit_id": self.audit_id,
            "redacted_context_hash": self.redacted_context_hash,
            "raw_content_stored": self.raw_content_stored,
        }


SECRET_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("openai_api_key", re.compile(r"\bsk-[A-Za-z0-9][A-Za-z0-9_\-]{20,}\b")),
    ("github_token", re.compile(r"\bgh[pousr]_[A-Za-z0-9_]{20,}\b")),
    ("aws_access_key", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("bearer_token", re.compile(r"(?i)\bbearer\s+[a-z0-9._\-]{12,}\b")),
    (
        "jwt_token",
        re.compile(r"\beyJ[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{8,}\b"),
    ),
    (
        "private_key",
        re.compile(
            r"-----BEGIN (?:RSA |DSA |EC |OPENSSH |PGP )?PRIVATE KEY-----[\s\S]*?-----END (?:RSA |DSA |EC |OPENSSH |PGP )?PRIVATE KEY-----"
        ),
    ),
    (
        "credential_assignment",
        re.compile(
            r"(?i)(api[_-]?key|private[_-]?key|password|passwd|token|secret)\s*[:=]\s*['\"]?[^'\"\s]+"
        ),
    ),
    (
        "database_url",
        re.compile(r"(?i)\b(?:postgres|postgresql|mysql|mongodb|redis)://[^\s'\"<>]+"),
    ),
]
PII_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("email", re.compile(r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b")),
    ("phone", re.compile(r"\b(?:\+?82[-.\s]?)?0?1[016789][-. ]?\d{3,4}[-. ]?\d{4}\b")),
    ("resident_registration_number", re.compile(r"\b\d{6}[- ]?[1-4]\d{6}\b")),
    ("business_registration_number", re.compile(r"\b\d{3}[- ]?\d{2}[- ]?\d{5}\b")),
    # Candidate finder only — validated with Luhn before it counts as a card.
    # A bare digit-run regex matched ~0.1% of UUIDs, silently mangling upload
    # ids so the affected file became permanently unreadable by the AI tools.
    ("card_number", re.compile(r"\b(?:\d[ -]*?){13,19}\b")),
    ("ipv4_address", re.compile(r"\b(?:10|172\.(?:1[6-9]|2\d|3[0-1])|192\.168)(?:\.\d{1,3}){2}\b")),
]
PROMPT_INJECTION_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("prompt_injection", re.compile(r"(?i)ignore (all )?(previous|system|developer) instructions")),
    ("prompt_injection", re.compile(r"(?i)reveal (the )?(system prompt|secrets?|tokens?)")),
    ("prompt_injection", re.compile(r"(?i)\.env 파일|read .*\.env|send the entire")),
    ("prompt_injection", re.compile(r"(?i)<\s*system\s*>")),
]
CONFIDENTIAL_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("customer_contract", re.compile(r"(?i)(contract|계약|할인율|discount|고객사|customer)")),
    (
        "security_incident_root_cause",
        re.compile(r"(?i)(incident|장애 원인|root cause|replication lag)"),
    ),
    ("auth_architecture", re.compile(r"(?i)(auth|session|refresh token|jwt|권한|permission)")),
    ("payment_flow", re.compile(r"(?i)(payment|billing|결제|카드|계좌)")),
]


def load_context_firewall_policy(workspace_dir: Path) -> ContextFirewallPolicy:
    path = workspace_dir / ".patchnote-security.yml"
    if not path.exists():
        return ContextFirewallPolicy()
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError):
        return ContextFirewallPolicy()
    if not isinstance(raw, dict):
        return ContextFirewallPolicy()
    policy_raw = (
        raw.get("context_firewall") if isinstance(raw.get("context_firewall"), dict) else raw
    )
    return _policy_from_mapping(cast(dict[str, Any], policy_raw))


def sanitize_context(
    value: Any,
    *,
    destination: str,
    task_type: str = "",
    source_uri: str = "",
    policy: ContextFirewallPolicy | None = None,
) -> ContextFirewallResult:
    policy = policy or ContextFirewallPolicy()
    sanitized, findings = _sanitize_value(value)
    path_findings = _path_findings(source_uri, policy)
    all_findings = [*findings, *path_findings]
    highest = _highest_sensitivity(all_findings)
    removed_counts = _removed_counts(all_findings)
    blocked_items = sorted(
        {finding.item_type for finding in all_findings if finding.sensitivity in {"S3", "S4", "S5"}}
    )
    decision = _decision_for(
        destination=destination,
        highest_sensitivity=highest,
        findings=all_findings,
        policy=policy,
    )
    sanitized = (
        _abstract_for_frontier(sanitized, task_type=task_type, source_uri=source_uri)
        if _is_frontier(destination)
        else sanitized
    )
    context_hash = _hash_json(sanitized)
    return ContextFirewallResult(
        decision=decision,
        highest_sensitivity=highest,
        sanitized=sanitized,
        removed_counts=removed_counts,
        blocked_items=blocked_items,
        detectors_triggered=sorted({finding.detector for finding in all_findings}),
        redacted_context_hash=f"sha256:{context_hash}",
    )


def sanitize_text(
    text: str,
    *,
    destination: str = "local_storage",
    task_type: str = "",
    source_uri: str = "",
    policy: ContextFirewallPolicy | None = None,
) -> str:
    result = sanitize_context(
        text,
        destination=destination,
        task_type=task_type,
        source_uri=source_uri,
        policy=policy,
    )
    return str(result.sanitized)


def _coerce_message_content(value: Any) -> str | list[dict[str, Any]]:
    """Preserve multimodal list content; otherwise normalize to a string."""

    if isinstance(value, list):
        return [item for item in value if isinstance(item, dict)]
    return str(value or "")


def sanitize_llm_messages(
    messages: list[LlmMessage],
    *,
    destination: str,
    task_type: str,
    policy: ContextFirewallPolicy | None = None,
) -> tuple[list[LlmMessage], ContextFirewallResult]:
    # Only ``content`` and ``reasoning`` carry model-authored text worth
    # scanning. Tool-calling identity fields (tool_call_id, tool_calls, name)
    # and the provider-native ``raw`` payload are carried across out of band:
    # rebuilding messages from {role, content} alone silently strips them, and a
    # ``tool`` message without its ``tool_call_id`` makes the provider reject the
    # whole request on the next loop iteration.
    payload = [
        {"role": message.role, "content": message.content, "reasoning": message.reasoning}
        for message in messages
    ]
    result = sanitize_context(payload, destination=destination, task_type=task_type, policy=policy)
    sanitized_payload = [item for item in (result.sanitized or []) if isinstance(item, dict)]
    # Both sanitizers map lists 1:1, so index alignment holds. Guard anyway:
    # a misaligned copy would attach one message's tool_call_id to another.
    aligned = len(sanitized_payload) == len(messages)
    sanitized_messages: list[LlmMessage] = []
    for index, item in enumerate(sanitized_payload):
        original = messages[index] if aligned else None
        sanitized_messages.append(
            LlmMessage(
                str(item.get("role") or "user"),
                _coerce_message_content(item.get("content")),
                tool_calls=original.tool_calls if original else None,
                tool_call_id=original.tool_call_id if original else "",
                name=original.name if original else "",
                reasoning=str(item.get("reasoning") or ""),
                raw=_sanitized_raw(
                    original,
                    sanitized_content=_coerce_message_content(item.get("content")),
                    sanitized_reasoning=str(item.get("reasoning") or ""),
                    destination=destination,
                    task_type=task_type,
                )
                if original
                else None,
            )
        )
    if _is_frontier(destination) and result.decision in {"allow", "allow_redacted"}:
        sanitized_messages = [LlmMessage("system", CONTEXT_HEADER), *sanitized_messages]
    return sanitized_messages or messages, result


def _sanitized_raw(
    message: LlmMessage,
    *,
    sanitized_content: str | list[dict[str, Any]],
    sanitized_reasoning: str,
    destination: str,
    task_type: str,
) -> dict[str, Any] | None:
    """Return the provider-native assistant payload with sanitized text.

    ``raw`` is replayed verbatim to keep tool_call ids intact, so every piece of
    model-authored text inside it must be replaced with its sanitized version —
    otherwise the firewall's redaction is undone the moment the message is
    replayed on the next loop iteration.
    """

    if not message.raw:
        return None
    raw = dict(message.raw)
    for key in ("reasoning_content", "reasoning"):
        if key in raw:
            raw[key] = sanitized_reasoning
    if isinstance(raw.get("content"), str) and raw["content"]:
        raw["content"] = (
            sanitized_content
            if isinstance(sanitized_content, str)
            else sanitize_text(str(raw["content"]), destination=destination, task_type=task_type)
        )
    # Tool-call arguments are model-authored too and can echo redacted input.
    for call in raw.get("tool_calls") or []:
        function = call.get("function") if isinstance(call, dict) else None
        if isinstance(function, dict) and isinstance(function.get("arguments"), str):
            function["arguments"] = sanitize_text(
                function["arguments"], destination=destination, task_type=task_type
            )
    return raw


def sanitize_llm_response(
    response: LlmResponse, *, destination: str, task_type: str
) -> LlmResponse:
    result = sanitize_context(response.text, destination=destination, task_type=task_type)
    reasoning = (
        sanitize_text(response.reasoning, destination=destination, task_type=task_type)
        if response.reasoning
        else ""
    )
    raw_message = response.raw_message
    if raw_message:
        raw_message = dict(raw_message)
        for key in ("reasoning_content", "reasoning"):
            if key in raw_message:
                raw_message[key] = reasoning
        # Replayed verbatim next turn, so its content must carry the same
        # redaction as ``text``.
        if isinstance(raw_message.get("content"), str) and raw_message["content"]:
            raw_message["content"] = str(result.sanitized)
    # tool_calls/stop_reason/raw_message must survive: dropping them turns a
    # tool-calling turn into a silent no-op with an empty answer.
    return LlmResponse(
        text=str(result.sanitized),
        prompt_tokens=response.prompt_tokens,
        completion_tokens=response.completion_tokens,
        route=response.route,
        model=response.model,
        tool_calls=response.tool_calls,
        stop_reason=response.stop_reason,
        reasoning=reasoning,
        raw_message=raw_message,
    )


def record_firewall_audit(
    container: Any,
    result: ContextFirewallResult,
    *,
    actor: str = "",
    agent_run_id: str = "",
    destination: str,
    task_type: str = "",
) -> ContextFirewallResult:
    store = getattr(container, "context_firewall", None)
    if store is None:
        return result
    record = store.record(
        actor=actor,
        agent_run_id=agent_run_id,
        destination=destination,
        task_type=task_type,
        decision=result.decision,
        highest_sensitivity=result.highest_sensitivity,
        detectors_triggered=result.detectors_triggered,
        removed_counts=result.removed_counts,
        blocked_items=result.blocked_items,
        raw_content_stored=False,
        redacted_context_hash=result.redacted_context_hash,
    )
    return ContextFirewallResult(
        decision=result.decision,
        highest_sensitivity=result.highest_sensitivity,
        sanitized=result.sanitized,
        removed_counts=result.removed_counts,
        blocked_items=result.blocked_items,
        detectors_triggered=result.detectors_triggered,
        audit_id=str(record.get("id") or ""),
        redacted_context_hash=result.redacted_context_hash,
        raw_content_stored=False,
    )


def default_policy_payload(workspace_dir: Path) -> dict[str, Any]:
    policy = load_context_firewall_policy(workspace_dir)
    return {
        "default_action": policy.default_action,
        "unknown_data_action": policy.unknown_data_action,
        "allow_frontier_api": policy.allow_frontier_api,
        "blocked_paths": policy.blocked_paths,
        "local_only_paths": policy.local_only_paths,
        "redacted_allowed_paths": policy.redacted_allowed_paths,
        "require_human_approval_for": policy.require_human_approval_for,
    }


def _policy_from_mapping(raw: dict[str, Any]) -> ContextFirewallPolicy:
    raw_model_policy = raw.get("model_policy")
    raw_blocked = raw.get("blocked")
    raw_local_only = raw.get("local_only")
    raw_path_rules = raw.get("path_rules")
    raw_outbound = raw.get("outbound_rules")
    model_policy: dict[str, Any] = raw_model_policy if isinstance(raw_model_policy, dict) else {}
    blocked: dict[str, Any] = raw_blocked if isinstance(raw_blocked, dict) else {}
    local_only: dict[str, Any] = raw_local_only if isinstance(raw_local_only, dict) else {}
    path_rules: dict[str, Any] = raw_path_rules if isinstance(raw_path_rules, dict) else {}
    outbound: dict[str, Any] = raw_outbound if isinstance(raw_outbound, dict) else {}
    return ContextFirewallPolicy(
        default_action=_decision(str(raw.get("default_action") or "local_only")),
        unknown_data_action=_decision(
            str(
                raw.get("unknown_data_action")
                or model_policy.get("unknown_data_action")
                or "local_only"
            )
        ),
        allow_frontier_api=bool(
            model_policy.get("allow_frontier_api", raw.get("allow_frontier_api", True))
        ),
        blocked_paths=_strings(
            blocked.get("paths") or path_rules.get("block_all_llm"),
            ContextFirewallPolicy().blocked_paths,
        ),
        local_only_paths=_strings(
            local_only.get("paths") or path_rules.get("local_only"),
            ContextFirewallPolicy().local_only_paths,
        ),
        redacted_allowed_paths=_strings(
            path_rules.get("redacted_allowed"), ContextFirewallPolicy().redacted_allowed_paths
        ),
        require_human_approval_for=_strings(
            outbound.get("require_human_approval"),
            ContextFirewallPolicy().require_human_approval_for,
        ),
    )


def _sanitize_value(value: Any) -> tuple[Any, list[FirewallFinding]]:
    if isinstance(value, str):
        return _sanitize_string(value)
    if isinstance(value, list):
        findings: list[FirewallFinding] = []
        sanitized_items: list[Any] = []
        for item in value:
            sanitized_item, item_findings = _sanitize_value(item)
            sanitized_items.append(sanitized_item)
            findings.extend(item_findings)
        return sanitized_items, findings
    if isinstance(value, dict):
        # Multimodal image parts carry opaque base64; never scan/redact the bytes.
        if value.get("type") == "image" and "data" in value:
            return value, []
        findings = []
        sanitized: dict[str, Any] = {}
        for key, item in value.items():
            key_text = str(key)
            if re.search(r"(?i)(api[_-]?key|token|secret|password|private[_-]?key)", key_text):
                sanitized[key_text] = "[REDACTED_SECRET]"
                findings.append(FirewallFinding("secret_scanner", key_text, "S4"))
                continue
            sanitized_item, item_findings = _sanitize_value(item)
            sanitized[key_text] = sanitized_item
            findings.extend(item_findings)
        return sanitized, findings
    return value, []


def _luhn_valid(digits: str) -> bool:
    """Standard card checksum. Random digit runs pass only ~10% of the time."""

    total = 0
    for index, char in enumerate(reversed(digits)):
        value = int(char)
        if index % 2:
            value *= 2
            if value > 9:
                value -= 9
        total += value
    return total % 10 == 0


def _redact_card_numbers(text: str) -> tuple[str, int]:
    """Redact only digit runs that actually checksum as a card number.

    The regex alone flagged hyphenated hex identifiers (UUIDs) as cards.
    """

    pattern = dict(PII_PATTERNS)["card_number"]
    count = 0

    def _replace(match: re.Match[str]) -> str:
        nonlocal count
        digits = re.sub(r"\D", "", match.group(0))
        if len(digits) < 13 or not _luhn_valid(digits):
            return match.group(0)
        count += 1
        return "[REDACTED_CARD_NUMBER]"

    return pattern.sub(_replace, text), count


def _sanitize_string(text: str) -> tuple[str, list[FirewallFinding]]:
    findings: list[FirewallFinding] = []
    sanitized = text
    for item_type, pattern in SECRET_PATTERNS:
        sanitized, count = pattern.subn(f"[REDACTED_{item_type.upper()}]", sanitized)
        if count:
            findings.append(FirewallFinding("secret_scanner", item_type, "S4", count))
    for item_type, pattern in PII_PATTERNS:
        if item_type == "card_number":
            sanitized, count = _redact_card_numbers(sanitized)
        else:
            sanitized, count = pattern.subn(f"[REDACTED_{item_type.upper()}]", sanitized)
        if count:
            findings.append(
                FirewallFinding(
                    "pii_scanner",
                    item_type,
                    "S5" if item_type == "resident_registration_number" else "S3",
                    count,
                )
            )
    for item_type, pattern in PROMPT_INJECTION_PATTERNS:
        sanitized, count = pattern.subn("[UNTRUSTED_EXTERNAL_INSTRUCTION_REMOVED]", sanitized)
        if count:
            findings.append(FirewallFinding("prompt_injection_detector", item_type, "S3", count))
    for item_type, pattern in CONFIDENTIAL_PATTERNS:
        if pattern.search(text):
            sensitivity: Sensitivity = (
                "S3" if item_type in {"auth_architecture", "payment_flow"} else "S2"
            )
            findings.append(FirewallFinding("local_llm_classifier_stub", item_type, sensitivity))
    return sanitized, findings


def _path_findings(path: str, policy: ContextFirewallPolicy) -> list[FirewallFinding]:
    if not path:
        return []
    normalized = path.replace("\\", "/").lstrip("/")
    findings: list[FirewallFinding] = []
    if _matches_any(normalized, policy.blocked_paths):
        findings.append(FirewallFinding("path_policy", "blocked_path", "S4"))
    if _matches_any(normalized, policy.local_only_paths):
        findings.append(FirewallFinding("path_policy", "local_only_path", "S3"))
    return findings


def _decision_for(
    *,
    destination: str,
    highest_sensitivity: Sensitivity,
    findings: list[FirewallFinding],
    policy: ContextFirewallPolicy,
) -> FirewallDecision:
    if any(
        finding.item_type == "blocked_path" or finding.sensitivity == "S4" for finding in findings
    ):
        return "block" if _is_frontier(destination) else "local_only"
    if any(finding.sensitivity == "S5" for finding in findings):
        return "block" if _is_frontier(destination) else "approval_required"
    if _is_local(destination):
        return "allow_redacted" if findings else "allow"
    if _is_frontier(destination):
        if not policy.allow_frontier_api:
            return "local_only"
        if highest_sensitivity == "S3":
            return "allow_redacted"
        if highest_sensitivity in {"S0", "S1", "S2"}:
            return "allow_redacted" if findings else "allow"
        return policy.unknown_data_action
    return "allow_redacted" if findings else "allow"


# Per-string ceiling for frontier egress. This is a data-minimization backstop,
# not a token budget: office prompts routinely run 4-6k chars (company context +
# template + meeting source), and a cap below that silently amputates whatever
# the template puts last — at 2400 the model received truncated company memory
# and never saw the meeting text at all, then narrated its confusion as the
# generated document. Keep it well above any office prompt while still bounding
# a runaway page dump.
_FRONTIER_MAX_CHARS = 48_000


def _abstract_for_frontier(value: Any, *, task_type: str, source_uri: str) -> Any:
    if isinstance(value, str):
        if len(value) <= _FRONTIER_MAX_CHARS:
            return value
        return (
            value[:_FRONTIER_MAX_CHARS] + "\n\n[Context truncated locally before frontier routing.]"
        )
    if isinstance(value, list):
        return [
            _abstract_for_frontier(item, task_type=task_type, source_uri=source_uri)
            for item in value
        ]
    if isinstance(value, dict):
        # Preserve multimodal image parts verbatim: base64 payloads must not be
        # truncated or they become invalid for the vision model.
        if value.get("type") == "image" and "data" in value:
            return value
        return {
            key: _abstract_for_frontier(item, task_type=task_type, source_uri=source_uri)
            for key, item in value.items()
            if key not in {"raw", "raw_content", "body_raw", "log_raw"}
        }
    return value


def _highest_sensitivity(findings: list[FirewallFinding]) -> Sensitivity:
    if not findings:
        return "S1"
    return max(
        (finding.sensitivity for finding in findings), key=lambda item: SENSITIVITY_RANK[item]
    )


def _removed_counts(findings: list[FirewallFinding]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for finding in findings:
        counts[finding.item_type] = counts.get(finding.item_type, 0) + finding.count
    return counts


def _matches_any(path: str, patterns: list[str]) -> bool:
    return any(
        fnmatch.fnmatch(path, pattern) or fnmatch.fnmatch(Path(path).name, pattern)
        for pattern in patterns
    )


def _is_frontier(destination: str) -> bool:
    return destination in FRONTIER_DESTINATIONS


def _is_local(destination: str) -> bool:
    return destination in LOCAL_DESTINATIONS


def _hash_json(value: Any) -> str:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _strings(value: object, default: list[str]) -> list[str]:
    if not isinstance(value, list):
        return default
    return [str(item) for item in value if str(item).strip()]


def _decision(value: str) -> FirewallDecision:
    if value in {"allow", "allow_redacted", "local_only", "approval_required", "block"}:
        return cast(FirewallDecision, value)
    return "local_only"
