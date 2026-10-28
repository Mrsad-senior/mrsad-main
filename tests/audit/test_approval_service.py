from __future__ import annotations

import asyncio
import threading
import time

import pytest
import pywebpush

from mirsad.approvals import (
    AUTO_DECIDER_USER,
    ApprovalNotFound,
    ApprovalService,
    Notifier,
    generate_vapid_keys,
    load_push_subscriptions,
    save_push_subscription,
)
from mirsad.auth import create_user
from mirsad.models import ApprovalStatus

from .conftest import make_call, make_decision


async def _request(service: ApprovalService, **call_overrides):
    call = make_call(**call_overrides)
    return await service.request(call, make_decision(call), agent_name="Email & CRM Assistant")


async def test_request_persists_pending_record_and_publishes(service, notifier):
    sub = notifier.subscribe()
    record = await _request(service)
    assert record.status == ApprovalStatus.PENDING and record.id.startswith("apr_")
    assert record.expires_at == pytest.approx(record.created_at + 30)
    assert record.decision.approval_id == record.id and record.decision.approval_status == "pending"
    assert record.risk.value == "critical" and record.tool == "send_email"
    assert "data@evil.example" in record.summary_en and record.summary_ar
    assert service.get(record.id) == record
    event, data = await asyncio.wait_for(sub.__anext__(), 1)
    assert event == "approval.requested" and data["id"] == record.id and data["status"] == "pending"


async def test_request_redacts_secret_arguments(service):
    record = await _request(service, tool="call_api",
                            arguments={"url": "https://api.evil.example", "api_key": "sk-proj-AbCdEf0123456789GhIj"})
    assert record.arguments["api_key"] == "[REDACTED]"
    assert "AbCdEf0123456789" not in record.summary_en
    assert service.get(record.id).arguments["url"] == "https://api.evil.example"


async def test_approve_wakes_waiter(service, notifier):
    record = await _request(service)
    sub = notifier.subscribe()
    waiter = asyncio.create_task(service.wait(record.id))
    await asyncio.sleep(0.01)
    assert not waiter.done()
    decided = await service.decide(record.id, approve=True, user="noura", note="expected email")
    result = await asyncio.wait_for(waiter, 1)
    assert result.status == ApprovalStatus.APPROVED == decided.status
    assert result.decided_by == "noura" and result.note == "expected email" and result.decided_at
    assert result.decision.approval_status == "approved"
    event, data = await asyncio.wait_for(sub.__anext__(), 1)
    assert event == "approval.decided" and data["status"] == "approved"


async def test_deny(service):
    record = await _request(service)
    denied = await service.decide(record.id, approve=False, user="noura")
    assert denied.status == ApprovalStatus.DENIED
    assert (await service.wait(record.id)).status == ApprovalStatus.DENIED


async def test_wait_timeout_marks_expired_and_publishes(service, notifier):
    record = await _request(service)
    sub = notifier.subscribe()
    started = time.monotonic()
    result = await service.wait(record.id, timeout_s=0.2)
    assert 0.15 <= time.monotonic() - started < 2
    assert result.status == ApprovalStatus.EXPIRED and result.decided_by is None
    event, data = await asyncio.wait_for(sub.__anext__(), 1)
    assert event == "approval.decided" and data["status"] == "expired"
    with pytest.raises(ValueError):  # a late click cannot approve it any more
        await service.decide(record.id, approve=True, user="noura")


async def test_record_deadline_expires_without_explicit_timeout(db, notifier):
    service = ApprovalService(db, notifier, timeout_s=0.2)
    record = await _request(service)
    assert (await asyncio.wait_for(service.wait(record.id), 2)).status == ApprovalStatus.EXPIRED


async def test_decide_twice_raises_value_error(service):
    record = await _request(service)
    await service.decide(record.id, approve=True, user="noura")
    with pytest.raises(ValueError, match="already approved"):
        await service.decide(record.id, approve=False, user="bader")
    assert service.get(record.id).decided_by == "noura"


async def test_decide_unknown_or_without_user(service):
    with pytest.raises(ApprovalNotFound):
        await service.decide("apr_missing", approve=True, user="noura")
    with pytest.raises(ApprovalNotFound):
        await service.wait("apr_missing")
    record = await _request(service)
    with pytest.raises(ValueError):
        await service.decide(record.id, approve=True, user="")


async def test_decide_after_deadline_expires_instead(db, notifier):
    service = ApprovalService(db, notifier, timeout_s=0.05)
    record = await _request(service)
    await asyncio.sleep(0.1)
    with pytest.raises(ValueError, match="expired"):
        await service.decide(record.id, approve=True, user="noura")
    assert service.get(record.id).status == ApprovalStatus.EXPIRED


async def test_expire_overdue(db, notifier):
    service = ApprovalService(db, notifier, timeout_s=0.05)
    sub = notifier.subscribe()
    first, second = await _request(service), await _request(service)
    await service.decide(second.id, approve=True, user="noura")
    long_lived = ApprovalService(db, notifier, timeout_s=60)
    third = await _request(long_lived)
    await asyncio.sleep(0.1)
    assert service.expire_overdue() == 1
    assert service.get(first.id).status == ApprovalStatus.EXPIRED
    assert service.get(third.id).status == ApprovalStatus.PENDING
    assert service.expire_overdue() == 0
    # 3 requested + 1 approved + 1 expired
    events = [await asyncio.wait_for(sub.__anext__(), 1) for _ in range(5)]
    assert ("approval.decided", "expired") in {(e, d["status"]) for e, d in events}


