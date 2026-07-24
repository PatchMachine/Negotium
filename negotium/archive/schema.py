"""Markdown front-matter utilities for archive documents."""

from __future__ import annotations

from typing import Any

import yaml


def parse_front_matter(markdown: str) -> dict[str, Any]:
    """Utility to read front matter from an existing log (used by indexes)."""
    if not markdown.startswith("---"):
        return {}
    end = markdown.find("\n---", 3)
    if end == -1:
        return {}
    block = markdown[3:end].strip()
    loaded = yaml.safe_load(block) or {}
    if not isinstance(loaded, dict):
        return {}
    return loaded
