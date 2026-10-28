"""In-process pub/sub for Server-Sent Events plus optional Web Push.

Each subscriber gets its own bounded ``asyncio.Queue``. A slow or stalled client
can never block the publisher or grow memory without bound: when its queue is
full the *oldest* event is dropped (approvers care about the latest state, and
the PWA reloads the full list on reconnect anyway).
"""

from __future__ import annotations

import asyncio
import base64
import json
import logging
import threading
import time
import weakref
from collections.abc import AsyncIterator, Iterable
from typing import Any

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec
from pydantic import BaseModel, Field
from sqlalchemy import delete, select

from mirsad.storage import Database, PushSubscriptionRow, UserRow

log = logging.getLogger("mirsad.approvals")

DEFAULT_QUEUE_SIZE = 100
PUSH_TTL_S = 300


class PushReport(BaseModel):
    """Result of one Web Push fan-out."""

    sent: int = 0
    failed: int = 0
    stale_endpoints: list[str] = Field(default_factory=list)  # 404/410: subscription is gone


class Subscription(AsyncIterator[tuple[str, dict[str, Any]]]):
    """One subscriber's bounded queue; iterate with ``async for event, data in sub``.

    Registered with the notifier on creation (so nothing published after
    ``subscribe()`` returns is missed) and unregistered on :meth:`aclose` or when
    garbage-collected.
    """

    def __init__(self, notifier: Notifier, maxsize: int) -> None:
        self._notifier = notifier
        self._queue: asyncio.Queue[tuple[str, dict[str, Any]]] = asyncio.Queue(maxsize=maxsize)
        self._loop: asyncio.AbstractEventLoop | None = _running_loop()
        self.dropped = 0
        self.closed = False

    def __aiter__(self) -> Subscription:
        return self

    async def __anext__(self) -> tuple[str, dict[str, Any]]:
        if self.closed:
            raise StopAsyncIteration
        if self._loop is None:
            self._loop = asyncio.get_running_loop()
        return await self._queue.get()

    async def aclose(self) -> None:
        self.close()

    def close(self) -> None:
        self.closed = True
        self._notifier._discard(self)

    async def __aenter__(self) -> Subscription:
        return self

    async def __aexit__(self, *exc: object) -> None:
        self.close()

    def pending(self) -> int:
        return self._queue.qsize()

    def _put(self, item: tuple[str, dict[str, Any]]) -> None:
        if self.closed:
            return
        if self._queue.full():
            try:
                self._queue.get_nowait()
                self.dropped += 1
            except asyncio.QueueEmpty:
                pass
        self._queue.put_nowait(item)

    def _offer(self, item: tuple[str, dict[str, Any]]) -> None:
        loop = self._loop
        if loop is None or loop is _running_loop():
            self._put(item)
        elif not loop.is_closed():
            # Published from another thread/loop: hand over to the subscriber's loop.
            loop.call_soon_threadsafe(self._put, item)


def _running_loop() -> asyncio.AbstractEventLoop | None:
    try:
        return asyncio.get_running_loop()
    except RuntimeError:
        return None


def _subscription_info(sub: Any) -> dict[str, Any] | None:
    """Accept browser JSON (``{endpoint, keys:{p256dh, auth}}``) or a ``PushSubscriptionRow``."""
    if isinstance(sub, PushSubscriptionRow):
        return {"endpoint": sub.endpoint, "keys": {"p256dh": sub.p256dh, "auth": sub.auth}}
    if isinstance(sub, dict):
        keys = sub.get("keys") or {}
        endpoint = sub.get("endpoint")
        p256dh = keys.get("p256dh") or sub.get("p256dh")
        auth = keys.get("auth") or sub.get("auth")
        if endpoint and p256dh and auth:
            return {"endpoint": endpoint, "keys": {"p256dh": p256dh, "auth": auth}}
    return None


