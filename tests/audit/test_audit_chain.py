from __future__ import annotations

import hashlib
import hmac
import json
import threading

import pytest
from sqlalchemy import select, text

from mirsad.audit import (
    GENESIS_HASH,
    AuditLog,
    audit_key_from_secret,
    canonical_json,
    compute_hash,
    verify_events,
)
from mirsad.models import Action, Risk
from mirsad.storage import AuditEventRow

from .conftest import HMAC_KEY


def _fill(audit: AuditLog, n: int = 5) -> None:
    for i in range(n):
        audit.append("tool_call.decision", session_id="s1", agent_id="email-crm-assistant", tool="send_email",
                     call_id=f"call_{i}", action=Action.ALLOW, risk=Risk.LOW, policy_version="v1",
                     payload={"i": i, "note": "طلب عميل"})


def _rechain_from(db, key: bytes, start_seq: int) -> None:
    """What an attacker would do: recompute every hash from ``start_seq`` with ``key``."""
    with db.session() as sess:
        rows = sess.scalars(select(AuditEventRow).order_by(AuditEventRow.seq)).all()
        prev = GENESIS_HASH
        for row in rows:
            if row.seq >= start_seq:
                body = {"seq": row.seq, "ts": row.ts, "event_type": row.event_type, "session_id": row.session_id,
                        "agent_id": row.agent_id, "tool": row.tool, "call_id": row.call_id, "action": row.action,
                        "risk": row.risk, "policy_version": row.policy_version,
                        "payload": json.loads(row.payload_json), "prev_hash": prev}
                row.prev_hash = prev
                row.hash = compute_hash(key, prev, body)
            prev = row.hash


def test_append_assigns_sequential_seq_and_links_hashes(audit):
    _fill(audit, 3)
    events = [audit.get(i) for i in (1, 2, 3)]
    assert [e.seq for e in events] == [1, 2, 3]
    assert events[0].prev_hash == GENESIS_HASH
    assert events[1].prev_hash == events[0].hash
    assert events[2].prev_hash == events[1].hash
    assert events[0].action == "allow" and events[0].risk == "low"
    assert audit.head() == (3, events[2].hash)


def test_hash_is_hmac_over_prev_hash_and_canonical_json(audit):
    event = audit.append("system.started", payload={"b": 1, "a": "مرصاد"})
    body = event.model_dump()
    body.pop("hash")
    expected = hmac.new(HMAC_KEY, f"{event.prev_hash}|{canonical_json(body)}".encode(), hashlib.sha256).hexdigest()
    assert event.hash == expected
    assert canonical_json({"b": 1, "a": "مرصاد"}) == '{"a":"مرصاد","b":1}'


def test_verify_ok_on_empty_and_populated_log(audit):
    empty = audit.verify()
    assert empty.ok and empty.checked == 0 and empty.head_seq == 0 and empty.head_hash == GENESIS_HASH
    _fill(audit, 10)
    report = audit.verify()
    assert report.ok and report.checked == 10 and report.head_seq == 10 and report.first_bad_seq is None


def test_verify_detects_modified_payload(audit, db):
    _fill(audit, 5)
    with db.session() as sess:
        sess.execute(text("UPDATE audit_events SET payload_json = :p WHERE seq = 3"), {"p": '{"i":2,"note":"edited"}'})
    report = audit.verify()
    assert not report.ok and report.first_bad_seq == 3 and "HMAC" in report.message
    assert report.checked == 2


def test_verify_detects_modified_indexed_column(audit, db):
    _fill(audit, 4)
    with db.session() as sess:
        sess.execute(text("UPDATE audit_events SET action = 'deny' WHERE seq = 2"))
    report = audit.verify()
    assert not report.ok and report.first_bad_seq == 2


def test_verify_detects_deleted_row(audit, db):
    _fill(audit, 6)
    with db.session() as sess:
        sess.execute(text("DELETE FROM audit_events WHERE seq = 4"))
    report = audit.verify()
    assert not report.ok and report.first_bad_seq == 5 and "missing" in report.message


def test_verify_detects_deleted_first_row(audit, db):
    _fill(audit, 3)
    with db.session() as sess:
        sess.execute(text("DELETE FROM audit_events WHERE seq = 1"))
    report = audit.verify()
    assert not report.ok and report.first_bad_seq == 2


def test_verify_detects_reordered_rows(audit, db):
    _fill(audit, 5)
    with db.session() as sess:  # swap the seq numbers of events 2 and 3
        sess.execute(text("UPDATE audit_events SET seq = -2 WHERE seq = 2"))
        sess.execute(text("UPDATE audit_events SET seq = 2 WHERE seq = 3"))
        sess.execute(text("UPDATE audit_events SET seq = 3 WHERE seq = -2"))
    report = audit.verify()
    assert not report.ok and report.first_bad_seq == 2


def test_verify_detects_forged_rechain_without_key(audit, db):
    _fill(audit, 6)
    with db.session() as sess:
        sess.execute(text("UPDATE audit_events SET payload_json = :p WHERE seq = 4"), {"p": '{"i":3,"note":"forged"}'})
    _rechain_from(db, b"attacker-guess-of-the-key-000000000", 4)
    report = audit.verify()
    assert not report.ok and report.first_bad_seq == 4


