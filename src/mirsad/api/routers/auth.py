"""Human authentication: login (throttled, audited) and current-user lookup."""

from __future__ import annotations

import logging
import threading
import time
from collections import defaultdict, deque

from fastapi import APIRouter, Depends, HTTPException, Request, status

from mirsad.api.deps import get_components, require_user
from mirsad.api.schemas import ErrorResponses, LoginRequest, LoginResponse, Problem, UserOut

log = logging.getLogger("mirsad.api")

router = APIRouter(prefix="/api/auth", tags=["auth"])


class LoginThrottle:
    """Sliding-window failure counter: per username+IP (brute force) and per IP (credential stuffing)."""

    def __init__(self, *, max_failures: int = 5, ip_max_failures: int = 30, window_s: float = 300.0) -> None:
        self.max_failures = max_failures
        self.ip_max_failures = ip_max_failures
        self.window_s = window_s
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def _prune(self, key: str, now: float) -> deque[float]:
        q = self._hits[key]
        while q and q[0] <= now - self.window_s:
            q.popleft()
        if not q:
            self._hits.pop(key, None)
        return q

    def retry_after(self, username: str, ip: str, now: float | None = None) -> int:
        """Seconds until the next attempt is allowed (0 = allowed now)."""
        now = time.time() if now is None else now
        with self._lock:
            waits = []
            for key, limit in ((f"u:{username.lower()}|{ip}", self.max_failures), (f"ip:{ip}", self.ip_max_failures)):
                q = self._prune(key, now)
                if len(q) >= limit:
                    waits.append(int(q[0] + self.window_s - now) + 1)
            return max(waits, default=0)

    def failure(self, username: str, ip: str, now: float | None = None) -> None:
        now = time.time() if now is None else now
        with self._lock:
            self._hits[f"u:{username.lower()}|{ip}"].append(now)
            self._hits[f"ip:{ip}"].append(now)

    def success(self, username: str, ip: str) -> None:
        with self._lock:
            self._hits.pop(f"u:{username.lower()}|{ip}", None)


def _client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


@router.post("/login", response_model=LoginResponse,
             responses={401: {"model": Problem}, 429: {"model": Problem, "description": "Too many failed attempts"}})
def login(body: LoginRequest, request: Request) -> LoginResponse:
    comps = get_components(request)
    throttle: LoginThrottle = request.app.state.login_throttle
    ip = _client_ip(request)
    wait = throttle.retry_after(body.username, ip)
    if wait:
        comps.audit.append("auth.login_failed", payload={"username": body.username, "ip": ip, "reason": "throttled"})
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, detail="Too many failed login attempts; try later",
                            headers={"Retry-After": str(wait)})
    user = comps.auth.authenticate_user(comps.db, body.username, body.password)
    if user is None:
        throttle.failure(body.username, ip)
        comps.audit.append("auth.login_failed", payload={"username": body.username, "ip": ip,
                                                          "reason": "bad_credentials"})
        log.info("failed login for %r from %s", body.username, ip)
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Invalid username or password")
    throttle.success(body.username, ip)
    settings = comps.settings
    token = comps.auth.create_token(user.username, user.role, comps.secret, settings.token_ttl_hours)
    comps.audit.append("auth.login", payload={"username": user.username, "ip": ip})
    return LoginResponse(access_token=token, expires_in=settings.token_ttl_hours * 3600,
                         user=UserOut(username=user.username, role=user.role, display_name=user.display_name,
                                      lang=user.lang))


@router.get("/me", response_model=UserOut, responses=ErrorResponses.AUTH)
def me(user=Depends(require_user())) -> UserOut:  # noqa: B008
    return UserOut(username=user.username, role=user.role, display_name=user.display_name, lang=user.lang)
