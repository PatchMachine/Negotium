"""Core domain value objects.

These types are the canonical contract between layers. They must stay free of
framework and I/O concerns.
"""

from __future__ import annotations

from typing import Literal

LlmRoute = Literal["cloud", "local"]
