"""Payloads for the MCP hub HTTP surface."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class McpToolCallPayload(BaseModel):
    arguments: dict[str, Any] = Field(default_factory=dict)


class McpToolDescriptorPayload(BaseModel):
    name: str
    description: str
    input_schema: dict[str, Any] = Field(default_factory=dict)
    required_permission: str = "work:read"
