"""vLLM adapter — **Phase 4 stub**.

Kept as a placeholder so ``LlmProvider`` routing code can reference it today.
Attempting to use it immediately raises ``NotImplementedError`` to make the
missing wiring obvious.
"""

from __future__ import annotations

from collections.abc import Sequence

from patch_machine.domain.entities import LlmRoute
from patch_machine.domain.ports import LlmMessage, LlmProvider, LlmResponse


class VllmProvider(LlmProvider):
    def __init__(self, *, base_url: str) -> None:
        self._base_url = base_url

    async def complete(
        self,
        messages: Sequence[LlmMessage],
        *,
        route: LlmRoute = "local",
        temperature: float = 0.0,
        max_tokens: int | None = None,
    ) -> LlmResponse:
        raise NotImplementedError("VllmProvider is a Phase 4 stub")
