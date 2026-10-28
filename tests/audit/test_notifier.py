from __future__ import annotations

import asyncio
import gc
import threading

import pytest
import pywebpush
from py_vapid import Vapid

from mirsad.approvals import (
    Notifier,
    delete_push_subscriptions,
    generate_vapid_keys,
    load_push_subscriptions,
    save_push_subscription,
)
from mirsad.auth import create_user, update_user

SUB = {"endpoint": "https://push.example/sub/1", "keys": {"p256dh": "BPubKey", "auth": "AuthSecret"}}


async def _drain(sub, n: int, timeout: float = 1.0) -> list:
    return [await asyncio.wait_for(sub.__anext__(), timeout) for _ in range(n)]


async def test_publish_fans_out_to_every_subscriber(notifier):
    a, b = notifier.subscribe(), notifier.subscribe()
    await notifier.publish("approval.requested", {"id": "apr_1"})
    await notifier.publish("approval.decided", {"id": "apr_1", "status": "approved"})
    for sub in (a, b):
        assert await _drain(sub, 2) == [("approval.requested", {"id": "apr_1"}),
                                        ("approval.decided", {"id": "apr_1", "status": "approved"})]


async def test_subscription_registered_before_first_iteration(notifier):
    sub = notifier.subscribe()
    assert notifier.subscriber_count == 1
    await notifier.publish("audit.event", {"seq": 1})  # published before anyone awaits
    assert await _drain(sub, 1) == [("audit.event", {"seq": 1})]


async def test_bounded_queue_drops_oldest_on_overflow():
    notifier = Notifier(max_queue=3)
    sub = notifier.subscribe()
    for i in range(5):
        await notifier.publish("audit.event", {"seq": i})
    assert sub.pending() == 3 and sub.dropped == 2
    assert [d["seq"] for _, d in await _drain(sub, 3)] == [2, 3, 4]


async def test_slow_subscriber_does_not_affect_others():
    notifier = Notifier(max_queue=2)
    slow, fast = notifier.subscribe(), notifier.subscribe()
    for i in range(4):
        await notifier.publish("e", {"i": i})
        assert (await _drain(fast, 1))[0][1] == {"i": i}
    assert slow.dropped == 2


async def test_aclose_and_garbage_collection_unsubscribe(notifier):
    sub = notifier.subscribe()
    await sub.aclose()
    assert notifier.subscriber_count == 0
    with pytest.raises(StopAsyncIteration):
        await sub.__anext__()
    notifier.subscribe()  # dropped immediately
    gc.collect()
    assert notifier.subscriber_count == 0


async def test_async_for_loop_and_context_manager(notifier):
    received = []

    async def consume():
        async with notifier.subscribe() as sub:
            async for event, data in sub:
                received.append((event, data))
                if len(received) == 2:
                    break

    task = asyncio.create_task(consume())
    await asyncio.sleep(0)
    await notifier.publish("a", {"n": 1})
    await notifier.publish("b", {"n": 2})
    await asyncio.wait_for(task, 1)
    assert received == [("a", {"n": 1}), ("b", {"n": 2})]
    assert notifier.subscriber_count == 0


async def test_publish_from_another_thread_is_delivered(notifier):
    sub = notifier.subscribe()
    thread = threading.Thread(target=notifier.publish_nowait, args=("audit.event", {"seq": 7}))
    thread.start()
    thread.join()
    assert await _drain(sub, 1) == [("audit.event", {"seq": 7})]


async def test_web_push_is_noop_without_vapid_keys(notifier, monkeypatch):
    calls = []
    monkeypatch.setattr(pywebpush, "webpush", lambda **kw: calls.append(kw))
    assert not notifier.push_enabled
    assert await notifier.web_push([SUB], {"title": "x"}) == 0
    assert calls == []


async def test_web_push_sends_and_reports_stale_endpoints(monkeypatch):
    public, private = generate_vapid_keys()
    notifier = Notifier(vapid_public_key=public, vapid_private_key=private)
    calls = []

    class Gone:
        status_code = 410
        text = "gone"

    def fake_webpush(**kwargs):
        calls.append(kwargs)
        if kwargs["subscription_info"]["endpoint"].endswith("/gone"):
            raise pywebpush.WebPushException("expired", response=Gone())

    monkeypatch.setattr(pywebpush, "webpush", fake_webpush)
    subs = [SUB, {"endpoint": "https://push.example/gone", "keys": {"p256dh": "k", "auth": "a"}},
            {"endpoint": "https://push.example/broken"}]  # malformed: skipped
    report = await notifier.web_push_detailed(subs, {"title": "مرصاد"})
    assert report.sent == 1 and report.failed == 1
    assert report.stale_endpoints == ["https://push.example/gone"]
    assert len(calls) == 2
    assert calls[0]["vapid_claims"] == {"sub": "mailto:security@najd-trading.example"}
    assert "مرصاد" in calls[0]["data"]
    assert await notifier.web_push([SUB], {"t": 1}) == 1


def test_generated_vapid_keys_are_usable_by_py_vapid():
    public, private = generate_vapid_keys()
    assert len(public) == 87 and len(private) == 43 and "=" not in public + private
    vapid = Vapid.from_string(private)
    headers = vapid.sign({"sub": "mailto:security@najd-trading.example", "aud": "https://push.example"})
    assert headers["Authorization"].startswith("vapid ")


def test_push_subscription_storage_round_trip(db):
    create_user(db, "approver1", "correct-horse-1", "approver")
    create_user(db, "auditor1", "correct-horse-2", "auditor")
    save_push_subscription(db, "approver1", SUB)
    save_push_subscription(db, "auditor1", {**SUB, "endpoint": "https://push.example/sub/2"})
    save_push_subscription(db, "approver1", {**SUB, "keys": {"p256dh": "New", "auth": "New"}})  # upsert
    subs = load_push_subscriptions(db)
    assert subs == [{"endpoint": SUB["endpoint"], "keys": {"p256dh": "New", "auth": "New"}}]
    assert len(load_push_subscriptions(db, roles=("auditor",))) == 1
    update_user(db, "approver1", disabled=True)
    assert load_push_subscriptions(db) == []
    assert delete_push_subscriptions(db, [SUB["endpoint"]]) == 1


def test_push_subscription_validation(db):
    create_user(db, "approver1", "correct-horse-1", "approver")
    with pytest.raises(ValueError):
        save_push_subscription(db, "approver1", {"endpoint": "https://push.example/x"})
    with pytest.raises(ValueError):
        save_push_subscription(db, "approver1", {**SUB, "endpoint": "http://insecure.example/x"})
    with pytest.raises(LookupError):
        save_push_subscription(db, "ghost", SUB)
