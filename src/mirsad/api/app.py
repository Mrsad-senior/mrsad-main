"""FastAPI application factory for the Mirsad gateway, management API, dashboard and approver PWA."""

from __future__ import annotations

import asyncio
import contextlib
import logging
import os
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool
from starlette.routing import Route

from mirsad import __version__
from mirsad.api.components import Components, bootstrap_admin, build_components, build_engine
from mirsad.api.routers import agents as agents_router
from mirsad.api.routers import (
    approvals,
    audit,
    auth,
    detector,
    guard,
    policies,
    push,
    stats,
    stream,
    tools,
    users,
)
from mirsad.api.routers.auth import LoginThrottle
from mirsad.api.security import MAX_BODY_BYTES, BodyLimitMiddleware, SecurityHeadersMiddleware
from mirsad.api.static import install_static
from mirsad.config import PACKAGE_DIR, Settings, get_settings

log = logging.getLogger("mirsad.api")

MAINTENANCE_INTERVAL_S = 5.0

DESCRIPTION = """
**Mirsad (مرصاد)** is a runtime security firewall between LLM agents and their tools.

* **Agent API** (`/v1/...`, agent key `Authorization: Bearer mk_...` or `X-Mirsad-Key`): Guard API,
  tool invocation, OpenAI-compatible proxy, MCP (`/mcp`).
* **Management API** (`/api/...`, user JWT from `POST /api/auth/login`): approvals, audit, policies,
  agents, users, statistics, live SSE stream.

Errors are JSON `{"detail": "..."}`.
"""


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    comps: Components = app.state.components
    listener = None
    if hasattr(comps.audit, "add_listener") and hasattr(comps.notifier, "publish_nowait"):
        def listener(event: Any) -> None:  # runs in the appending thread; publish_nowait is thread-safe
            comps.notifier.publish_nowait("audit.event", event.model_dump(mode="json"))

        comps.audit.add_listener(listener)
        app.state.audit_events_via_notifier = True

    if comps.upstreams is not None:
        try:
            await comps.upstreams.start()
        except Exception:
            log.exception("starting upstream tool servers failed; continuing without them")

    await run_in_threadpool(comps.audit.append, "system.started", policy_version=getattr(comps.policy, "version", None),
                            payload={"version": __version__, "pid": os.getpid(),
                                     "demo": comps.settings.enable_demo})
    maintenance = asyncio.create_task(_maintenance(app), name="mirsad-maintenance")
    try:
        yield
    finally:
        maintenance.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await maintenance
        mcp_app = getattr(app.state, "mcp_app", None)
        if mcp_app is not None and hasattr(mcp_app, "aclose"):
            with contextlib.suppress(Exception):
                await mcp_app.aclose()
        if comps.upstreams is not None:
            with contextlib.suppress(Exception):
                await comps.upstreams.stop()
        if hasattr(comps.approvals, "aclose"):
            with contextlib.suppress(Exception):
                await comps.approvals.aclose()
        if listener is not None:
            comps.audit.remove_listener(listener)
            app.state.audit_events_via_notifier = False
        if hasattr(comps.db, "dispose"):
            with contextlib.suppress(Exception):
                await run_in_threadpool(comps.db.dispose)


async def _maintenance(app: FastAPI) -> None:
    """Expire overdue approvals and pick up policy activations made elsewhere (CLI, other workers)."""
    comps: Components = app.state.components
    interval = getattr(app.state, "maintenance_interval_s", MAINTENANCE_INTERVAL_S)
    while True:
        await asyncio.sleep(interval)
        try:
            await run_in_threadpool(comps.approvals.expire_overdue)
            await run_in_threadpool(sync_active_policy, app)
        except Exception:
            log.exception("maintenance cycle failed")


def sync_active_policy(app: FastAPI) -> bool:
    """Hot-swap the gateway policy if the active version in the database changed. Returns True if swapped."""
    comps: Components = app.state.components
    store = comps.policy_store
    if not hasattr(store, "active_version"):
        return False
    version = store.active_version()
    gateway = app.state.gateway
    if not version or version == getattr(gateway.policy, "version", None):
        return False
    yaml_text = store.get_yaml(version)
    if yaml_text is None:
        return False
    engine = build_engine(comps.policy_module, yaml_text, gateway.policy)
    gateway.set_policy(engine)
    comps.policy = engine
    log.info("picked up policy %s activated outside this process", version[:12])
    return True