@pytest.mark.parametrize(("verdict", "expected"), [(True, ApprovalStatus.APPROVED), (False, ApprovalStatus.DENIED)])
async def test_auto_decider_decides_immediately(db, notifier, verdict, expected):
    seen = []

    def decider(record):
        seen.append(record)
        return verdict

    service = ApprovalService(db, notifier, timeout_s=30, auto_decider=decider)
    record = await _request(service)
    assert record.status == expected and record.decided_by == AUTO_DECIDER_USER
    assert seen[0].status == ApprovalStatus.PENDING and seen[0].tool == "send_email"
    assert (await asyncio.wait_for(service.wait(record.id), 1)).status == expected


async def test_auto_decider_none_or_error_waits_for_human(db, notifier):
    for decider in (lambda r: None, lambda r: 1 / 0):
        service = ApprovalService(db, notifier, timeout_s=30, auto_decider=decider)
        record = await _request(service)
        assert record.status == ApprovalStatus.PENDING
        await service.decide(record.id, approve=False, user="noura")


async def test_concurrent_waiters_all_wake_on_one_decision(service):
    record = await _request(service)
    waiters = [asyncio.create_task(service.wait(record.id)) for _ in range(5)]
    await asyncio.sleep(0.01)
    await service.decide(record.id, approve=True, user="noura")
    results = await asyncio.wait_for(asyncio.gather(*waiters), 1)
    assert {r.status for r in results} == {ApprovalStatus.APPROVED}
    assert service._waiters == {}


async def test_concurrent_deciders_exactly_one_wins(service):
    record = await _request(service)
    outcomes = await asyncio.gather(
        *(service.decide(record.id, approve=i % 2 == 0, user=f"user{i}") for i in range(6)),
        return_exceptions=True,
    )
    wins = [o for o in outcomes if not isinstance(o, Exception)]
    assert len(wins) == 1
    assert all(isinstance(o, ValueError) for o in outcomes if isinstance(o, Exception))


async def test_waiting_does_not_busy_poll(service, monkeypatch):
    record = await _request(service)
    reads = 0
    original_get = service.get

    def counting_get(approval_id):
        nonlocal reads
        reads += 1
        return original_get(approval_id)

    monkeypatch.setattr(service, "get", counting_get)
    waiter = asyncio.create_task(service.wait(record.id))
    await asyncio.sleep(0.5)
    assert reads <= 2  # parked on an asyncio.Event, not polling the database
    await service.decide(record.id, approve=True, user="noura")
    await asyncio.wait_for(waiter, 1)


async def test_decision_from_another_thread_wakes_waiter(service):
    record = await _request(service)
    waiter = asyncio.create_task(service.wait(record.id))
    await asyncio.sleep(0.01)
    thread = threading.Thread(
        target=lambda: asyncio.run(service.decide(record.id, approve=True, user="remote")))
    thread.start()
    result = await asyncio.wait_for(waiter, 2)
    thread.join()
    assert result.status == ApprovalStatus.APPROVED and result.decided_by == "remote"


async def test_cancel(service):
    record = await _request(service)
    cancelled = await service.cancel(record.id, note="session closed")
    assert cancelled.status == ApprovalStatus.CANCELLED
    with pytest.raises(ValueError):
        await service.cancel(record.id)


async def test_list_filters_and_orders_newest_first(service):
    ids = [(await _request(service, call_id=f"call_{i}")).id for i in range(4)]
    await service.decide(ids[0], approve=True, user="noura")
    listed = service.list()
    assert [r.id for r in listed] == list(reversed(ids))
    assert [r.id for r in service.list(status=ApprovalStatus.PENDING)] == list(reversed(ids[1:]))
    assert [r.id for r in service.list(status=ApprovalStatus.APPROVED)] == [ids[0]]
    assert len(service.list(limit=2)) == 2


async def test_request_triggers_web_push_and_prunes_stale_subscriptions(db, monkeypatch):
    public, private = generate_vapid_keys()
    notifier = Notifier(vapid_public_key=public, vapid_private_key=private)
    create_user(db, "approver1", "correct-horse-1", "approver")
    save_push_subscription(db, "approver1", {"endpoint": "https://push.example/ok", "keys": {"p256dh": "k", "auth": "a"}})
    save_push_subscription(db, "approver1", {"endpoint": "https://push.example/gone", "keys": {"p256dh": "k", "auth": "a"}})
    sent = []

    class Gone:
        status_code = 410
        text = "gone"

    def fake_webpush(**kwargs):
        sent.append(kwargs)
        if kwargs["subscription_info"]["endpoint"].endswith("/gone"):
            raise pywebpush.WebPushException("gone", response=Gone())

    monkeypatch.setattr(pywebpush, "webpush", fake_webpush)
    service = ApprovalService(db, notifier, timeout_s=30)
    record = await _request(service)
    await service.aclose()
    assert len(sent) == 2 and record.id in sent[0]["data"]
    assert [s["endpoint"] for s in load_push_subscriptions(db)] == ["https://push.example/ok"]


def test_invalid_timeout_rejected(db, notifier):
    with pytest.raises(ValueError):
        ApprovalService(db, notifier, timeout_s=0)
