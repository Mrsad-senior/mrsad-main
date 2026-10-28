"""MCP server exposing the Najd Trading Co. demo workspace tools.

Wraps a module-level :data:`WORLD` (a :class:`demo.world.World`) and exposes all
twelve workspace tools over MCP. The demo endpoints and the in-process upstream
share this same ``WORLD`` object, so a reset or a planted payload is visible to
both. Runnable as a stdio server with ``python -m demo.workspace_server``.

The installed MCP SDK is v2.x: ``FastMCP`` was renamed to
``mcp.server.mcpserver.MCPServer``. Each tool returns JSON **text** (the tool
functions are typed ``-> str`` so the server publishes unstructured text
content); callers ``json.loads`` the single text block.
"""

from __future__ import annotations

import logging

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError

from demo.world import TOOLS, ToolArgumentError, World, call_tool, to_text

logger = logging.getLogger("mirsad.demo")

WORLD = World()

server: MCPServer = MCPServer(
    name="najd-workspace",
    instructions="Najd Trading Co. simulated email & CRM workspace (demo, all data fictional).",
)


def _run(name: str, arguments: dict) -> str:
    """Dispatch to the shared world and render the result as JSON text.

    Invalid arguments become an MCP ``ToolError`` so the clear reason reaches the
    caller as an error result instead of a generic "unexpected exception".
    """
    try:
        return to_text(call_tool(WORLD, name, arguments))
    except ToolArgumentError as exc:
        raise ToolError(str(exc)) from exc


# Each wrapper has an explicit signature so the MCP server derives a correct
# input schema and description; the body just forwards to the shared world.


def list_emails(folder: str = "inbox", limit: int = 10) -> str:
    """List emails in a mailbox folder (inbox, sent or archive)."""
    return _run("list_emails", {"folder": folder, "limit": limit})


def read_email(email_id: str) -> str:
    """Read the full content of a single email by its id (e.g. E001)."""
    return _run("read_email", {"email_id": email_id})


def send_email(to: str, subject: str, body: str, cc: str | None = None) -> str:
    """Send an email on behalf of Najd Trading Co."""
    return _run("send_email", {"to": to, "subject": subject, "body": body, "cc": cc})


def search_customers(query: str, limit: int = 10) -> str:
    """Search the CRM for customers matching a query (name, email, city or id)."""
    return _run("search_customers", {"query": query, "limit": limit})


def get_customer(customer_id: str) -> str:
    """Fetch the full CRM record of one customer by id (e.g. C001)."""
    return _run("get_customer", {"customer_id": customer_id})


def export_customers(query: str = "", count: int = 10) -> str:
    """Export customer records matching a query as CSV text."""
    return _run("export_customers", {"query": query, "count": count})


def update_customer_note(customer_id: str, note: str) -> str:
    """Replace the free-text note on a customer's CRM record."""
    return _run("update_customer_note", {"customer_id": customer_id, "note": note})


def delete_customer(customer_id: str) -> str:
    """Permanently delete a customer record from the CRM by id."""
    return _run("delete_customer", {"customer_id": customer_id})


def fetch_url(url: str) -> str:
    """Fetch the text content of a web page by URL (intranet or public)."""
    return _run("fetch_url", {"url": url})


def list_documents() -> str:
    """List documents in the shared drive (id, title, owner, source)."""
    return _run("list_documents", {})


def read_document(doc_id: str) -> str:
    """Read the full content of a document by its id (e.g. D001)."""
    return _run("read_document", {"doc_id": doc_id})


def transfer_funds(to_iban: str, amount_sar: float, memo: str = "") -> str:
    """Transfer funds from the company account to a destination IBAN (in SAR)."""
    return _run("transfer_funds", {"to_iban": to_iban, "amount_sar": amount_sar, "memo": memo})


_WRAPPERS = {
    "list_emails": list_emails,
    "read_email": read_email,
    "send_email": send_email,
    "search_customers": search_customers,
    "get_customer": get_customer,
    "export_customers": export_customers,
    "update_customer_note": update_customer_note,
    "delete_customer": delete_customer,
    "fetch_url": fetch_url,
    "list_documents": list_documents,
    "read_document": read_document,
    "transfer_funds": transfer_funds,
}

for _name, _fn in _WRAPPERS.items():
    server.add_tool(
        _fn,
        name=_name,
        description=TOOLS[_name].description,
        structured_output=False,
    )


def main() -> None:
    """Run the workspace as a stdio MCP server."""
    logging.basicConfig(level=logging.INFO)
    server.run("stdio")


if __name__ == "__main__":
    main()
