"""Application (use-case) layer.

Coordinates domain objects and downstream ports. Has no knowledge of specific
adapter technologies (FastAPI, discord.py, OpenAI, ...).
"""

from patch_machine.application.event_bus import EventBus, QueueFullError
from patch_machine.application.orchestrator import Orchestrator

__all__ = ["EventBus", "Orchestrator", "QueueFullError"]
