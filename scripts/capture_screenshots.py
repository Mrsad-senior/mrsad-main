"""Capture report screenshots of the running system (dashboard + approver PWA, English and Arabic).

1. Initialises a temporary data directory with demo users and the demo agent (``mirsad init --demo``).
2. Starts ``mirsad serve --demo`` on a free port.
3. Generates realistic activity through the real API with the demo agent key: allowed reads,
   policy denials (bulk export, large transfer, internal-network URL, unknown tool) and approval requests,
   some decided and some left pending.
4. Uses Playwright with the installed Chrome to screenshot every page into docs/figures/screens/.

Usage: python scripts/capture_screenshots.py [--out docs/figures/screens]
"""

from __future__ import annotations

import argparse
import os
import re
import socket
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

import httpx
from playwright.sync_api import Page, sync_playwright

ROOT = Path(__file__).resolve().parent.parent


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def read_credentials(path: Path) -> dict[str, str]:
    text = path.read_text(encoding="utf-8")
    creds: dict[str, str] = {}
    for role, user, pw in re.findall(r"^(\w+)\s+username=(\S+)\s+password=(\S+)", text, flags=re.M):
        creds[f"{role}_user"], creds[f"{role}_password"] = user, pw
    key = re.search(r"api_key=(\S+)", text)
    if key:
        creds["agent_key"] = key.group(1)
    return creds


def seed_activity(base: str, creds: dict[str, str]) -> None:
    agent = {"Authorization": f"Bearer {creds['agent_key']}"}
    admin_token = httpx.post(f"{base}/api/auth/login", json={"username": creds["admin_user"],
                                                             "password": creds["admin_password"]}).json()["access_token"]
    approver_token = httpx.post(f"{base}/api/auth/login", json={"username": creds["approver_user"],
                                                                "password": creds["approver_password"]}
                                ).json()["access_token"]
    approver = {"Authorization": f"Bearer {approver_token}"}

    def invoke(session: str, tool: str, **arguments) -> dict:
        r = httpx.post(f"{base}/v1/tools/{tool}/invoke", headers=agent, timeout=700,
                       json={"session_id": session, "arguments": arguments})
        return r.json()

    # Ordinary work that is allowed.
    invoke("sess-morning", "list_emails", folder="inbox", limit=5)
    invoke("sess-morning", "read_email", email_id="E001")
    invoke("sess-morning", "read_email", email_id="E002")
    invoke("sess-morning", "search_customers", query="Riyadh", limit=5)
    invoke("sess-morning", "get_customer", customer_id="C001")
    invoke("sess-morning", "list_documents")
    invoke("sess-morning", "send_email", to="sales.team@najd-trading.example", subject="Weekly summary",
           body="Hi team, the weekly CRM summary is ready in the shared folder.")
    invoke("sess-crm", "update_customer_note", customer_id="C002", note="Called back; prefers Arabic invoices.")
    # Requests the policy refuses.
    invoke("sess-bulk", "export_customers", query="", count=200)
    invoke("sess-bulk", "transfer_funds", to_iban="SA4420000001234567891234", amount_sar=250000, memo="Q4")
    invoke("sess-bulk", "fetch_url", url="http://169.254.169.254/latest/meta-data/")
    invoke("sess-bulk", "format_disk")

    # Approval requests: run in threads because the agent call waits for a human.
    def waiting(session: str, tool: str, **arguments) -> threading.Thread:
        t = threading.Thread(target=invoke, args=(session, tool), kwargs=arguments, daemon=True)
        t.start()
        return t

    waiting("sess-vendor", "send_email", to="quotes@gulf-supplies.example", subject="Re: quotation Q-881",
            body="Thank you for the quotation. Please confirm delivery dates for the 40 units.")
    waiting("sess-ops", "delete_customer", customer_id="C017")
    waiting("sess-vendor2", "send_email", to="accounts@red-sea-logistics.example", subject="Invoice INV-2231",
            body="Please find our remittance advice for invoice INV-2231.")
    waiting("sess-ops", "transfer_funds", to_iban="SA0380000000608010167519", amount_sar=4200, memo="Supplier payment")
    deadline = time.time() + 20
    pending: list = []
    while time.time() < deadline and len(pending) < 4:
        pending = httpx.get(f"{base}/api/approvals?status=pending", headers=approver).json()
        time.sleep(0.3)
    # Decide two (one approved, one denied) so history is populated; leave the rest pending.
    for record, approve in zip(pending[:2], (True, False), strict=False):
        httpx.post(f"{base}/api/approvals/{record['id']}/decision", headers=approver,
                   json={"approve": approve, "note": "Checked with the requester." if approve else "Not expected."})
    httpx.post(f"{base}/api/audit/verify", headers={"Authorization": f"Bearer {admin_token}"})


def login(page: Page, user: str, password: str) -> None:
    page.fill("input[name=username]", user)
    page.fill("input[name=password]", password)
    page.click("button[type=submit]")
    page.wait_for_timeout(1500)


