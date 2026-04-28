"""FastAPI entry point — webhook ingestion + background orchestrator + Discord bot."""

from __future__ import annotations

import asyncio
import contextlib
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from patch_machine.app.container import Container
from patch_machine.observability import get_logger


def create_app(container: Container | None = None) -> FastAPI:
    container = container or Container.build()
    log = get_logger(component="app")
    orchestrator_task: asyncio.Task[None] | None = None

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        nonlocal orchestrator_task
        log.info("app.startup")
        orchestrator_task = asyncio.create_task(
            container.orchestrator.run_forever(container.bus),
            name="orchestrator",
        )
        await container.discord.start()
        try:
            yield
        finally:
            log.info("app.shutdown")
            await container.discord.stop()
            if orchestrator_task is not None:
                orchestrator_task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await orchestrator_task

    app = FastAPI(title="Patch Machine", version="0.1.0", lifespan=lifespan)
    app.include_router(container.github_router.router)

    @app.get("/health")
    async def health() -> dict[str, object]:
        return {
            "ok": True,
            "queue_size": container.bus.size,
            "queue_capacity": container.bus.capacity,
            "metrics": container.metrics.snapshot(),
        }

    return app


app = create_app
