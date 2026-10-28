"""Upstream tool sources protected by Mirsad.

An :class:`UpstreamManager` aggregates the tools of several MCP servers
(in-process, stdio subprocess, streamable HTTP) and plain Python functions behind
one ``list_tools`` / ``call`` interface. ``call`` is an executor compatible with
:meth:`mirsad.gateway.Gateway.execute`: it never raises for upstream failures,
it returns a :class:`~mirsad.models.ToolResult` with ``is_error=True`` instead, so
errors still flow through inspection and audit.

Each MCP connection runs in its own background task that owns the ``mcp.Client``
context (anyio cancel scopes must be entered and exited by the same task), so
connections can be (re)opened lazily from any request task and closed from
``stop()`` safely.
"""

from __future__ import annotations

import asyncio
import contextlib
import importlib
import inspect
import json
import logging
import os
import re
import sys
import time
from collections.abc import AsyncIterator, Callable, Sequence
from contextlib import asynccontextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal, TextIO

import anyio
import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator

from mirsad.adapters.serialization import parse_json_text, to_json_text
from mirsad.models import ToolCall, ToolResult

logger = logging.getLogger("mirsad.adapters")

__all__ = [
    "UpstreamConfig",
    "UpstreamError",
    "UpstreamManager",
    "UpstreamTool",
    "UpstreamsFile",
    "call_result_to_tool_result",
    "load_object",
    "value_to_tool_result",
]

PYTHON_UPSTREAM = "python"
_ENV_RE = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}")
_MAX_LIST_PAGES = 100
# Reconnect backoff after a failed connect: a dead upstream must not stall every
# tool refresh (and therefore every call) for its full connect timeout.
_BACKOFF_INITIAL_S = 2.0
_BACKOFF_MAX_S = 60.0
# After an unknown-tool miss we re-list at most this often, so a misbehaving
# agent cannot turn every call into an upstream round-trip.
_MISS_REFRESH_INTERVAL_S = 2.0


class UpstreamError(Exception):
    """Invalid upstream configuration or an upstream that cannot be reached."""


# --------------------------------------------------------------------------- configuration


