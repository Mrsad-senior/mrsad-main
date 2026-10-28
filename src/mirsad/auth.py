"""Authentication primitives: passwords, JWTs, agent API keys and login throttling.

* Human users (roles ``admin``, ``approver``, ``auditor``) log in with a password
  stored as a salted scrypt hash in PHC string format
  (``$scrypt$ln=14,r=8,p=1$<salt>$<hash>``) and then use a short-lived HS256 JWT.
* Agents authenticate with an API key ``mk_<8-char prefix>_<secret>``. Only the
  prefix (for lookup and display) and the SHA-256 of the full key are stored; the
  key is shown once at creation/rotation. A fast hash is appropriate here because
  the secret has 256 bits of entropy, unlike a human password.

The FastAPI dependencies (``require_user``/``require_agent``) live in the api
package and are built on the functions below.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import logging
import re
import secrets
import string
import threading
import time
from collections import OrderedDict, deque
from functools import lru_cache
from typing import Any, Literal

import jwt
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from mirsad.storage import USER_LANGS, USER_ROLES, AgentRow, Database, UserRow

log = logging.getLogger("mirsad.auth")

Role = Literal["admin", "approver", "auditor"]

SCRYPT_LOG_N = 14  # n = 2**14
SCRYPT_R = 8
SCRYPT_P = 1
SCRYPT_SALT_BYTES = 16
SCRYPT_DKLEN = 32
# Upper bounds accepted when *verifying*, so a tampered hash cannot trigger huge allocations.
_MAX_LOG_N, _MAX_R, _MAX_P = 17, 16, 16
MIN_PASSWORD_LENGTH = 8
MAX_PASSWORD_LENGTH = 1024

JWT_ALGORITHM = "HS256"
JWT_ISSUER = "mirsad"

AGENT_KEY_PREFIX_LEN = 8
_PREFIX_ALPHABET = string.ascii_lowercase + string.digits
AGENT_KEY_RE = re.compile(r"^mk_([a-z0-9]{8})_([A-Za-z0-9_-]{32,128})$")
_LAST_SEEN_WRITE_INTERVAL_S = 30.0

USERNAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.@-]{2,63}$")
AGENT_ID_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{1,63}$")


class AuthError(Exception):
    """Authentication failed (bad/expired token, bad credentials, disabled principal)."""


class AlreadyExistsError(ValueError):
    """A user or agent with this identifier already exists."""


class NotFoundError(KeyError):
    """No user or agent with this identifier (a ``KeyError``, hence also a ``LookupError``)."""

    def __str__(self) -> str:
        return str(self.args[0]) if self.args else "not found"


class UserInfo(BaseModel):
    username: str
    role: Role
    display_name: str = ""
    lang: str = "en"


class AgentInfo(BaseModel):
    id: str
    name: str
    policy_agent_id: str


class UserDetails(UserInfo):
    """Admin view of a user (never includes the password hash)."""

    id: int
    created_at: float
    disabled: bool = False


class AgentDetails(AgentInfo):
    """Admin view of an agent (never includes the key hash)."""

    description: str = ""
    key_prefix: str
    created_at: float
    disabled: bool = False
    last_seen_at: float | None = None


# ----------------------------------------------------------------------------- passwords


def _b64e(raw: bytes) -> str:
    return base64.b64encode(raw).decode().rstrip("=")


def _b64d(text: str) -> bytes:
    return base64.b64decode(text + "=" * (-len(text) % 4), validate=True)


def _scrypt(pw: str, salt: bytes, log_n: int, r: int, p: int, dklen: int) -> bytes:
    n = 2**log_n
    maxmem = 128 * r * n * p + 128 * r * n * 2 + (1 << 20)
    return hashlib.scrypt(pw.encode("utf-8"), salt=salt, n=n, r=r, p=p, dklen=dklen, maxmem=maxmem)


def hash_password(pw: str) -> str:
    """Salted scrypt hash in PHC format: ``$scrypt$ln=14,r=8,p=1$<salt>$<hash>``."""
    if not isinstance(pw, str) or not pw:
        raise ValueError("password must be a non-empty string")
    if len(pw) > MAX_PASSWORD_LENGTH:
        raise ValueError("password is too long")
    salt = secrets.token_bytes(SCRYPT_SALT_BYTES)
    digest = _scrypt(pw, salt, SCRYPT_LOG_N, SCRYPT_R, SCRYPT_P, SCRYPT_DKLEN)
    return f"$scrypt$ln={SCRYPT_LOG_N},r={SCRYPT_R},p={SCRYPT_P}${_b64e(salt)}${_b64e(digest)}"


def _parse_hash(hashed: str) -> tuple[int, int, int, bytes, bytes] | None:
    try:
        _, scheme, params, salt_b64, hash_b64 = hashed.split("$")
        if scheme != "scrypt":
            return None
        kv = dict(item.split("=", 1) for item in params.split(","))
        log_n, r, p = int(kv["ln"]), int(kv["r"]), int(kv["p"])
        salt, digest = _b64d(salt_b64), _b64d(hash_b64)
    except (ValueError, KeyError, TypeError):
        return None
    if not (1 <= log_n <= _MAX_LOG_N and 1 <= r <= _MAX_R and 1 <= p <= _MAX_P) or not salt or len(digest) < 16:
        return None
    return log_n, r, p, salt, digest


def verify_password(pw: str, hashed: str) -> bool:
    """Constant-time check of ``pw`` against a hash from :func:`hash_password`. Never raises."""
    if not isinstance(pw, str) or not isinstance(hashed, str) or len(pw) > MAX_PASSWORD_LENGTH:
        return False
    parsed = _parse_hash(hashed)
    if parsed is None:
        log.warning("unrecognised password hash format")
        return False
    log_n, r, p, salt, digest = parsed
    candidate = _scrypt(pw, salt, log_n, r, p, len(digest))
    return hmac.compare_digest(candidate, digest)


def needs_rehash(hashed: str) -> bool:
    """True when the stored hash uses weaker parameters than the current defaults."""
    parsed = _parse_hash(hashed)
    if parsed is None:
        return True
    log_n, r, p, _, digest = parsed
    return (log_n, r, p) < (SCRYPT_LOG_N, SCRYPT_R, SCRYPT_P) or len(digest) < SCRYPT_DKLEN


@lru_cache(maxsize=1)
def _dummy_hash() -> str:
    return hash_password(secrets.token_urlsafe(16))


# ----------------------------------------------------------------------------- JWT


def create_token(username: str, role: str, secret: str, ttl_hours: int) -> str:
    """Signed HS256 JWT with ``sub``, ``role``, ``iat``, ``exp``, ``iss`` and a random ``jti``."""
    if role not in USER_ROLES:
        raise ValueError(f"unknown role {role!r}")
    if not secret:
        raise ValueError("JWT secret must not be empty")
    if ttl_hours <= 0:
        raise ValueError("ttl_hours must be positive")
    now = int(time.time())
    claims = {
        "sub": username, "role": role, "iat": now, "nbf": now, "exp": now + int(ttl_hours * 3600),
        "iss": JWT_ISSUER, "jti": secrets.token_hex(8),
    }
    return jwt.encode(claims, secret, algorithm=JWT_ALGORITHM)


def decode_token(token: str, secret: str) -> dict[str, Any]:
    """Validate signature, expiry and required claims; raises :class:`AuthError`."""
    if not token or not secret:
        raise AuthError("missing token")
    try:
        claims = jwt.decode(
            token, secret, algorithms=[JWT_ALGORITHM], issuer=JWT_ISSUER,
            options={"require": ["exp", "iat", "sub", "role"]},
        )
    except jwt.ExpiredSignatureError as exc:
        raise AuthError("token expired") from exc
    except jwt.PyJWTError as exc:
        raise AuthError(f"invalid token: {exc}") from exc
    if claims.get("role") not in USER_ROLES:
        raise AuthError("invalid token: unknown role")
    return claims


# ----------------------------------------------------------------------------- agent keys


def hash_agent_key(key: str) -> str:
    """SHA-256 hex digest of the full agent key (what the database stores)."""
    return hashlib.sha256(key.encode("utf-8")).hexdigest()


def generate_agent_key() -> tuple[str, str, str]:
    """New key as ``(full_key, prefix, sha256_hash)``; ``full_key = mk_<prefix>_<secret>``."""
    prefix = "".join(secrets.choice(_PREFIX_ALPHABET) for _ in range(AGENT_KEY_PREFIX_LEN))
    key = f"mk_{prefix}_{secrets.token_urlsafe(32)}"
    return key, prefix, hash_agent_key(key)


def parse_agent_key(key: str) -> str | None:
    """Return the prefix of a well-formed agent key, else None."""
    match = AGENT_KEY_RE.match((key or "").strip())
    return match.group(1) if match else None


def _agent_details(row: AgentRow) -> AgentDetails:
    return AgentDetails(
        id=row.id, name=row.name, policy_agent_id=row.policy_agent_id, description=row.description or "",
        key_prefix=row.key_prefix, created_at=row.created_at, disabled=row.disabled, last_seen_at=row.last_seen_at,
    )


def authenticate_agent_key(db: Database, key: str) -> AgentInfo | None:
    """Resolve an agent key; None if malformed, unknown or disabled. Updates ``last_seen_at``."""
    prefix = parse_agent_key(key)
    if prefix is None:
        return None
    digest = hash_agent_key(key.strip())
    with db.session() as sess:
        rows = sess.scalars(select(AgentRow).where(AgentRow.key_prefix == prefix)).all()
        match = None
        for row in rows:  # prefixes are random but not guaranteed unique
            if hmac.compare_digest(row.key_hash, digest):
                match = row
        if match is None or match.disabled:
            return None
        now = time.time()
        if match.last_seen_at is None or now - match.last_seen_at >= _LAST_SEEN_WRITE_INTERVAL_S:
            match.last_seen_at = now
        return AgentInfo(id=match.id, name=match.name, policy_agent_id=match.policy_agent_id)


def create_agent(db: Database, agent_id: str, name: str, policy_agent_id: str,
                 description: str = "") -> tuple[AgentInfo, str]:
    """Register an agent; returns its info and the full API key (shown only this once)."""
    if not AGENT_ID_RE.match(agent_id or ""):
        raise ValueError("agent id must be a lowercase slug (a-z, 0-9, '-', '_'), 2-64 chars")
    if not name or not policy_agent_id:
        raise ValueError("name and policy_agent_id are required")
    key, prefix, digest = generate_agent_key()
    try:
        with db.session() as sess:
            if sess.get(AgentRow, agent_id) is not None:
                raise AlreadyExistsError(f"agent {agent_id!r} already exists")
            sess.add(AgentRow(id=agent_id, name=name, description=description, policy_agent_id=policy_agent_id,
                              key_prefix=prefix, key_hash=digest, created_at=time.time(), disabled=False))
    except IntegrityError as exc:
        raise AlreadyExistsError(f"agent {agent_id!r} already exists") from exc
    log.info("agent %s created (key prefix %s)", agent_id, prefix)
    return AgentInfo(id=agent_id, name=name, policy_agent_id=policy_agent_id), key


def rotate_agent_key(db: Database, agent_id: str) -> str:
    """Replace an agent's key; the old key stops working immediately. Returns the new key."""
    key, prefix, digest = generate_agent_key()
    with db.session() as sess:
        row = sess.get(AgentRow, agent_id)
        if row is None:
            raise NotFoundError(f"unknown agent {agent_id!r}")
        row.key_prefix, row.key_hash = prefix, digest
    log.info("agent %s key rotated (new prefix %s)", agent_id, prefix)
    return key