class Notifier:
    """Publish ``(event, data)`` to every live subscriber; optionally deliver Web Push."""

    def __init__(
        self,
        *,
        vapid_public_key: str = "",
        vapid_private_key: str = "",
        vapid_subject: str = "mailto:security@najd-trading.example",
        max_queue: int = DEFAULT_QUEUE_SIZE,
    ) -> None:
        if max_queue < 1:
            raise ValueError("max_queue must be >= 1")
        self.vapid_public_key = vapid_public_key
        self._vapid_private_key = vapid_private_key
        self.vapid_subject = vapid_subject
        self.max_queue = max_queue
        self._subs: weakref.WeakSet[Subscription] = weakref.WeakSet()
        self._lock = threading.Lock()
        self.published = 0

    @classmethod
    def from_settings(cls, settings: Any) -> Notifier:
        return cls(
            vapid_public_key=getattr(settings, "vapid_public_key", ""),
            vapid_private_key=getattr(settings, "vapid_private_key", ""),
            vapid_subject=getattr(settings, "vapid_subject", "mailto:security@najd-trading.example"),
        )

    @property
    def push_enabled(self) -> bool:
        return bool(self.vapid_public_key and self._vapid_private_key)

    @property
    def subscriber_count(self) -> int:
        with self._lock:
            return len(self._subs)

    # -- SSE fan-out -------------------------------------------------------------------------

    def subscribe(self) -> Subscription:
        """New subscriber queue (an async iterator of ``(event, data)``)."""
        sub = Subscription(self, self.max_queue)
        with self._lock:
            self._subs.add(sub)
        return sub

    def _discard(self, sub: Subscription) -> None:
        with self._lock:
            self._subs.discard(sub)

    def publish_nowait(self, event: str, data: dict[str, Any]) -> int:
        """Synchronous publish, safe from any thread. Returns the number of subscribers reached."""
        item = (event, data)
        with self._lock:
            subs = list(self._subs)
        for sub in subs:
            try:
                sub._offer(item)
            except Exception:
                log.exception("failed to deliver %s to a subscriber", event)
        self.published += 1
        return len(subs)

    async def publish(self, event: str, data: dict[str, Any]) -> None:
        self.publish_nowait(event, data)

    # -- Web Push ----------------------------------------------------------------------------

    async def web_push(self, subscriptions: list, payload: dict) -> int:
        """Send ``payload`` to each subscription; returns how many were accepted (0 without VAPID keys)."""
        return (await self.web_push_detailed(subscriptions, payload)).sent

    async def web_push_detailed(self, subscriptions: Iterable[Any], payload: dict[str, Any]) -> PushReport:
        report = PushReport()
        if not self.push_enabled:
            return report
        infos = [i for i in (_subscription_info(s) for s in subscriptions) if i]
        if not infos:
            return report
        try:
            import pywebpush
        except ImportError:  # pragma: no cover - pywebpush is a declared dependency
            log.warning("pywebpush is not installed; Web Push disabled")
            return report
        data = json.dumps(payload, ensure_ascii=False)

        def send(info: dict[str, Any]) -> tuple[bool, bool]:
            try:
                pywebpush.webpush(
                    subscription_info=info,
                    data=data,
                    vapid_private_key=self._vapid_private_key,
                    vapid_claims={"sub": self.vapid_subject},  # fresh dict: webpush mutates it
                    ttl=PUSH_TTL_S,
                    timeout=10,
                )
                return True, False
            except pywebpush.WebPushException as exc:
                status = getattr(exc, "status_code", None)
                if status is None and getattr(exc, "response", None) is not None:
                    status = getattr(exc.response, "status_code", None)
                log.warning("web push to %s failed (status %s)", info["endpoint"][:60], status)
                return False, status in (404, 410)
            except Exception:
                log.exception("web push to %s failed", info["endpoint"][:60])
                return False, False

        results = await asyncio.gather(*(asyncio.to_thread(send, info) for info in infos))
        for info, (ok, stale) in zip(infos, results, strict=True):
            if ok:
                report.sent += 1
            else:
                report.failed += 1
                if stale:
                    report.stale_endpoints.append(info["endpoint"])
        return report


# ----------------------------------------------------------------------------- push storage helpers


def generate_vapid_keys() -> tuple[str, str]:
    """New P-256 VAPID key pair as ``(public_key, private_key)``, both base64url without padding.

    The public key is the uncompressed point the browser's ``applicationServerKey``
    expects; the private key is the raw 32-byte scalar accepted by pywebpush.
    """
    key = ec.generate_private_key(ec.SECP256R1())
    public = key.public_key().public_bytes(serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint)
    private = key.private_numbers().private_value.to_bytes(32, "big")

    def b64(raw: bytes) -> str:
        return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()

    return b64(public), b64(private)


def save_push_subscription(db: Database, username: str, subscription: dict[str, Any]) -> int:
    """Store (or re-assign) a browser push subscription for ``username``; returns its row id."""
    info = _subscription_info(subscription)
    if info is None:
        raise ValueError("subscription must contain endpoint and keys.p256dh / keys.auth")
    if not str(info["endpoint"]).startswith("https://"):
        raise ValueError("push endpoint must be an https:// URL")
    with db.session() as sess:
        user = sess.scalar(select(UserRow).where(UserRow.username == username))
        if user is None:
            raise LookupError(f"unknown user {username!r}")
        row = sess.scalar(select(PushSubscriptionRow).where(PushSubscriptionRow.endpoint == info["endpoint"]))
        if row is None:
            row = PushSubscriptionRow(endpoint=info["endpoint"], user_id=user.id,
                                      p256dh=info["keys"]["p256dh"], auth=info["keys"]["auth"],
                                      created_at=time.time())
            sess.add(row)
        else:
            row.user_id, row.p256dh, row.auth = user.id, info["keys"]["p256dh"], info["keys"]["auth"]
        sess.flush()
        return row.id


def delete_push_subscriptions(db: Database, endpoints: Iterable[str]) -> int:
    endpoints = list(endpoints)
    if not endpoints:
        return 0
    with db.session() as sess:
        result = sess.execute(delete(PushSubscriptionRow).where(PushSubscriptionRow.endpoint.in_(endpoints)))
        return int(result.rowcount or 0)


def load_push_subscriptions(db: Database, roles: Iterable[str] = ("admin", "approver")) -> list[dict[str, Any]]:
    """Subscriptions of enabled users with one of ``roles``, in browser JSON form."""
    with db.session() as sess:
        rows = sess.scalars(
            select(PushSubscriptionRow).join(UserRow)
            .where(UserRow.disabled.is_(False), UserRow.role.in_(list(roles)))
        ).all()
        return [i for i in (_subscription_info(r) for r in rows) if i]
