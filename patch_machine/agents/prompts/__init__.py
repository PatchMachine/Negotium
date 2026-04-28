"""Prompt templates rendered at runtime via Jinja2."""

from __future__ import annotations

from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined

_PROMPT_DIR = Path(__file__).resolve().parent
_env = Environment(
    loader=FileSystemLoader(_PROMPT_DIR),
    undefined=StrictUndefined,
    keep_trailing_newline=True,
    autoescape=False,
)


def render(name: str, **context: object) -> str:
    template = _env.get_template(name)
    return template.render(**context)
