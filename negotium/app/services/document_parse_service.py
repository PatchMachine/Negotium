"""Upstage Document Parse client: office file → markdown, with a sidecar cache.

Called only from the cloud attachment route — the caller is responsible for
never invoking this on the local route (the file bytes leave the machine).
Results are cached next to the upload (``<file>.parsed.md``) so repeated chat
turns over the same attachment are not billed again; uploads are immutable,
which makes the path-keyed cache safe.
"""

from __future__ import annotations

import contextlib
from pathlib import Path

import httpx

DOCUMENT_PARSE_MAX_BYTES = 50 * 1024 * 1024
_TIMEOUT_SECONDS = 60.0

_MIME_BY_SUFFIX = {
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".hwp": "application/octet-stream",
    ".hwpx": "application/octet-stream",
}


def digitization_url(solar_base_url: str) -> str:
    """``https://api.upstage.ai/v1`` → ``https://api.upstage.ai/v1/document-digitization``."""
    return solar_base_url.rstrip("/") + "/document-digitization"


def cached_parse_path(path: Path) -> Path:
    return Path(f"{path}.parsed.md")


def read_cached_parse(path: Path) -> str | None:
    sidecar = cached_parse_path(path)
    try:
        if sidecar.exists():
            content = sidecar.read_text(encoding="utf-8")
            return content if content.strip() else None
    except OSError:
        return None
    return None


def write_cached_parse(path: Path, markdown: str) -> None:
    # Cache is best-effort; the parse result is still returned on write failure.
    with contextlib.suppress(OSError):
        cached_parse_path(path).write_text(markdown, encoding="utf-8")


async def parse_document_via_api(
    path: Path, *, api_key: str, base_url: str, timeout: float = _TIMEOUT_SECONDS
) -> tuple[str | None, str]:
    """Returns ``(markdown, "")`` on success, ``(None, reason)`` on failure. Never raises."""
    try:
        size = path.stat().st_size
    except OSError as exc:
        return None, f"파일을 읽지 못했습니다: {exc}"
    if size > DOCUMENT_PARSE_MAX_BYTES:
        return None, "파일이 50MB 제한을 초과합니다."

    mime = _MIME_BY_SUFFIX.get(path.suffix.lower(), "application/octet-stream")
    try:
        payload_bytes = path.read_bytes()
    except OSError as exc:
        return None, f"파일을 읽지 못했습니다: {exc}"

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(
                digitization_url(base_url),
                headers={"Authorization": f"Bearer {api_key}"},
                files={"document": (path.name, payload_bytes, mime)},
                data={
                    "model": "document-parse",
                    "output_formats": '["markdown"]',
                    "ocr": "auto",
                    "coordinates": "false",
                },
            )
    except httpx.HTTPError as exc:
        return None, f"Document Parse 호출 실패: {exc}"
    if response.status_code >= 400:
        return None, f"Document Parse 오류(status {response.status_code})"
    try:
        body = response.json()
    except ValueError:
        return None, "Document Parse 응답을 해석하지 못했습니다."
    content = body.get("content") if isinstance(body, dict) else None
    markdown = content.get("markdown") if isinstance(content, dict) else None
    if not isinstance(markdown, str) or not markdown.strip():
        return None, "응답에 markdown이 없습니다."
    return markdown, ""


async def parse_office_document(
    path: Path, *, api_key: str, base_url: str
) -> tuple[str | None, str]:
    """Cache read → API call → cache write; same return contract as the API call."""
    cached = read_cached_parse(path)
    if cached is not None:
        return cached, ""
    markdown, reason = await parse_document_via_api(path, api_key=api_key, base_url=base_url)
    if markdown is not None:
        write_cached_parse(path, markdown)
    return markdown, reason


__all__ = [
    "DOCUMENT_PARSE_MAX_BYTES",
    "cached_parse_path",
    "digitization_url",
    "parse_document_via_api",
    "parse_office_document",
    "read_cached_parse",
    "write_cached_parse",
]