class UpstreamConfig(BaseModel):
    """One entry of ``configs/upstreams.yaml``."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_.\-]+$")
    transport: Literal["inprocess", "stdio", "http"]
    description: str = ""
    target: str | None = None  # inprocess: "package.module:attribute"
    command: list[str] | None = None  # stdio: argv; "python" means the running interpreter
    env: dict[str, str] | None = None  # stdio: extra environment variables
    cwd: str | None = None  # stdio: working directory
    url: str | None = None  # http: streamable-HTTP endpoint, e.g. http://127.0.0.1:9000/mcp
    headers: dict[str, str] = Field(default_factory=dict)  # http: extra headers (auth tokens via ${ENV})
    tool_prefix: str = ""  # exposed tool name = prefix + upstream tool name
    connect_timeout_s: float = Field(default=20.0, gt=0, le=600)
    call_timeout_s: float = Field(default=60.0, gt=0, le=3600)
    enabled: bool = True

    @field_validator("tool_prefix")
    @classmethod
    def _prefix_chars(cls, v: str) -> str:
        if v and not re.fullmatch(r"[A-Za-z0-9_.\-]+", v):
            raise ValueError("tool_prefix may only contain letters, digits, '_', '.', '-'")
        return v

    @model_validator(mode="after")
    def _transport_fields(self) -> UpstreamConfig:
        if self.transport == "inprocess":
            if not self.target or ":" not in self.target:
                raise ValueError("transport 'inprocess' needs target: 'package.module:attribute'")
        elif self.transport == "stdio":
            if not self.command:
                raise ValueError("transport 'stdio' needs a non-empty command list")
        elif self.transport == "http":
            if not self.url or not re.match(r"^https?://", self.url):
                raise ValueError("transport 'http' needs url: http(s)://host:port/path")
        return self


class UpstreamsFile(BaseModel):
    """Top level of ``configs/upstreams.yaml``."""

    model_config = ConfigDict(extra="forbid")

    upstreams: list[UpstreamConfig] = Field(default_factory=list)

    @model_validator(mode="after")
    def _unique_names(self) -> UpstreamsFile:
        seen: set[str] = set()
        for up in self.upstreams:
            if up.name in seen or up.name == PYTHON_UPSTREAM:
                raise ValueError(f"duplicate or reserved upstream name: {up.name!r}")
            seen.add(up.name)
        return self


def _expand_env(value: Any) -> Any:
    """Replace ``${NAME}`` with environment values (missing variables become empty strings)."""
    if isinstance(value, str):

        def sub(m: re.Match[str]) -> str:
            name = m.group(1)
            if name not in os.environ:
                logger.warning("upstream config references unset environment variable %s", name)
            return os.environ.get(name, "")

        return _ENV_RE.sub(sub, value)
    if isinstance(value, list):
        return [_expand_env(v) for v in value]
    if isinstance(value, dict):
        return {k: _expand_env(v) for k, v in value.items()}
    return value


class UpstreamTool(BaseModel):
    """A tool offered by an upstream, as exposed to agents (name includes any prefix)."""

    name: str
    description: str = ""
    input_schema: dict[str, Any] = Field(default_factory=lambda: {"type": "object", "properties": {}})
    upstream: str
    title: str | None = None
    output_schema: dict[str, Any] | None = None


# --------------------------------------------------------------------------- result conversion


def _block_text(block: Any) -> str | None:
    """Text form of one MCP content block; non-text media become short placeholders."""
    kind = getattr(block, "type", None)
    if kind == "text":
        return block.text
    if kind == "resource":
        res = block.resource
        text = getattr(res, "text", None)
        if text is not None:
            return text
        return f"[binary resource {res.uri} ({getattr(res, 'mime_type', None) or 'unknown type'}) omitted]"
    if kind == "resource_link":
        return f"[resource link: {getattr(block, 'name', '')} <{block.uri}>]"
    if kind in ("image", "audio"):
        # Mirsad cannot inspect media, so it does not forward it to the model.
        return f"[{kind} ({getattr(block, 'mime_type', 'unknown type')}) omitted by Mirsad]"
    return None


def call_result_to_tool_result(call: ToolCall, result: Any) -> ToolResult:
    """Convert an MCP ``CallToolResult`` to a :class:`ToolResult`.

    ``content`` = text blocks (and embedded text resources) joined by newlines;
    ``structured`` = ``structuredContent`` when present, else the JSON-parsed text.
    A structured-only result gets its JSON dump as text so ``content`` is never empty
    while data exists.
    """
    parts = [t for t in (_block_text(b) for b in (getattr(result, "content", None) or [])) if t is not None]
    text = "\n".join(parts)
    structured = getattr(result, "structured_content", None)
    if structured is None:
        structured = parse_json_text(text)
    elif not text:
        text = json.dumps(structured, ensure_ascii=False)
    return ToolResult(
        call_id=call.call_id,
        session_id=call.session_id,
        agent_id=call.agent_id,
        tool=call.tool,
        content=text,
        structured=structured,
        is_error=bool(getattr(result, "is_error", False)),
    )


def value_to_tool_result(call: ToolCall, value: Any, *, is_error: bool = False) -> ToolResult:
    """Convert a Python return value (str, dict, list, model, ...) to a :class:`ToolResult`."""
    if isinstance(value, ToolResult):
        return value.model_copy(
            update={"call_id": call.call_id, "session_id": call.session_id, "agent_id": call.agent_id}
        )
    if type(value).__name__ == "CallToolResult" and hasattr(value, "content"):
        return call_result_to_tool_result(call, value)
    text, structured = to_json_text(value)
    return ToolResult(
        call_id=call.call_id,
        session_id=call.session_id,
        agent_id=call.agent_id,
        tool=call.tool,
        content=text,
        structured=structured,
        is_error=is_error,
    )


def _internal_error_text(tool: str) -> str:
    return (f"Tool '{tool}' failed because of an internal error; the details were recorded in the gateway log. | "
            f"تعذّر تنفيذ الأداة '{tool}' بسبب خطأ داخلي، وسُجّلت التفاصيل في سجل البوابة.")

def _error_result(call: ToolCall, message: str) -> ToolResult:
    return ToolResult(
        call_id=call.call_id,
        session_id=call.session_id,
        agent_id=call.agent_id,
        tool=call.tool,
        content=message,
        is_error=True,
    )


def load_object(target: str) -> Any:
    """Import ``package.module:attr[.attr]``; a callable that is not a server is called to build one."""
    module_name, _, attr_path = target.partition(":")
    if not module_name or not attr_path:
        raise UpstreamError(f"invalid import target {target!r}; expected 'package.module:attribute'")
    try:
        obj: Any = importlib.import_module(module_name)
    except ImportError as exc:
        raise UpstreamError(f"cannot import module {module_name!r}: {exc}") from exc
    for part in attr_path.split("."):
        try:
            obj = getattr(obj, part)
        except AttributeError as exc:
            raise UpstreamError(f"{module_name!r} has no attribute {attr_path!r}") from exc
    from mcp.server import Server
    from mcp.server.mcpserver import MCPServer

    if not isinstance(obj, (Server, MCPServer)) and callable(obj):
        obj = obj()
    if not isinstance(obj, (Server, MCPServer)):
        raise UpstreamError(f"{target!r} is not an MCP server (got {type(obj).__name__})")
    return obj


# --------------------------------------------------------------------------- MCP connections


def _root_cause(exc: BaseException) -> BaseException:
    """First leaf of nested exception groups (anyio wraps transport errors in task-group groups)."""
    while isinstance(exc, BaseExceptionGroup) and exc.exceptions:
        exc = exc.exceptions[0]
    return exc


def _python_command(argv: list[str]) -> list[str]:
    # Configs say "python"; inside a virtualenv that must mean *this* interpreter.
    if argv and argv[0] in ("python", "python3"):
        return [sys.executable, *argv[1:]]
    return argv


@asynccontextmanager
async def _http_transport(url: str, headers: dict[str, str], timeout_s: float) -> AsyncIterator[Any]:
    """Streamable-HTTP transport with custom headers (``mcp.Client(url)`` cannot set headers)."""
    import httpx2
    from mcp.client.streamable_http import streamable_http_client

    timeout = httpx2.Timeout(timeout_s, read=max(300.0, timeout_s))
    async with httpx2.AsyncClient(headers=headers or None, timeout=timeout) as http:
        async with streamable_http_client(url, http_client=http) as streams:
            yield streams


class _MCPConnection:
    """One lazily (re)connected MCP client, owned by a dedicated background task."""

    def __init__(self, config: UpstreamConfig, errlog: TextIO | None = None) -> None:
        self.config = config
        self._errlog = errlog
        self._client: Any = None
        self._task: asyncio.Task[None] | None = None
        self._stop: asyncio.Event | None = None
        self._lock: asyncio.Lock | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._retry_at = 0.0
        self._backoff_s = _BACKOFF_INITIAL_S
        self.last_error: str | None = None
        self.connected_at: float | None = None
        self.connect_count = 0

    @property
    def connected(self) -> bool:
        return self._client is not None and self._task is not None and not self._task.done()

    def _check_loop(self) -> None:
        """Drop state that belongs to another (possibly closed) event loop."""
        loop = asyncio.get_running_loop()
        if self._loop is loop:
            return
        if self._loop is not None and self._task is not None:
            logger.info("upstream %s: event loop changed; reconnecting", self.config.name)
        self._loop = loop
        self._lock = None
        self._client = self._task = self._stop = None

    def _get_lock(self) -> asyncio.Lock:
        if self._lock is None:
            self._lock = asyncio.Lock()
        return self._lock

    def _make_client(self) -> Any:
        from mcp import Client, StdioServerParameters
        from mcp.client.stdio import stdio_client

        cfg = self.config
        if cfg.transport == "inprocess":
            server = load_object(cfg.target or "")
            return Client(server, cache=None)
        if cfg.transport == "stdio":
            argv = _python_command(list(cfg.command or []))
            params = StdioServerParameters(command=argv[0], args=argv[1:], env=cfg.env, cwd=cfg.cwd)
            return Client(stdio_client(params, errlog=self._errlog or sys.stderr), cache=None)
        return Client(_http_transport(cfg.url or "", cfg.headers, cfg.connect_timeout_s), cache=None)

    async def ensure_connected(self) -> Any:
        self._check_loop()
        if self.connected:
            return self._client
        async with self._get_lock():
            if self.connected:
                return self._client
            await self._close_locked()
            wait = self._retry_at - time.monotonic()
            if wait > 0:
                raise UpstreamError(
                    f"upstream {self.config.name!r} unavailable ({self.last_error}); next retry in {wait:.0f}s"
                )
            try:
                return await self._open_locked()
            except Exception:
                self._retry_at = time.monotonic() + self._backoff_s
                self._backoff_s = min(self._backoff_s * 2, _BACKOFF_MAX_S)
                raise

    async def _open_locked(self) -> Any:
        ready = asyncio.Event()
        stop = asyncio.Event()
        box: dict[str, Any] = {}
        client = self._make_client()  # config/import errors surface here, synchronously

        async def runner() -> None:
            try:
                async with client:
                    box["client"] = client
                    ready.set()
                    await stop.wait()
            except Exception as exc:  # recorded; surfaced to callers through last_error
                box["error"] = _root_cause(exc)
                logger.warning("upstream %s connection ended: %r", self.config.name, box["error"])
            finally:
                ready.set()

        task = asyncio.create_task(runner(), name=f"mirsad-upstream-{self.config.name}")
        try:
            await asyncio.wait_for(ready.wait(), timeout=self.config.connect_timeout_s)
        except TimeoutError:
            stop.set()
            task.cancel()
            with contextlib.suppress(BaseException):
                await task
            self.last_error = f"connect timed out after {self.config.connect_timeout_s:g}s"
            raise UpstreamError(f"upstream {self.config.name!r}: {self.last_error}") from None
        if "client" not in box or task.done():
            err = box.get("error")
            self.last_error = f"{type(err).__name__}: {err}" if err else "connection closed during startup"
            raise UpstreamError(f"upstream {self.config.name!r} unavailable: {self.last_error}") from err
        self._client, self._task, self._stop = box["client"], task, stop
        self.connected_at = time.time()
        self.connect_count += 1
        self.last_error = None
        self._retry_at, self._backoff_s = 0.0, _BACKOFF_INITIAL_S
        logger.info("upstream %s connected (%s)", self.config.name, self.config.transport)
        return self._client

    def mark_broken(self, reason: str) -> None:
        """Ask the runner to close; the next call reconnects."""
        self.last_error = reason
        if self._stop is not None:
            self._stop.set()
        self._client = None

    async def close(self) -> None:
        self._check_loop()
        async with self._get_lock():
            await self._close_locked()

    async def _close_locked(self) -> None:
        task, stop = self._task, self._stop
        self._client = self._task = self._stop = None
        if task is None:
            return
        if stop is not None:
            stop.set()
        done, _ = await asyncio.wait({task}, timeout=10.0)
        if not done:
            task.cancel()
            with contextlib.suppress(BaseException):
                await task

    async def list_tools(self) -> list[Any]:
        client = await self.ensure_connected()
        tools: list[Any] = []
        cursor: str | None = None
        with anyio.fail_after(self.config.call_timeout_s):
            for _ in range(_MAX_LIST_PAGES):
                page = await client.list_tools(cursor=cursor)
                tools.extend(page.tools)
                cursor = page.next_cursor
                if not cursor:
                    break
        return tools


@dataclass
class _PythonTool:
    name: str
    fn: Callable[..., Any]
    description: str
    input_schema: dict[str, Any]
    in_thread: bool
    timeout_s: float


_TRANSPORT_ERRORS: tuple[type[BaseException], ...] = (
    anyio.ClosedResourceError,
    anyio.BrokenResourceError,
    anyio.EndOfStream,
    ConnectionError,
    OSError,
)


def _is_connection_failure(exc: BaseException) -> bool:
    """An ``MCPError`` that means the session is gone (closed transport / request timeout)."""
    from mcp_types import CONNECTION_CLOSED, REQUEST_TIMEOUT

    return getattr(exc, "code", None) in (CONNECTION_CLOSED, REQUEST_TIMEOUT)


# --------------------------------------------------------------------------- manager


class UpstreamManager:
    """Aggregates upstream MCP servers and Python function tools behind one interface."""

    def __init__(
        self,
        upstreams: Sequence[UpstreamConfig] | None = None,
        *,
        tools_ttl_s: float = 300.0,
        errlog: TextIO | None = None,
    ) -> None:
        self._configs = [c for c in (upstreams or []) if c.enabled]
        self._connections = {c.name: _MCPConnection(c, errlog) for c in self._configs}
        self._python_tools: dict[str, _PythonTool] = {}
        self._upstream_tools: dict[str, list[UpstreamTool]] = {}
        self._tools: list[UpstreamTool] = []
        self._routes: dict[str, tuple[str, str]] = {}  # exposed name -> (upstream, upstream tool name)
        self._tools_ttl_s = tools_ttl_s
        self._fetched_at: float | None = None
        self._last_miss_refresh = 0.0
        self._refresh_lock: asyncio.Lock | None = None
        self._lock_loop: asyncio.AbstractEventLoop | None = None
        self._dirty = True

    # ---------------------------------------------------------------- construction

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None, **kwargs: Any) -> UpstreamManager:
        try:
            parsed = UpstreamsFile.model_validate(_expand_env(data or {}))
        except ValidationError as exc:
            raise UpstreamError(f"invalid upstreams configuration: {exc}") from exc
        return cls(parsed.upstreams, **kwargs)

    @classmethod
    def from_yaml(cls, text: str, **kwargs: Any) -> UpstreamManager:
        try:
            data = yaml.safe_load(text) or {}
        except yaml.YAMLError as exc:
            raise UpstreamError(f"upstreams YAML is not valid: {exc}") from exc
        if not isinstance(data, dict):
            raise UpstreamError("upstreams YAML must be a mapping with an 'upstreams' list")
        return cls.from_dict(data, **kwargs)

    @classmethod
    def from_file(cls, path: str | Path, **kwargs: Any) -> UpstreamManager:
        """Load ``configs/upstreams.yaml``; a missing file yields an empty manager (logged)."""
        p = Path(path)
        if not p.exists():
            logger.warning("upstreams file %s not found; starting with no upstream servers", p)
            return cls([], **kwargs)
        return cls.from_yaml(p.read_text(encoding="utf-8"), **kwargs)

    # ---------------------------------------------------------------- lifecycle

    async def start(self) -> None:
        """Connect to every upstream (failures are logged, not raised) and load the tool list."""

        async def connect(conn: _MCPConnection) -> None:
            try:
                await conn.ensure_connected()
            except Exception as exc:
                conn.last_error = conn.last_error or str(exc)
                logger.error("upstream %s failed to start: %s", conn.config.name, exc)

        await asyncio.gather(*(connect(c) for c in self._connections.values()))
        await self.refresh_tools()

    async def stop(self) -> None:
        await asyncio.gather(*(c.close() for c in self._connections.values()), return_exceptions=True)

    async def __aenter__(self) -> UpstreamManager:
        await self.start()
        return self

    async def __aexit__(self, *exc: object) -> None:
        await self.stop()

    # ---------------------------------------------------------------- python tools

    def register_python(
        self,
        name: str,
        fn: Callable[..., Any],
        description: str,
        input_schema: dict[str, Any],
        *,
        in_thread: bool = False,
        timeout_s: float = 60.0,
    ) -> None:
        """Expose a plain (sync or async) function as a tool; it is called as ``fn(**arguments)``.

        Sync functions run inline unless ``in_thread`` is set (use it for blocking I/O).
        Python tools take precedence over MCP tools with the same name.
        """
        if not callable(fn):
            raise TypeError("fn must be callable")
        if not name or not re.fullmatch(r"[A-Za-z0-9_.\-]{1,128}", name):
            raise ValueError(f"invalid tool name {name!r}")
        schema = dict(input_schema or {})
        schema.setdefault("type", "object")
        schema.setdefault("properties", {})
        self._python_tools[name] = _PythonTool(name, fn, description or "", schema, in_thread, timeout_s)
        self._dirty = True

    # ---------------------------------------------------------------- tool listing

    def _get_refresh_lock(self) -> asyncio.Lock:
        loop = asyncio.get_running_loop()
        if self._refresh_lock is None or self._lock_loop is not loop:
            self._refresh_lock, self._lock_loop = asyncio.Lock(), loop
        return self._refresh_lock

    def _stale(self) -> bool:
        return (
            self._dirty
            or self._fetched_at is None
            or (time.monotonic() - self._fetched_at) > self._tools_ttl_s
        )

    async def list_tools(self, *, refresh: bool = False) -> list[UpstreamTool]:
        """All tools (cached for ``tools_ttl_s``); ``refresh=True`` forces a re-list."""
        if refresh or self._stale():
            await self.refresh_tools()
        return list(self._tools)

    async def refresh_tools(self) -> list[UpstreamTool]:
        """Re-list every upstream. An unreachable upstream keeps its last known tools."""
        async with self._get_refresh_lock():

            async def fetch(conn: _MCPConnection) -> None:
                name = conn.config.name
                try:
                    raw = await conn.list_tools()
                except Exception as exc:
                    conn.last_error = f"list_tools failed: {exc}"
                    logger.warning("upstream %s: tool listing failed: %s", name, exc)
                    if isinstance(exc, (*_TRANSPORT_ERRORS, TimeoutError)) or _is_connection_failure(exc):
                        conn.mark_broken(conn.last_error)
                    return
                prefix = conn.config.tool_prefix
                self._upstream_tools[name] = [
                    UpstreamTool(
                        name=f"{prefix}{t.name}",
                        description=t.description or "",
                        input_schema=dict(t.input_schema or {"type": "object", "properties": {}}),
                        upstream=name,
                        title=getattr(t, "title", None),
                        output_schema=getattr(t, "output_schema", None),
                    )
                    for t in raw
                ]

            await asyncio.gather(*(fetch(c) for c in self._connections.values()))
            self._rebuild_index()
            self._fetched_at = time.monotonic()
            self._dirty = False
            return list(self._tools)

    def _rebuild_index(self) -> None:
        tools: list[UpstreamTool] = []
        routes: dict[str, tuple[str, str]] = {}
        for pt in self._python_tools.values():
            tools.append(
                UpstreamTool(
                    name=pt.name,
                    description=pt.description,
                    input_schema=pt.input_schema,
                    upstream=PYTHON_UPSTREAM,
                )
            )
            routes[pt.name] = (PYTHON_UPSTREAM, pt.name)
        for cfg in self._configs:
            for tool in self._upstream_tools.get(cfg.name, []):
                if tool.name in routes:
                    logger.warning(
                        "tool %r from upstream %s hidden: name already provided by %s",
                        tool.name,
                        cfg.name,
                        routes[tool.name][0],
                    )
                    continue
                tools.append(tool)
                routes[tool.name] = (cfg.name, tool.name[len(cfg.tool_prefix) :])
        self._tools, self._routes = tools, routes

    async def get_tool(self, name: str) -> UpstreamTool | None:
        for tool in await self.list_tools():
            if tool.name == name:
                return tool
        return None

    # ---------------------------------------------------------------- calls

    async def _route(self, tool: str) -> tuple[str, str] | None:
        if self._stale():
            await self.refresh_tools()
        route = self._routes.get(tool)
        if route is None and time.monotonic() - self._last_miss_refresh > _MISS_REFRESH_INTERVAL_S:
            self._last_miss_refresh = time.monotonic()
            await self.refresh_tools()
            route = self._routes.get(tool)
        return route

    async def call(self, call: ToolCall) -> ToolResult:
        """Run ``call`` on the upstream that provides ``call.tool`` (errors become ``is_error`` results)."""
        route = await self._route(call.tool)
        if route is None:
            return _error_result(call, f"Unknown tool: {call.tool}")
        upstream, tool_name = route
        if upstream == PYTHON_UPSTREAM:
            return await self._call_python(self._python_tools[tool_name], call)
        return await self._call_mcp(self._connections[upstream], tool_name, call)

    async def _call_python(self, tool: _PythonTool, call: ToolCall) -> ToolResult:
        args = dict(call.arguments or {})
        try:
            with anyio.fail_after(tool.timeout_s):
                if inspect.iscoroutinefunction(tool.fn):
                    value = await tool.fn(**args)
                elif tool.in_thread:
                    value = await anyio.to_thread.run_sync(lambda: tool.fn(**args))
                else:
                    value = tool.fn(**args)
                if inspect.isawaitable(value):
                    value = await value
        except TimeoutError:
            return _error_result(call, f"Tool {call.tool} timed out after {tool.timeout_s:g}s")
        except (ValueError, TypeError) as exc:
            # Argument validation errors are meant for the caller so it can correct the call.
            logger.info("python tool %s rejected its arguments: %s", call.tool, type(exc).__name__)
            return _error_result(call, f"Tool {call.tool} rejected the arguments: {exc}")
        except Exception:
            # Anything else may carry internal details (paths, hosts, stack data): log it, return a safe message.
            logger.warning("python tool %s failed", call.tool, exc_info=True)
            return _error_result(call, _internal_error_text(call.tool))
        try:
            return value_to_tool_result(call, value)
        except Exception:
            logger.warning("python tool %s returned an unserialisable value", call.tool, exc_info=True)
            return _error_result(call, f"Tool {call.tool} returned a value that cannot be serialised.")

    async def _call_mcp(self, conn: _MCPConnection, tool_name: str, call: ToolCall) -> ToolResult:
        from mcp import MCPError

        name = conn.config.name
        try:
            client = await conn.ensure_connected()
        except Exception:
            logger.warning("upstream %s unavailable", name, exc_info=True)
            return _error_result(call, f"Upstream '{name}' is unavailable.")
        timeout = conn.config.call_timeout_s
        try:
            with anyio.fail_after(timeout):
                result = await client.call_tool(tool_name, dict(call.arguments or {}))
        except TimeoutError:
            # We cannot tell a slow tool from a hung transport; reconnect on the next call.
            conn.mark_broken(f"call to {tool_name} timed out")
            return _error_result(call, f"Upstream '{name}' timed out after {timeout:g}s running {call.tool}")
        except MCPError as exc:
            if _is_connection_failure(exc):
                conn.mark_broken(f"MCPError {exc.code}: {exc}")
                return _error_result(call, f"Upstream '{name}' connection failed during {call.tool}.")
            return _error_result(call, f"Upstream '{name}' rejected {call.tool}: {exc}")
        except _TRANSPORT_ERRORS as exc:
            # The call is NOT retried: it may already have had side effects upstream.
            conn.mark_broken(f"{type(exc).__name__}: {exc}")
            logger.warning("upstream %s transport error during %s: %r", name, call.tool, exc)
            return _error_result(call, f"Upstream '{name}' connection failed during {call.tool}.")
        except Exception as exc:
            logger.warning("upstream %s: call %s failed: %r", name, call.tool, exc)
            return _error_result(call, _internal_error_text(call.tool))
        return call_result_to_tool_result(call, result)

    # ---------------------------------------------------------------- introspection

    def status(self) -> list[dict[str, Any]]:
        """Connection status per upstream (for dashboards and health checks)."""
        out: list[dict[str, Any]] = []
        if self._python_tools:
            out.append(
                {
                    "name": PYTHON_UPSTREAM,
                    "transport": "python",
                    "connected": True,
                    "tools": sorted(self._python_tools),
                    "last_error": None,
                }
            )
        for cfg in self._configs:
            conn = self._connections[cfg.name]
            out.append(
                {
                    "name": cfg.name,
                    "transport": cfg.transport,
                    "connected": conn.connected,
                    "tools": [t.name for t in self._upstream_tools.get(cfg.name, [])],
                    "last_error": conn.last_error,
                    "connect_count": conn.connect_count,
                    "next_retry_s": round(max(0.0, conn._retry_at - time.monotonic()), 1),
                }
            )
        return out
