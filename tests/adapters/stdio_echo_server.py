"""Stand-alone MCP server run as a subprocess by the stdio-transport tests."""

import os

from mcp.server.mcpserver import MCPServer

server = MCPServer("stdio-echo", log_level="WARNING")


@server.tool()
def echo(text: str) -> str:
    """Echo the text back."""
    return f"echo: {text}"


@server.tool()
def whoami() -> dict:
    """Process information."""
    return {"pid": os.getpid(), "marker": os.environ.get("ECHO_MARKER", "")}


@server.tool()
def crash() -> str:
    """Kill the server process abruptly (simulates an upstream crash)."""
    os._exit(3)


if __name__ == "__main__":
    server.run()
