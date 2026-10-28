"""FastAPI dependencies: component access and authentication (human JWT / agent API key)."""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import APIKeyHeader, HTTPAuthorizationCredentials, HTTPBearer
from starlette.concurrency import run_in_threadpool

from mirsad.api.components import Components
from mirsad.api.schemas import UserOut
from mirsad.gateway import Gateway, principal_var

log = logging.getLogger("mirsad.api")

ROLES = ("admin", "approver", "auditor")

_bearer = HTTPBearer(auto_error=False, description="User JWT from /api/auth/login, or an agent key `mk_...`")
_agent_header = APIKeyHeader(name="X-Mirsad-Key", auto_error=False, description="Agent API key `mk_...`")


def _unauthorized(detail: str) -> HTTPException:
    return HTTPException(status.HTTP_401_UNAUTHORIZED, detail=detail, headers={"WWW-Authenticate": "Bearer"})


def get_components(request: Request) -> Components:
    return request.app.state.components


def get_gateway(request: Request) -> Gateway:
    return request.app.state.gateway


def resolve_user(comps: Components, token: str) -> Any:
    """Validate a JWT and re-load the user so disabled accounts and role changes apply immediately."""
    if token.startswith("mk_"):
        raise _unauthorized("Agent keys cannot access the management API")
    try:
        claims = comps.auth.decode_token(token, comps.secret)
    except Exception as exc:  # AuthError and any decoding failure
        raise _unauthorized("Invalid or expired token") from exc
    username = claims.get("sub") if isinstance(claims, dict) else None
    if not username:
        raise _unauthorized("Invalid token")
    row = comps.auth.get_user(comps.db, str(username))
    if row is None or row.disabled:
        raise _unauthorized("User is unknown or disabled")
    # Spec section 14: require_user -> mirsad.auth.UserInfo (same fields as the API's UserOut).
    model = getattr(comps.auth, "UserInfo", None) or UserOut
    return model(username=row.username, role=row.role, display_name=row.display_name or "", lang=row.lang or "en")


def require_user(*roles: str) -> Callable[..., Any]:
    """Dependency factory: any authenticated user, or one of ``roles``. The dependency returns ``UserInfo``."""
    for role in roles:
        if role not in ROLES:
            raise ValueError(f"unknown role {role!r}")

    def dependency(request: Request,
                   credentials: HTTPAuthorizationCredentials | None = Depends(_bearer)) -> Any:  # noqa: B008
        if credentials is None or not credentials.credentials:
            raise _unauthorized("Not authenticated")
        user = resolve_user(request.app.state.components, credentials.credentials)
        if roles and user.role not in roles:
            raise HTTPException(status.HTTP_403_FORBIDDEN, detail=f"Requires role: {' or '.join(roles)}")
        request.state.user = user
        return user

    dependency.__name__ = f"require_user_{'_'.join(roles) or 'any'}"
    return dependency


def authenticate_agent(comps: Components, key: str | None) -> Any:
    if not key or not key.startswith("mk_"):
        raise _unauthorized("Agent API key required (Authorization: Bearer mk_... or X-Mirsad-Key)")
    agent = comps.auth.authenticate_agent_key(comps.db, key)
    if agent is None:
        raise _unauthorized("Invalid or disabled agent key")
    return agent


async def require_agent(request: Request,
                        credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),  # noqa: B008
                        x_key: str | None = Depends(_agent_header)) -> Any:  # noqa: B008
    """Authenticate an agent key. Async so the principal context variable reaches the endpoint."""
    key = x_key.strip() if x_key else (credentials.credentials if credentials else None)
    agent = await run_in_threadpool(authenticate_agent, request.app.state.components, key)
    principal_var.set(agent.id)
    request.state.agent = agent
    return agent
