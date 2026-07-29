"""Serve the built React console from the backend process.

The console and the API share a single origin and port (``NG_HTTP_PORT``), so
there is one URL to open and no CORS/proxy layer between them. The Vite dev
server is optional and only used for hot module replacement while editing the
frontend; it proxies back to this same backend.

The build output directory is ``frontend/dist`` by default and can be pointed
elsewhere with ``NG_FRONTEND_DIST`` (useful when the console is built in a
separate image layer, as the Dockerfile does).

Mechanism: ``/assets`` is a normal ``StaticFiles`` mount (conditional GETs,
ranges, threadpool stat all come for free), and the SPA shell is served from
the app's 404 handler — only for GET/HEAD requests that matched *no* route.
Normal routing, method dispatch (405s), and trailing-slash redirects therefore
keep working exactly as they would without a frontend.
"""

from __future__ import annotations

import os
import stat as stat_lib
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exception_handlers import http_exception_handler
from fastapi.responses import FileResponse, HTMLResponse, Response
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.staticfiles import StaticFiles

from negotium.archive._paths import resolve_within

# Cache tiers (the whole policy, in one place):
#   assets/*   — content-hashed filenames, safe to cache forever
#   other dist files (logo, …) — unhashed, cache briefly
#   index.html — the manifest pointing at the hashes; always revalidate
#   not-built page — transient state, never cache
_ASSET_CACHE = "public, max-age=31536000, immutable"
_FILE_CACHE = "public, max-age=3600"
_SHELL_CACHE = "no-cache"

# Namespaces where a miss must stay a real 404: /api callers expect JSON, and
# HTML in place of a missing bundle would execute as a broken script.
_NO_FALLBACK = ("/api", "/assets")

_NOT_BUILT_HTML = """
<!doctype html>
<html lang="ko">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Negotium | 콘솔 빌드 필요</title></head>
<body style="font-family: ui-sans-serif, system-ui, sans-serif; max-width: 42rem; margin: 4rem auto; padding: 0 1rem; line-height: 1.7;">
  <h1>콘솔이 아직 빌드되지 않았습니다.</h1>
  <p>백엔드는 정상 동작 중입니다. 프론트엔드를 한 번 빌드하면 이 주소에서 콘솔이 열립니다.</p>
  <pre style="background: #f3f4f6; padding: 1rem; border-radius: 8px; overflow-x: auto;">npm install --prefix frontend
npm run build --prefix frontend</pre>
  <p><code>negotium serve --build-frontend</code> 로 실행하면 위 빌드를 자동으로 수행합니다.</p>
  <p>API 문서는 <a href="/docs">/docs</a>, 상태 확인은 <a href="/health">/health</a> 에서 확인하세요.</p>
</body>
</html>
""".strip()


def default_frontend_dist() -> Path:
    """Repo-relative location of ``npm run build --prefix frontend`` output."""
    return Path(__file__).resolve().parents[2] / "frontend" / "dist"


class _ImmutableAssets(StaticFiles):
    """``dist/assets`` files carry content hashes, so they can cache forever."""

    def file_response(self, *args: Any, **kwargs: Any) -> Response:
        response = super().file_response(*args, **kwargs)
        response.headers["Cache-Control"] = _ASSET_CACHE
        return response


def _dist_file(dist: Path, relative: str) -> tuple[Path, os.stat_result] | None:
    """Stat ``relative`` inside ``dist``; ``None`` on miss, escape, or non-file."""
    try:
        target = resolve_within(dist, relative)
        result = target.stat()
    except (ValueError, OSError):
        return None
    if not stat_lib.S_ISREG(result.st_mode):
        return None
    return target, result


def _console_response(dist: Path) -> Response:
    """The SPA shell, or build instructions when ``dist`` has no build yet."""
    index_html = dist / "index.html"
    try:
        result = index_html.stat()
    except OSError:
        return HTMLResponse(_NOT_BUILT_HTML, headers={"Cache-Control": "no-store"})
    return FileResponse(index_html, stat_result=result, headers={"Cache-Control": _SHELL_CACHE})


def install_console(app: FastAPI, dist_dir: Path | None) -> None:
    """Mount the console onto ``app`` (assets + SPA fallback for 404s).

    The dist tree is re-checked per request rather than cached, so rebuilding
    the frontend is picked up without restarting the backend.
    """

    dist = (dist_dir if dist_dir is not None else default_frontend_dist()).resolve()
    app.mount("/assets", _ImmutableAssets(directory=dist / "assets", check_dir=False))

    @app.exception_handler(StarletteHTTPException)
    async def _spa_fallback(request: Request, exc: StarletteHTTPException) -> Response:
        path = request.url.path
        if (
            exc.status_code == 404
            and request.method in ("GET", "HEAD")
            # Only when no route matched at all — an endpoint's own 404
            # (e.g. "document not found") must keep its JSON body.
            and request.scope.get("endpoint") is None
            and not any(path == p or path.startswith(p + "/") for p in _NO_FALLBACK)
        ):
            found = _dist_file(dist, path.lstrip("/")) if path.strip("/") else None
            if found is not None:
                target, result = found
                return FileResponse(
                    target, stat_result=result, headers={"Cache-Control": _FILE_CACHE}
                )
            return _console_response(dist)
        return await http_exception_handler(request, exc)
