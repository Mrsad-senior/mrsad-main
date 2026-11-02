"""Blue-team triage: turn the Mirsad audit log into an incident queue.

    python scripts/soc_triage.py                 # incident queue
    python scripts/soc_triage.py --incident 3    # full timeline + IOCs for one incident

Logs in as an admin/auditor (MIRSAD_SOC_USER / MIRSAD_SOC_PASSWORD, or the admin line of
.mirsad/credentials.txt). The password is never printed. Read-only: it changes nothing.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from collections import defaultdict
from pathlib import Path

import httpx

WRITE_TOOLS = {"transfer_funds", "approve_payment", "send_email", "send_lab_results", "update_prescription",
               "delete_customer", "export_customers", "update_customer_note", "book_appointment", "fetch_url"}
SEV_ORDER = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}
# The audit log masks IBANs to country + last four ("SA****...0001"); that is still enough to correlate.
IBAN = re.compile(r"\b[A-Z]{2}[\d*][\d*\s.-]{12,40}\d{4}\b")
EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
URL = re.compile(r"https?://[^\s\"'<>)\]]+")


def login(base: str, creds: Path) -> httpx.Client:
    user, pw = os.getenv("MIRSAD_SOC_USER"), os.getenv("MIRSAD_SOC_PASSWORD")
    if not (user and pw):
        m = re.search(r"^admin\s+username=(\S+)\s+password=(\S+)", creds.read_text(encoding="utf-8"), re.M)
        if not m:
            sys.exit("no credentials: set MIRSAD_SOC_USER / MIRSAD_SOC_PASSWORD")
        user, pw = m.groups()
    client = httpx.Client(base_url=base, timeout=60)
    r = client.post("/api/auth/login", json={"username": user, "password": pw})
    r.raise_for_status()
    client.headers["Authorization"] = f"Bearer {r.json()['access_token']}"
    return client


def fetch_events(client: httpx.Client) -> list[dict]:
    events, offset = [], 0
    while True:
        page = client.get("/api/audit/events", params={"limit": 1000, "offset": offset, "order": "asc"}).json()
        events += page["items"]
        offset += len(page["items"])
        if not page["items"] or offset >= page["total"]:
            return events


def blocking_codes(payload: dict) -> list[str]:
    return [f"{r['layer']}:{r['code']}" for r in payload.get("reasons", []) if r.get("action") != "allow"]


def iocs(text: str) -> set[str]:
    ibans = {f"IBAN {m[:2]}…{m[-4:]}" for m in IBAN.findall(text)}
    return ibans | set(EMAIL.findall(text)) | set(URL.findall(text))


def build_incidents(events: list[dict], internal: tuple[str, ...]) -> list[dict]:
    sessions: dict[str, list[dict]] = defaultdict(list)
    failed_logins: dict[str, list[dict]] = defaultdict(list)
    for e in events:
        if e["event_type"] == "auth.login_failed":
            failed_logins[(e.get("payload") or {}).get("username", "?")].append(e)
        elif e.get("session_id") and e["event_type"].startswith(("tool_call", "tool_result", "approval")):
            sessions[e["session_id"]].append(e)

    incidents = []
    for sid, evs in sessions.items():
        missed, caught, attempts, policy_hits, human = [], [], [], [], []
        indicators: set[str] = set()
        for e in evs:
            p = e.get("payload") or {}
            if e["event_type"] == "tool_result.inspection":
                det = p.get("detection") or {}
                if e["action"] in ("block", "sanitize", "flag"):
                    caught.append(e)
                    indicators |= iocs((p.get("result") or {}).get("content", ""))
                elif det and (p.get("profile") or {}).get("trust") == "untrusted":
                    missed.append(e)  # untrusted content the detector let through
            elif e["event_type"] == "tool_call.decision" and e["action"] != "allow":
                args = json.dumps((p.get("call") or {}).get("arguments", {}), ensure_ascii=False)
                (attempts if e["tool"] in WRITE_TOOLS else policy_hits).append(e)
                indicators |= iocs(args)
            elif e["event_type"] == "approval.decided":
                human.append(e)
        indicators = {i for i in indicators if not any(i.endswith(d) or f"//{d}" in i or f".{d}" in i
                                                       for d in internal)}
        untrusted_flow = any(c.startswith("taint:TAINT_UNTRUSTED") for e in attempts
                             for c in blocking_codes(e.get("payload") or {}))
        if attempts and missed and untrusted_flow:
            sev, title = "CRITICAL", "Detector missed injection; harmful action stopped at action layer"
        elif attempts:
            sev, title = "HIGH", "Harmful action attempted and stopped"
        elif any(e["action"] in ("block", "sanitize") for e in caught):
            sev, title = "MEDIUM", "Injection detected in untrusted content; content withheld"
        elif caught:
            sev, title = "MEDIUM", "Suspicious untrusted content flagged (delivered; watch for follow-up actions)"
        elif policy_hits:
            sev, title = "MEDIUM", "Policy violation (tool or parameter not allowed)"
        else:
            continue
        codes = sorted({c for e in attempts + policy_hits for c in blocking_codes(e.get("payload") or {})})
        principal = str((evs[0].get("payload") or {}).get("principal") or "")
        source = "demo-console" if principal.startswith("demo:") else f"api:{principal[:12]}"
        incidents.append({
            "severity": sev, "title": title, "session": sid, "agent": evs[0].get("agent_id"), "source": source,
            "first": evs[0]["ts"], "last": evs[-1]["ts"], "events": evs, "layers": codes,
            "attempted": [f"{e['tool']}({json.dumps((e['payload'].get('call') or {}).get('arguments', {}), ensure_ascii=False)[:80]})"
                          for e in attempts],
            "iocs": sorted(indicators), "human_decisions": len(human),
        })
    for user, evs in failed_logins.items():
        if len(evs) >= 3:
            incidents.append({"severity": "HIGH" if len(evs) >= 5 else "MEDIUM",
                              "title": f"{len(evs)} failed logins for '{user}'", "session": f"auth:{user}",
                              "agent": "-", "source": "login", "first": evs[0]["ts"], "last": evs[-1]["ts"], "events": evs,
                              "layers": [], "attempted": [], "iocs": sorted({(e.get('payload') or {}).get('ip', '?') for e in evs}),
                              "human_decisions": 0})
    incidents.sort(key=lambda i: (SEV_ORDER[i["severity"]], -i["last"]))
    return incidents


def ts(t: float) -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(t))


def show_queue(incidents: list[dict], chain: dict) -> None:
    print(f"Audit chain: {'OK' if chain.get('ok') else 'BROKEN'} ({chain.get('message')})\n")
    counts = defaultdict(int)
    for i in incidents:
        counts[i["severity"]] += 1
    print("Open incidents: " + ", ".join(f"{k} {counts[k]}" for k in SEV_ORDER if counts[k]) + "\n")
    print(f"{'#':>3}  {'SEV':<8} {'LAST SEEN':<19}  {'AGENT':<21} {'SOURCE':<17} TITLE")
    for n, i in enumerate(incidents, 1):
        print(f"{n:>3}  {i['severity']:<8} {ts(i['last'])}  {str(i['agent'])[:21]:<21} {i['source']:<17} {i['title']}")
        if i["attempted"]:
            print(f"{'':>15}attempted: {'; '.join(i['attempted'])[:150]}")
        if i["iocs"]:
            print(f"{'':>15}IOCs: {', '.join(i['iocs'])[:150]}")


def show_incident(n: int, inc: dict) -> None:
    print(f"INCIDENT #{n}  [{inc['severity']}]  {inc['title']}")
    print(f"session={inc['session']}  agent={inc['agent']}  source={inc['source']}  "
          f"{ts(inc['first'])} -> {ts(inc['last'])}")
    print(f"layers that fired: {', '.join(inc['layers']) or '-'}")
    print(f"IOCs: {', '.join(inc['iocs']) or '-'}\n\nTIMELINE")
    for e in inc["events"]:
        p = e.get("payload") or {}
        line = f"  seq {e['seq']:>4}  {ts(e['ts'])}  {e['event_type']:<24} {str(e.get('tool') or ''):<20} -> {e.get('action')}"
        print(line)
        if e["event_type"] == "tool_call.decision":
            print(f"            args: {json.dumps((p.get('call') or {}).get('arguments', {}), ensure_ascii=False)[:160]}")
            for r in p.get("reasons", []):
                if r.get("action") != "allow":
                    print(f"            [{r['layer']}:{r['code']} -> {r['action']}] {r.get('message', '')[:130]}")
        elif e["event_type"] == "tool_result.inspection":
            det = p.get("detection") or {}
            if det:
                print(f"            detector score={det.get('score')} label={det.get('label')} layers={det.get('layer_scores')}")
                judge = (det.get("layer_reasons") or {}).get("llm_judge")
                if judge:
                    print(f"            judge: {judge[:160]}")
            content = (p.get("result") or {}).get("content", "")
            print(f"            content: {content[:220]!r}")
        elif e["event_type"].startswith("approval"):
            print(f"            {json.dumps({k: p.get(k) for k in ('status', 'decided_by', 'note', 'final_action')}, ensure_ascii=False)}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--url", default="http://127.0.0.1:8700")
    ap.add_argument("--creds", type=Path, default=Path(".mirsad/credentials.txt"))
    ap.add_argument("--incident", type=int, help="show the full timeline of incident N from the queue")
    ap.add_argument("--internal", default="najd-trading.example,najd-health.example",
                    help="comma-separated internal domains (excluded from IOCs)")
    args = ap.parse_args()
    client = login(args.url, args.creds)
    incidents = build_incidents(fetch_events(client), tuple(d for d in args.internal.split(",") if d))
    if args.incident:
        if not 1 <= args.incident <= len(incidents):
            sys.exit(f"no incident #{args.incident} (queue has {len(incidents)})")
        show_incident(args.incident, incidents[args.incident - 1])
    else:
        show_queue(incidents, client.post("/api/audit/verify").json())


if __name__ == "__main__":
    main()
