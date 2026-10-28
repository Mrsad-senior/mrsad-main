"""Adapters that put the Mirsad gateway in front of real agents and tools.

* :mod:`mirsad.adapters.upstreams` - connections to the tools being protected
  (MCP servers over in-process / stdio / streamable HTTP, plain Python functions).
* :mod:`mirsad.adapters.mcp_proxy` - an MCP server that agents connect to instead
  of the real servers (stdio and streamable HTTP).
* :mod:`mirsad.adapters.openai_proxy` - an OpenAI-compatible ``/v1/chat/completions``
  endpoint that inspects tool messages and checks tool calls.
* :mod:`mirsad.adapters.messages` - bilingual (EN/AR) explanations of blocks.

Submodules are imported explicitly by callers; this package deliberately imports
nothing heavy so that :mod:`mirsad.sdk` can reuse the small helper modules.
"""
