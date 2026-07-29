"""Shared archive-corpus rules: which files are retrievable memory sources.

Extracted from ``permanent_memory`` so the search index can share the exact
same corpus definition without a circular import
(``permanent_memory → search_index → _corpus``).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Literal

SourceKind = Literal[
    "patch_log",
    "audit_log",
    "document",
    "conversation",
    "promoted_memory",
    "upload",
    "token_usage",
    "unknown",
]

FULL_TEXT_CHAR_CAP = 48_000


def kind_for(path: Path, archive_dir: Path) -> SourceKind:
    try:
        rel = path.relative_to(archive_dir)
    except ValueError:
        return "unknown"
    parts = rel.parts
    if len(parts) >= 3 and parts[0].isdigit() and parts[1].isdigit() and path.suffix == ".md":
        return "patch_log"
    if parts and parts[0] == "conversations" and path.suffix == ".jsonl":
        return "conversation"
    if parts[:2] == ("memory", "promoted") and path.suffix == ".md":
        return "promoted_memory"
    if (
        parts
        and parts[0] == "uploads"
        and path.suffix in {".md", ".markdown", ".txt", ".json", ".jsonl", ".yaml", ".yml"}
    ):
        return "upload"
    if (
        parts
        and parts[0] in {"documents", "hr", "handover", "work_architecture"}
        and path.suffix in {".md", ".jsonl"}
    ):
        return "document"
    return "unknown"


def is_operational_internal_file(path: Path, archive_dir: Path) -> bool:
    try:
        rel = path.relative_to(archive_dir)
    except ValueError:
        return True
    parts = rel.parts
    # search_index holds the derived retrieval cache itself — indexing it
    # would make the index its own corpus. .git is the nested backup repo.
    return rel.as_posix() == "audit_log.jsonl" or bool(
        parts
        and parts[0] in {"token_usage", "context_firewall", "mcp_hub", "search_index", ".git"}
    )


def tombstoned_source_ids(archive_dir: Path) -> set[str]:
    path = archive_dir / "memory" / "tombstones.jsonl"
    if not path.exists():
        return set()
    tombstoned: set[str] = set()
    try:
        lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
    except OSError:
        return tombstoned
    for line in lines:
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(payload, dict):
            continue
        for key in ("target_id", "source_path"):
            value = str(payload.get(key) or "").strip().lstrip("/")
            if value:
                tombstoned.add(value)
    return tombstoned


def title_for(path: Path, text: str) -> str:
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            return stripped.lstrip("#").strip()
    return path.stem


def read_full_text(path: Path, *, max_chars: int = FULL_TEXT_CHAR_CAP) -> str:
    """Full retrievable text of a source (unlike the 600-char excerpt path)."""
    try:
        if path.suffix == ".jsonl":
            lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
            rendered: list[str] = []
            total = 0
            for line in lines:
                try:
                    payload = json.loads(line)
                    piece = str(payload.get("content") or payload.get("action") or payload)
                except (json.JSONDecodeError, AttributeError):
                    piece = line
                rendered.append(piece)
                total += len(piece) + 1
                if total >= max_chars:
                    break
            return "\n".join(rendered)[:max_chars]
        return path.read_text(encoding="utf-8", errors="ignore")[:max_chars]
    except OSError:
        return ""