def get_agent(db: Database, agent_id: str) -> AgentDetails | None:
    with db.session() as sess:
        row = sess.get(AgentRow, agent_id)
        return _agent_details(row) if row else None


def list_agents(db: Database) -> list[AgentDetails]:
    with db.session() as sess:
        return [_agent_details(r) for r in sess.scalars(select(AgentRow).order_by(AgentRow.id)).all()]


def update_agent(db: Database, agent_id: str, *, name: str | None = None, description: str | None = None,
                 policy_agent_id: str | None = None, disabled: bool | None = None) -> AgentDetails:
    with db.session() as sess:
        row = sess.get(AgentRow, agent_id)
        if row is None:
            raise NotFoundError(f"unknown agent {agent_id!r}")
        if name is not None:
            row.name = name
        if description is not None:
            row.description = description
        if policy_agent_id is not None:
            row.policy_agent_id = policy_agent_id
        if disabled is not None:
            row.disabled = disabled
        sess.flush()
        return _agent_details(row)


def delete_agent(db: Database, agent_id: str) -> bool:
    with db.session() as sess:
        row = sess.get(AgentRow, agent_id)
        if row is None:
            return False
        sess.delete(row)
        return True


# ----------------------------------------------------------------------------- users


def _user_details(row: UserRow) -> UserDetails:
    return UserDetails(id=row.id, username=row.username, role=row.role, display_name=row.display_name or "",
                       lang=row.lang, created_at=row.created_at, disabled=row.disabled)


