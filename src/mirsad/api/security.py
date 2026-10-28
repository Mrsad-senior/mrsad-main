"""HTTP hardening: security headers (incl. CSP) and a request body size limit.

Both are pure ASGI middlewares so they also cover mounted sub-applications (e.g. ``/mcp``)
and streaming responses without buffering.
"""

from __future__ import annotations

import json
import logging

from fastapi import HTTPException
from starlette.types import ASGIApp, Message, Receive, Scope, Send

log = logging.getLogger("mirsad.api")

MAX_BODY_BYTES = 1024 * 1024

# The built SPA is served from 'self' only (Vite emits external module scripts and CSS files).
# 'unsafe-inline' for styles only: React/Vite may set inline style attributes; scripts stay strict.
APP_CSP = (
    "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; "
    "font-src 'self' data:; connect-src 'self'; worker-src 'self'; manifest-src 'self'; object-src 'none'; "
    "base-uri 'self'; form-action 'self'; frame-ancestors 'none'"
)
# Swagger UI / ReDoc pages are rendered by FastAPI with an inline bootstrap script and CDN assets.
DOCS_CSP = (
    "default-src 'self'; script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
    "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://fonts.googleapis.com; "
    "img-src 'self' data: https://fastapi.tiangolo.com https://cdn.redoc.ly; font-src 'self' https://fonts.gstatic.com; "
    "connect-src 'self'; worker-src 'self' blob:; object-src 'none'; base-uri 'self'; frame-ancestors 'none'"
)
DOCS_PATHS = ("/docs", "/redoc")


class SecurityHeadersMiddleware:
    """Adds CSP, nosniff, frame denial, referrer policy and no-store caching for API responses."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        path: str = scope.get("path", "")
        csp = DOCS_CSP if path.startswith(DOCS_PATHS) else APP_CSP
        is_api = path.startswith(("/api/", "/v1/", "/mcp"))

        async def send_wrapper(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = [(k, v) for k, v in message.get("headers", [])
                           if k.lower() not in (b"x-frame-options", b"x-content-type-options")]
                existing = {k.lower() for k, _ in headers}
                headers += [
                    (b"x-content-type-options", b"nosniff"),
                    (b"x-frame-options", b"DENY"),
                    (b"referrer-policy", b"no-referrer"),
                    (b"cross-origin-opener-policy", b"same-origin"),
                    (b"permissions-policy", b"camera=(), microphone=(), geolocation=(), payment=()"),
                ]
                if b"content-security-policy" not in existing:
                    headers.append((b"content-security-policy", csp.encode()))
                if is_api and b"cache-control" not in existing:
                    headers.append((b"cache-control", b"no-store"))
                if scope.get("scheme") == "https":
                    headers.append((b"strict-transport-security", b"max-age=31536000; includeSubDomains"))
                message["headers"] = headers
            await send(message)

        await self.app(scope, receive, send_wrapper)


class _BodyTooLarge(HTTPException):
    """Raised from ``receive``; an HTTPException so FastAPI re-raises it instead of mapping it to 400."""

    def __init__(self, limit: int) -> None:
        super().__init__(status_code=413, detail=f"Request body too large (limit {limit} bytes)")


class BodyLimitMiddleware:
    """Rejects request bodies larger than ``max_bytes`` with 413 (declared or streamed)."""

    def __init__(self, app: ASGIApp, max_bytes: int = MAX_BODY_BYTES) -> None:
        self.app = app
        self.max_bytes = max_bytes

    async def _reject(self, send: Send) -> None:
        body = json.dumps({"detail": f"Request body too large (limit {self.max_bytes} bytes)"}).encode()
        await send({"type": "http.response.start", "status": 413,
                    "headers": [(b"content-type", b"application/json"), (b"content-length", str(len(body)).encode())]})
        await send({"type": "http.response.body", "body": body})

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        for key, value in scope.get("headers", []):
            if key == b"content-length":
                try:
                    declared = int(value)
                except ValueError:
                    declared = -1
                if declared > self.max_bytes or declared < 0:
                    await self._reject(send)
                    return

        received = 0
        started = False

        async def limited_receive() -> Message:
            nonlocal received
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > self.max_bytes:
                    raise _BodyTooLarge(self.max_bytes)
            return message

        async def tracking_send(message: Message) -> None:
            nonlocal started
            if message["type"] == "http.response.start":
                started = True
            await send(message)

        try:
            await self.app(scope, limited_receive, tracking_send)
        except _BodyTooLarge:
            if started:  # response already under way; nothing sensible left to send
                log.warning("request body exceeded limit after response start: %s", scope.get("path"))
                return
            await self._reject(send)