def test_verify_detects_plain_sha256_forgery(audit, db):
    _fill(audit, 3)
    with db.session() as sess:
        row = sess.get(AuditEventRow, 3)
        row.payload_json = '{"i":2,"note":"x"}'
        row.hash = hashlib.sha256(f"{row.prev_hash}|forged".encode()).hexdigest()
    report = audit.verify()
    assert not report.ok and report.first_bad_seq == 3


def test_key_holder_rewrite_passes_chain_but_fails_external_anchor(audit, db):
    _fill(audit, 5)
    anchor = audit.anchor()
    assert anchor["seq"] == 5 and set(anchor) == {"seq", "hash", "ts"}
    with db.session() as sess:
        sess.execute(text("UPDATE audit_events SET payload_json = :p WHERE seq = 2"), {"p": '{"i":1,"note":"rewritten"}'})
    _rechain_from(db, HMAC_KEY, 2)
    assert audit.verify().ok  # documented limitation: the key holder can rewrite history
    report = audit.verify(anchor=anchor)
    assert not report.ok and report.anchor_ok is False and report.first_bad_seq == 5


def test_tail_truncation_detected_only_with_anchor(audit, db):
    _fill(audit, 5)
    anchor = audit.anchor()
    with db.session() as sess:
        sess.execute(text("DELETE FROM audit_events WHERE seq >= 4"))
    assert audit.verify().ok
    report = audit.verify(anchor=anchor)
    assert not report.ok and "truncated" in report.message


def test_anchor_matches_when_untampered(audit):
    _fill(audit, 3)
    anchor = audit.anchor()
    _fill(audit, 2)
    report = audit.verify(anchor=anchor)
    assert report.ok and report.anchor_ok is True


def test_wrong_key_fails_verification(db):
    AuditLog(db, HMAC_KEY).append("system.started")
    report = AuditLog(db, b"some-other-key-that-is-long-enough").verify()
    assert not report.ok and report.first_bad_seq == 1


def test_payload_is_redacted_before_storage(audit, db):
    audit.append("auth.login_failed", payload={"username": "noura", "password": "Sup3rSecret!",
                                               "headers": {"Authorization": "Bearer abcdef0123456789abcdef"}})
    with db.session() as sess:
        stored = sess.get(AuditEventRow, 1).payload_json
    assert "Sup3rSecret" not in stored and "abcdef0123456789" not in stored
    assert '"username":"noura"' in stored
    assert audit.verify().ok


def test_large_payload_truncated_with_marker_and_still_verifies(db):
    audit = AuditLog(db, HMAC_KEY, payload_max_chars=2_000)
    event = audit.append("tool_result.inspection", payload={"result": {"content": "A" * 50_000}, "action": "pass"})
    assert event.payload["_truncated"] is True
    assert event.payload["_original_chars"] > 50_000
    assert event.payload["action"] == "pass"  # structure is kept
    assert len(canonical_json(event.payload)) <= 2_000
    assert audit.verify().ok


def test_payload_with_too_many_keys_falls_back_to_preview(db):
    audit = AuditLog(db, HMAC_KEY, payload_max_chars=500)
    event = audit.append("x", payload={f"k{i}": i for i in range(500)})
    assert event.payload["_truncated"] is True and "_preview" in event.payload
    assert audit.verify().ok


def test_concurrent_appends_from_threads_keep_chain_valid(audit):
    def worker(n: int) -> None:
        for i in range(20):
            audit.append("tool_call.decision", agent_id=f"agent-{n}", payload={"i": i})

    threads = [threading.Thread(target=worker, args=(n,)) for n in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    report = audit.verify()
    assert report.ok and report.checked == 160 and report.head_seq == 160


def test_two_writers_on_same_database_stay_consistent(db):
    """Two AuditLog instances (like two worker processes) only share the database."""
    a, b = AuditLog(db, HMAC_KEY), AuditLog(db, HMAC_KEY)

    def worker(log: AuditLog) -> None:
        for i in range(25):
            log.append("x", payload={"i": i})

    threads = [threading.Thread(target=worker, args=(w,)) for w in (a, b, a, b)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    report = a.verify()
    assert report.ok and report.head_seq == 100


def test_listener_receives_events_and_failures_are_isolated(audit):
    seen = []
    audit.add_listener(lambda e: (_ for _ in ()).throw(RuntimeError("listener bug")))
    audit.add_listener(seen.append)
    event = audit.append("system.started")
    assert seen == [event]


def test_offline_verification_of_json_export(audit):
    _fill(audit, 4)
    doc = json.loads(audit.export("json"))
    assert doc["count"] == 4 and doc["head"]["seq"] == 4
    assert verify_events(doc["events"], HMAC_KEY).ok
    doc["events"][1]["payload"]["note"] = "changed offline"
    report = verify_events(doc["events"], HMAC_KEY)
    assert not report.ok and report.first_bad_seq == 2


def test_audit_key_derivation_is_deterministic_and_separated():
    k1 = audit_key_from_secret("app-secret")
    assert k1 == audit_key_from_secret(b"app-secret") and len(k1) == 32
    assert k1 != b"app-secret" and k1 != audit_key_from_secret("other-secret")


def test_invalid_construction_and_arguments(db):
    with pytest.raises(ValueError):
        AuditLog(db, b"")
    with pytest.raises(ValueError):
        AuditLog(db, HMAC_KEY).append("")
