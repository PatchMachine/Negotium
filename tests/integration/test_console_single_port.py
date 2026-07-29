"""The console SPA and the API are served from the same FastAPI app/port."""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from negotium.app.console_site import _dist_file
from negotium.app.container import Container
from negotium.app.main import create_app
from negotium.app.settings import Settings


def _client(tmp_path: Path, dist: Path | None) -> TestClient:
    container = Container.build(
        Settings(
            env="test",
            archive_dir=tmp_path / "archive",
            workspace_dir=tmp_path / "workspaces",
            frontend_dist=dist,
        )
    )
    return TestClient(create_app(container))


def _build_dist(tmp_path: Path) -> Path:
    dist = tmp_path / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text("<html><div id=root></div></html>", encoding="utf-8")
    (dist / "assets" / "index-abc123.js").write_text("console.log(1)", encoding="utf-8")
    (dist / "negotium-logo.png").write_bytes(b"\x89PNG fake")
    return dist


def test_console_and_api_share_one_port(tmp_path: Path) -> None:
    with _client(tmp_path, _build_dist(tmp_path)) as client:
        index = client.get("/")
        asset = client.get("/assets/index-abc123.js")
        logo = client.get("/negotium-logo.png")
        health = client.get("/health")

    assert index.status_code == 200
    assert "id=root" in index.text
    assert index.headers["cache-control"] == "no-cache"
    assert asset.status_code == 200
    # Hashed build artifacts are safe to cache forever; unhashed files briefly.
    assert "immutable" in asset.headers["cache-control"]
    assert logo.status_code == 200
    assert logo.headers["cache-control"] == "public, max-age=3600"
    assert health.status_code == 200 and health.json()["ok"] is True


def test_fallback_serves_spa_without_breaking_routing_semantics(tmp_path: Path) -> None:
    with _client(tmp_path, _build_dist(tmp_path)) as client:
        deep_link = client.get("/work-schedule")
        missing_api = client.get("/api/definitely-not-a-route")
        missing_api_post = client.post("/api/definitely-not-a-route")
        missing_asset = client.get("/assets/nope.js")
        slash_redirect = client.get("/contribute/", follow_redirects=False)

    assert deep_link.status_code == 200
    assert "id=root" in deep_link.text
    # API misses stay JSON 404s for every method, never an HTML body.
    assert missing_api.status_code == 404
    assert missing_api.json()["detail"] == "Not Found"
    assert missing_api_post.status_code == 404
    # A missing bundle must 404 rather than execute the shell as a script.
    assert missing_asset.status_code == 404
    # The fallback must not shadow Starlette's trailing-slash redirects.
    assert slash_redirect.status_code in (301, 307)


def test_asset_path_cannot_escape_the_dist_directory(tmp_path: Path) -> None:
    # HTTP clients normalize `..` away, so exercise the guard directly.
    dist = _build_dist(tmp_path)
    (tmp_path / "secret.txt").write_text("nope", encoding="utf-8")

    assert _dist_file(dist, "../secret.txt") is None
    assert _dist_file(dist, "index.html") is not None


def test_missing_build_explains_how_to_build_instead_of_500(tmp_path: Path) -> None:
    with _client(tmp_path, tmp_path / "never-built") as client:
        response = client.get("/")

    assert response.status_code == 200
    assert "npm run build --prefix frontend" in response.text
    # Never cached: it must disappear on the next load after a build.
    assert response.headers["cache-control"] == "no-store"