def _validation_handler(_request: Request, exc: RequestValidationError) -> JSONResponse:
    # Never echo submitted values back (they may contain passwords or keys).
    errors = [{"loc": list(e.get("loc", ())), "msg": e.get("msg", ""), "type": e.get("type", "")}
              for e in exc.errors()]
    detail = "; ".join(f"{'.'.join(str(p) for p in e['loc'])}: {e['msg']}" for e in errors) or "Invalid request"
    return JSONResponse(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                        content={"detail": detail, "errors": jsonable_encoder(errors)})


def _server_error_handler(request: Request, exc: Exception) -> JSONResponse:
    log.error("unhandled error on %s %s: %s", request.method, request.url.path, type(exc).__name__, exc_info=exc)
    return JSONResponse(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, content={"detail": "Internal server error"})


def _mount_adapters(app: FastAPI) -> None:
    try:
        from mirsad.adapters.openai_proxy import build_openai_router
    except ImportError:
        log.warning("OpenAI-compatible proxy unavailable (mirsad.adapters.openai_proxy not importable)")
    else:
        app.include_router(build_openai_router())
    try:
        from mirsad.adapters.mcp_proxy import mcp_http_app
    except ImportError:
        log.warning("MCP HTTP endpoint unavailable (mirsad.adapters.mcp_proxy not importable)")
        return
    mcp_app = mcp_http_app(app.state)
    app.state.mcp_app = mcp_app
    # Exact "/mcp" (no redirect to "/mcp/": MCP clients do not follow redirects on POST) and sub-paths.
    app.router.routes.append(Route("/mcp", endpoint=mcp_app, methods=["GET", "POST", "DELETE"],
                                   include_in_schema=False))
    app.mount("/mcp", mcp_app, name="mcp")


def create_app(settings: Settings | None = None, *, gateway_overrides: dict[str, Any] | None = None,
               static_dir: Path | None = None) -> FastAPI:
    """Build the app. ``gateway_overrides`` replaces components (see ``components.OVERRIDE_KEYS``)."""
    settings = settings or get_settings()
    comps = build_components(settings, gateway_overrides)
    bootstrap_admin(comps)

    app = FastAPI(title="Mirsad API", version=__version__, description=DESCRIPTION, lifespan=lifespan,
                  docs_url="/docs", redoc_url="/redoc", openapi_url="/openapi.json")
    app.state.components = comps
    for name, value in comps.as_state().items():
        setattr(app.state, name, value)
    app.state.login_throttle = LoginThrottle()
    app.state.demo_sessions = set()
    app.state.audit_events_via_notifier = False
    app.state.started_at = time.time()

    # add_middleware prepends: the last one added runs first (outermost).
    app.add_middleware(BodyLimitMiddleware, max_bytes=MAX_BODY_BYTES)
    app.add_middleware(CORSMiddleware, allow_origins=list(settings.cors_origins), allow_credentials=False,
                       allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
                       allow_headers=["Authorization", "Content-Type", "X-Mirsad-Key", "X-Mirsad-Session",
                                      "X-Upstream-Authorization"],
                       max_age=600)
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_exception_handler(RequestValidationError, _validation_handler)  # type: ignore[arg-type]
    app.add_exception_handler(Exception, _server_error_handler)

    @app.get("/healthz", tags=["health"])
    def healthz() -> dict[str, str]:
        return {"status": "ok", "version": __version__}

    for module in (auth, guard, detector, approvals, stream, push, audit, stats, policies, agents_router, users, tools):
        app.include_router(module.router)
    _mount_adapters(app)
    if settings.enable_demo:
        from mirsad.api.routers import demo

        app.include_router(demo.router)
    install_static(app, static_dir or PACKAGE_DIR / "static")
    log.info("Mirsad API ready (policy %s, demo=%s)", str(getattr(comps.policy, "version", "?"))[:12],
             settings.enable_demo)
    return app
