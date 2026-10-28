"""Storage, audit chain, approvals and auth against a real PostgreSQL server (NFR: portable persistence).

Uses the ``pgserver`` package, which ships PostgreSQL binaries; skipped when it is not installed.
"""

from __future__ import annotations

import asyncio

import pytest
from sqlalchemy import text

pgserver = pytest.importorskip("pgserver")
pytest.importorskip("psycopg")

from mirsad.approvals import ApprovalService, Notifier  # noqa: E402
from mirsad.audit import AuditLog  # noqa: E402
from mirsad.auth import authenticate_agent_key, authenticate_user, create_agent, create_user  # noqa: E402
from mirsad.models import Action, Decision, ToolCall  # noqa: E402
from mirsad.storage import Database  # noqa: E402

pytestmark = pytest.mark.slow


@pytest.fixture(scope="module")
def pg_url(tmp_path_factory):
    server = pgserver.get_server(tmp_path_factory.mktemp("pgdata"), cleanup_mode="stop")
    uri = server.get_uri()  # postgresql://postgres:@/postgres?host=/socket/dir
    server.psql("CREATE DATABASE mirsad_test;")
    yield uri.replace("postgresql://", "postgresql+psycopg://", 1).replace("/postgres?", "/mirsad_test?", 1)
    server.cleanup()


@pytest.fixture
def db(pg_url):
    database = Database(pg_url)
    database.create_all()
    yield database
    with database.session() as s:
        for table in ("approvals", "push_subscriptions", "audit_events", "policies", "agents", "users"):
            s.execute(text(f"DELETE FROM {table}"))  # noqa: S608 - fixed table names
        s.commit()


def test_audit_chain_appends_and_verifies_on_postgres(db):
    log = AuditLog(db, b"k" * 32)
    for i in range(25):
        log.append("tool_call.decision", agent_id="a", tool="t", action="allow", payload={"i": i, "text": "مرحبا"})
    report = log.verify()
    assert report.ok and report.checked == 25
    events, total = log.query(tool="t", limit=5)
    assert total == 25 and len(events) == 5
    assert "مرحبا" in log.export("json")


def test_audit_tampering_detected_on_postgres(db):
    log = AuditLog(db, b"k" * 32)
    for i in range(5):
        log.append("tool_call.decision", agent_id="a", tool="t", action="deny", payload={"i": i})
    with db.session() as s:
        s.execute(text("UPDATE audit_events SET action='allow' WHERE seq = (SELECT MIN(seq) + 2 FROM audit_events)"))
        s.commit()
    assert log.verify().ok is False


def test_auth_round_trip_on_postgres(db):
    create_user(db, "noura", "a-strong-password", "approver")
    assert authenticate_user(db, "noura", "a-strong-password").role == "approver"
    assert authenticate_user(db, "noura", "wrong-password-x") is None
    info, key = create_agent(db, "crm-bot", "CRM Bot", "email-crm-assistant")
    assert authenticate_agent_key(db, key).id == "crm-bot"


def test_approval_lifecycle_on_postgres(db):
    async def scenario():
        service = ApprovalService(db, Notifier(), timeout_s=5)
        call = ToolCall(session_id="s", agent_id="crm-bot", tool="delete_customer", arguments={"customer_id": "C001"})
        decision = Decision(call_id=call.call_id, action=Action.REQUIRE_APPROVAL)
        record = await service.request(call, decision, agent_name="CRM Bot")
        waiter = asyncio.create_task(service.wait(record.id))
        await asyncio.sleep(0.05)
        await service.decide(record.id, approve=True, user="noura", note="ok")
        final = await waiter
        await service.aclose()
        return final

    final = asyncio.run(scenario())
    assert final.status.value == "approved" and final.decided_by == "noura"
