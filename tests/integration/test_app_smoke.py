"""Smoke test: FastAPI app factory + /health returns bus metrics."""

from __future__ import annotations

from fastapi.testclient import TestClient

from patch_machine.app.container import Container
from patch_machine.app.main import create_app


def test_health_endpoint_reports_queue_state() -> None:
    container = Container.build()
    app = create_app(container)
    with TestClient(app) as client:
        response = client.get("/health")
        assert response.status_code == 200
        payload = response.json()
        assert payload["ok"] is True
        assert payload["queue_capacity"] == container.bus.capacity
        assert "metrics" in payload
