from __future__ import annotations

import csv
import io
import json
import time
from datetime import UTC, datetime

import pytest
from sqlalchemy import text

from mirsad.audit import EXPORT_FORMAT, AuditLog


@pytest.fixture
def populated(audit: AuditLog, db) -> AuditLog:
    rows = [
        ("tool_call.decision", "email-crm-assistant", "send_email", "deny", "s1", "c1",
         {"reasons": [{"code": "TAINT_UNTRUSTED_DESTINATION"}], "to": "data@evil.example"}),
        ("tool_call.decision", "email-crm-assistant", "read_email", "allow", "s1", "c2", {"email_id": "E-1042"}),
        ("tool_result.inspection", "email-crm-assistant", "read_email", "sanitize", "s1", "c2",
         {"detection": {"label": "injection"}, "note": "تجاهل التعليمات السابقة"}),
        ("tool_call.decision", "finance-bot", "transfer_funds", "require_approval", "s2", "c3",
         {"amount_sar": 9000, "memo": "100% urgent"}),
        ("approval.decided", "finance-bot", "transfer_funds", "deny", "s2", "c3", {"decided_by": "noura"}),
        ("system.started", None, None, None, None, None, {"version": "1.0.0"}),
    ]
    for event_type, agent, tool, action, session, call, payload in rows:
        audit.append(event_type, agent_id=agent, tool=tool, action=action, session_id=session, call_id=call,
                     payload=payload)
    # Spread timestamps deterministically: seq N happened at 1000 + N*100.
    with db.session() as sess:
        sess.execute(text("UPDATE audit_events SET ts = 1000 + seq * 100"))
    return audit


def test_query_filters_by_each_column(populated):
    assert populated.query(agent_id="finance-bot")[1] == 2
    assert populated.query(tool="read_email")[1] == 2
    assert populated.query(action="deny")[1] == 2
    assert populated.query(event_type="tool_call.decision")[1] == 3
    assert populated.query(session_id="s2")[1] == 2
    assert populated.query(call_id="c2")[1] == 2
    items, total = populated.query(agent_id="email-crm-assistant", action="allow")
    assert total == 1 and items[0].tool == "read_email"


def test_query_time_range(populated):
    items, total = populated.query(since=1300, until=1500, order="asc")
    assert total == 3 and [e.seq for e in items] == [3, 4, 5]
    dt = datetime.fromtimestamp(1400, tz=UTC)
    assert populated.query(since=dt)[1] == 3


def test_query_text_search_payload_tool_agent_case_insensitive(populated):
    assert {e.seq for e in populated.query(text="EVIL.EXAMPLE")[0]} == {1}
    assert {e.seq for e in populated.query(text="transfer")[0]} == {4, 5}
    assert {e.seq for e in populated.query(text="FINANCE")[0]} == {4, 5}
    assert {e.seq for e in populated.query(text="تجاهل التعليمات")[0]} == {3}


def test_query_text_wildcards_are_literal(populated):
    assert {e.seq for e in populated.query(text="100%")[0]} == {4}
    assert populated.query(text="%%%")[1] == 0
    assert populated.query(text="_")[1] >= 1  # literal underscore appears in tool names


def test_query_pagination_and_ordering(populated):
    page1, total = populated.query(limit=2, offset=0)
    page2, _ = populated.query(limit=2, offset=2)
    assert total == 6
    assert [e.seq for e in page1] == [6, 5] and [e.seq for e in page2] == [4, 3]
    asc, _ = populated.query(limit=3, order="asc")
    assert [e.seq for e in asc] == [1, 2, 3]
    empty, total = populated.query(limit=10, offset=100)
    assert empty == [] and total == 6
    with pytest.raises(ValueError):
        populated.query(order="sideways")


def test_get_returns_none_for_unknown_seq(populated):
    assert populated.get(999) is None
    assert populated.get(3).payload["detection"]["label"] == "injection"


def test_export_json_document(populated):
    doc = json.loads(populated.export("json", agent_id="finance-bot"))
    assert doc["format"] == EXPORT_FORMAT
    assert doc["count"] == 2 and [e["seq"] for e in doc["events"]] == [4, 5]
    assert doc["filters"] == {"agent_id": "finance-bot"}
    assert doc["head"]["seq"] == 6


def test_export_json_respects_limit_and_order(populated):
    doc = json.loads(populated.export("json", limit=2, order="desc"))
    assert [e["seq"] for e in doc["events"]] == [6, 5]


def test_export_csv_rows_and_header(populated):
    out = populated.export("csv", tool="transfer_funds")
    rows = list(csv.DictReader(io.StringIO(out)))
    assert [r["seq"] for r in rows] == ["4", "5"]
    assert rows[0]["action"] == "require_approval"
    assert json.loads(rows[0]["payload_json"])["amount_sar"] == 9000
    assert rows[0]["ts_iso"].startswith("1970-01-01T00:")
    assert len(rows[0]["hash"]) == 64


def test_export_csv_neutralises_formula_injection(audit):
    audit.append("tool_call.decision", agent_id="=HYPERLINK(\"http://evil.example\")", tool="@SUM(A1)")
    rows = list(csv.DictReader(io.StringIO(audit.export("csv"))))
    assert rows[0]["agent_id"].startswith("'=")
    assert rows[0]["tool"].startswith("'@")


def test_export_rejects_bad_format_and_unknown_filters(populated):
    with pytest.raises(ValueError):
        populated.export("xml")
    with pytest.raises(TypeError):
        populated.export("json", colour="red")


def test_export_streams_more_than_one_batch(audit):
    for i in range(1205):
        audit.append("x", payload={"i": i})
    doc = json.loads(audit.export("json"))
    assert doc["count"] == 1205 and doc["events"][-1]["seq"] == 1205
    assert audit.verify().checked == 1205


def test_query_since_until_accept_current_time(audit):
    before = time.time() - 1
    audit.append("x")
    assert audit.query(since=before)[1] == 1
    assert audit.query(until=before)[1] == 0