def shot(page: Page, out: Path, name: str, *, full: bool = False) -> None:
    page.wait_for_timeout(900)
    page.screenshot(path=str(out / f"{name}.png"), full_page=full)
    print("  captured", name)


def capture(base: str, creds: dict[str, str], out: Path) -> None:
    with sync_playwright() as pw:
        browser = pw.chromium.launch(channel="chrome", headless=True)
        # ---------------------------------------------------------------- dashboard (desktop)
        ctx = browser.new_context(viewport={"width": 1440, "height": 900}, device_scale_factor=2,
                                  color_scheme="light")
        page = ctx.new_page()
        page.goto(f"{base}/")
        page.wait_for_selector("input[name=username]")
        shot(page, out, "dash-login")
        login(page, creds["admin_user"], creds["admin_password"])
        for route, name in (("/", "dash-overview"), ("/activity", "dash-activity"), ("/approvals", "dash-approvals"),
                            ("/policies", "dash-policies"), ("/agents", "dash-agents"), ("/users", "dash-users"),
                            ("/tools", "dash-tools"), ("/demo", "dash-demo"), ("/settings", "dash-settings")):
            page.goto(f"{base}/#{route}")
            shot(page, out, name)
        page.goto(f"{base}/#/activity")
        page.wait_for_timeout(1200)
        rows = page.locator("table tbody tr")
        if rows.count():
            target = rows.nth(min(2, rows.count() - 1))
            button = target.locator("button")
            (button.first if button.count() else target).click()
            shot(page, out, "dash-activity-detail")
        page.goto(f"{base}/#/playground")
        page.wait_for_timeout(800)
        page.fill("textarea", "شكراً لتعاونكم. نرفق لكم عرض السعر رقم Q-881 لتوريد 40 وحدة، "
                              "ونأمل تأكيد موعد التسليم قبل نهاية الشهر. Best regards, Gulf Supplies.")
        page.locator("button[type=submit]").first.click()
        page.wait_for_timeout(1500)
        shot(page, out, "dash-playground")
        # Arabic, right-to-left.
        page.evaluate("localStorage.setItem('mirsad.lang', 'ar')")
        for route, name in (("/", "dash-overview-ar"), ("/activity", "dash-activity-ar"),
                            ("/policies", "dash-policies-ar")):
            page.goto(f"{base}/#{route}")
            page.reload()
            shot(page, out, name)
        # Dark theme example.
        page.evaluate("localStorage.setItem('mirsad.lang', 'en'); localStorage.setItem('mirsad.theme', 'dark')")
        page.goto(f"{base}/#/")
        page.reload()
        shot(page, out, "dash-overview-dark")
        ctx.close()

        # ---------------------------------------------------------------- approver PWA (phone)
        for lang in ("en", "ar"):
            mctx = browser.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=3,
                                       is_mobile=True, has_touch=True, color_scheme="light")
            m = mctx.new_page()
            m.goto(f"{base}/approve")
            m.evaluate(f"localStorage.setItem('mirsad.lang', '{lang}')")
            m.reload()
            m.wait_for_selector("input[name=username]")
            if lang == "en":
                shot(m, out, "pwa-login")
            login(m, creds["approver_user"], creds["approver_password"])
            shot(m, out, f"pwa-pending-{lang}")
            cards = m.locator("button.a-card__button")
            if cards.count():
                cards.first.click()
                shot(m, out, f"pwa-detail-{lang}")
                shot(m, out, f"pwa-detail-full-{lang}", full=True)
                back = m.locator("button.a-back")
                if back.count():
                    back.first.click()
            tabs = m.locator("[role=tab]")
            if tabs.count() > 1:
                tabs.nth(1).click()
                shot(m, out, f"pwa-history-{lang}")
            mctx.close()
        browser.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default=str(ROOT / "docs" / "figures" / "screens"))
    args = parser.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="mirsad-shots-") as tmp:
        port = free_port()
        env = dict(os.environ, MIRSAD_DATA_DIR=tmp, MIRSAD_ENABLE_DEMO="true", MIRSAD_APPROVAL_TIMEOUT_S="900",
                   MIRSAD_PORT=str(port))
        subprocess.run([sys.executable, "-m", "mirsad.cli", "init", "--demo"], env=env, check=True,  # noqa: S603
                       cwd=ROOT, capture_output=True)
        creds = read_credentials(Path(tmp) / "credentials.txt")
        server = subprocess.Popen([sys.executable, "-m", "mirsad.cli", "serve", "--port", str(port), "--demo"],  # noqa: S603
                                  env=env, cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        base = f"http://127.0.0.1:{port}"
        try:
            for _ in range(100):
                try:
                    if httpx.get(f"{base}/healthz", timeout=1).status_code == 200:
                        break
                except httpx.HTTPError:
                    time.sleep(0.2)
            seed_activity(base, creds)
            capture(base, creds, out)
        finally:
            server.terminate()
            try:
                server.wait(timeout=10)
            except subprocess.TimeoutExpired:
                server.kill()  # pending approval calls keep the graceful shutdown waiting
                server.wait(timeout=10)


if __name__ == "__main__":
    main()