def _validate_password(password: str) -> None:
    if not isinstance(password, str) or len(password) < MIN_PASSWORD_LENGTH:
        raise ValueError(f"password must be at least {MIN_PASSWORD_LENGTH} characters")


def create_user(db: Database, username: str, password: str, role: str, display_name: str = "",
                lang: str = "en") -> UserInfo:
    """Create a human user; raises ``ValueError`` (or :class:`AlreadyExistsError`) on bad input."""
    if not USERNAME_RE.match(username or ""):
        raise ValueError("username must be 3-64 characters: letters, digits, '_', '.', '@', '-'")
    if role not in USER_ROLES:
        raise ValueError(f"role must be one of {', '.join(USER_ROLES)}")
    if lang not in USER_LANGS:
        raise ValueError("lang must be 'en' or 'ar'")
    _validate_password(password)
    hashed = hash_password(password)
    try:
        with db.session() as sess:
            if sess.scalar(select(UserRow.id).where(UserRow.username == username)) is not None:
                raise AlreadyExistsError(f"user {username!r} already exists")
            sess.add(UserRow(username=username, password_hash=hashed, role=role, display_name=display_name,
                             lang=lang, created_at=time.time(), disabled=False))
    except IntegrityError as exc:
        raise AlreadyExistsError(f"user {username!r} already exists") from exc
    log.info("user %s created with role %s", username, role)
    return UserInfo(username=username, role=role, display_name=display_name, lang=lang)


def authenticate_user(db: Database, username: str, password: str) -> UserInfo | None:
    """Check credentials; None for unknown user, wrong password or disabled account.

    Unknown users still cost one scrypt evaluation so response time does not reveal
    which usernames exist.
    """
    with db.session() as sess:
        row = sess.scalar(select(UserRow).where(UserRow.username == username))
        if row is None:
            verify_password(password, _dummy_hash())
            return None
        if not verify_password(password, row.password_hash):
            return None
        if row.disabled:
            return None
        if needs_rehash(row.password_hash):
            row.password_hash = hash_password(password)
        return UserInfo(username=row.username, role=row.role, display_name=row.display_name or "", lang=row.lang)


def get_user(db: Database, username: str) -> UserDetails | None:
    with db.session() as sess:
        row = sess.scalar(select(UserRow).where(UserRow.username == username))
        return _user_details(row) if row else None


def list_users(db: Database) -> list[UserDetails]:
    with db.session() as sess:
        return [_user_details(r) for r in sess.scalars(select(UserRow).order_by(UserRow.username)).all()]


def update_user(db: Database, username: str, *, password: str | None = None, role: str | None = None,
                display_name: str | None = None, lang: str | None = None,
                disabled: bool | None = None) -> UserDetails:
    if role is not None and role not in USER_ROLES:
        raise ValueError(f"role must be one of {', '.join(USER_ROLES)}")
    if lang is not None and lang not in USER_LANGS:
        raise ValueError("lang must be 'en' or 'ar'")
    if password is not None:
        _validate_password(password)
    with db.session() as sess:
        row = sess.scalar(select(UserRow).where(UserRow.username == username))
        if row is None:
            raise NotFoundError(f"unknown user {username!r}")
        if password is not None:
            row.password_hash = hash_password(password)
        if role is not None:
            row.role = role
        if display_name is not None:
            row.display_name = display_name
        if lang is not None:
            row.lang = lang
        if disabled is not None:
            row.disabled = disabled
        sess.flush()
        return _user_details(row)


def delete_user(db: Database, username: str) -> bool:
    with db.session() as sess:
        row = sess.scalar(select(UserRow).where(UserRow.username == username))
        if row is None:
            return False
        sess.delete(row)
        return True


def user_from_token(db: Database, token: str, secret: str) -> UserInfo:
    """Decode a JWT and re-load the user so disabling or re-roling takes effect immediately."""
    claims = decode_token(token, secret)
    with db.session() as sess:
        row = sess.scalar(select(UserRow).where(UserRow.username == claims["sub"]))
        if row is None or row.disabled:
            raise AuthError("user is unknown or disabled")
        return UserInfo(username=row.username, role=row.role, display_name=row.display_name or "", lang=row.lang)


# ----------------------------------------------------------------------------- login throttle


class LoginThrottle:
    """Sliding-window limit on failed logins per ``(username, ip)``; thread-safe and memory-bounded.

    Usage: ``if throttle.is_blocked(u, ip): 429`` -> on failure ``record_failure(u, ip)``
    -> on success ``reset(u, ip)``.
    """

    def __init__(self, max_failures: int = 5, window_s: float = 300.0, *, max_keys: int = 10_000,
                 clock: Any = time.monotonic) -> None:
        if max_failures < 1 or window_s <= 0:
            raise ValueError("max_failures must be >= 1 and window_s > 0")
        self.max_failures = max_failures
        self.window_s = window_s
        self.max_keys = max_keys
        self._clock = clock
        self._failures: OrderedDict[tuple[str, str], deque[float]] = OrderedDict()
        self._lock = threading.Lock()

    @staticmethod
    def _key(username: str, ip: str | None) -> tuple[str, str]:
        return (username or "").strip().lower(), ip or "-"

    def _prune(self, key: tuple[str, str], now: float) -> deque[float] | None:
        times = self._failures.get(key)
        if times is None:
            return None
        while times and now - times[0] >= self.window_s:
            times.popleft()
        if not times:
            del self._failures[key]
            return None
        return times

    def record_failure(self, username: str, ip: str | None) -> int:
        """Record a failed attempt; returns failures in the current window."""
        key = self._key(username, ip)
        now = self._clock()
        with self._lock:
            times = self._prune(key, now)
            if times is None:
                times = deque()
                self._failures[key] = times
            times.append(now)
            self._failures.move_to_end(key)
            while len(self._failures) > self.max_keys:
                self._failures.popitem(last=False)
            return len(times)

    def failures(self, username: str, ip: str | None) -> int:
        with self._lock:
            times = self._prune(self._key(username, ip), self._clock())
            return len(times) if times else 0

    def is_blocked(self, username: str, ip: str | None) -> bool:
        return self.failures(username, ip) >= self.max_failures

    def retry_after(self, username: str, ip: str | None) -> float:
        """Seconds until the next attempt is allowed (0 when not blocked)."""
        key = self._key(username, ip)
        now = self._clock()
        with self._lock:
            times = self._prune(key, now)
            if not times or len(times) < self.max_failures:
                return 0.0
            # Unblocked once enough old failures leave the window.
            oldest_relevant = times[len(times) - self.max_failures]
            return max(0.0, self.window_s - (now - oldest_relevant))

    def reset(self, username: str, ip: str | None) -> None:
        with self._lock:
            self._failures.pop(self._key(username, ip), None)
