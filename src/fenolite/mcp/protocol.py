# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The Model Context Protocol on standard input and output (capability mcp-server, "MCP server on standard
input and output"; the facts and their sources are in ``docs/mcp.md``).

One JSON-RPC 2.0 message per line in, one per line out; nothing else is written to the output. The server is
dual-era:

* a request whose ``params._meta`` names ``io.modelcontextprotocol/protocolVersion`` is served statelessly by
  revision ``2026-07-28``, the only version such a request may name (else error ``-32022``);
* ``initialize`` selects a legacy revision (``2025-11-25``, ``2025-06-18`` or ``2025-03-26``) for the rest of
  the process, as the handshake revisions define it.

The protocol knows no Fenolite command: a :class:`Backend` lists and calls the tools and reads the resources.
Tool calls run one at a time on a worker thread, in order of arrival, so that the reader still answers
``ping`` and ``notifications/cancelled`` while a call runs; a cancelled call gets no response.
"""

from __future__ import annotations

import json
import queue
import sys
import threading
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, BinaryIO, Protocol, TextIO, cast

MODERN = "2026-07-28"
LEGACY = ("2025-11-25", "2025-06-18", "2025-03-26")
"""The handshake revisions served, newest first; an ``initialize`` of another version gets the first."""
BATCHING = "2025-03-26"
"""The only served revision whose messages may come as a JSON array (``docs/mcp.md``, version table)."""

PARSE_ERROR = -32700
INVALID_REQUEST = -32600
METHOD_NOT_FOUND = -32601
INVALID_PARAMS = -32602
INTERNAL_ERROR = -32603
UNSUPPORTED_VERSION = -32022
LEGACY_NOT_FOUND = -32002
"""The resource-not-found code of the handshake revisions; ``2026-07-28`` uses ``INVALID_PARAMS``."""

VERSION_KEY = "io.modelcontextprotocol/protocolVersion"
CAPABILITIES_KEY = "io.modelcontextprotocol/clientCapabilities"
SERVER_INFO_KEY = "io.modelcontextprotocol/serverInfo"
CACHE = {"ttlMs": 0, "cacheScope": "private"}
"""The cache fields of a ``2026-07-28`` list or read: never fresh (the list follows the installed version and
the server's options), and never shared (a page may name a local path)."""

Json = dict[str, Any]


class Backend(Protocol):
    """What the protocol serves: tools in their newest shape, and text resources."""

    def tools(self) -> list[Json]:
        """Every tool, in a deterministic order, as ``tools/list`` of ``2026-07-28`` lists it."""
        ...

    def call(self, name: str, arguments: Json, call: Call) -> Json:
        """The result of ``name`` (``content``, ``structuredContent``, ``isError``, ``_meta``); raises
        :class:`UnknownTool` for a name :meth:`tools` does not list."""
        ...

    def resources(self) -> list[Json]:
        """Every resource (``uri``, ``name``, ``title``, ``description``, ``mimeType``)."""
        ...

    def read(self, uri: str) -> list[Json] | None:
        """The contents of ``uri`` (``uri``, ``mimeType``, ``text``), or ``None`` when there is no such
        resource."""
        ...


class UnknownTool(LookupError):
    """A ``tools/call`` names a tool that the backend does not list."""


@dataclass
class Call:
    """One running tool call: its cancellation and its progress."""

    cancelled: threading.Event = field(default_factory=threading.Event)
    progress: Callable[[float, float | None, str | None], None] | None = None
    """Report ``progress`` (increasing), an optional ``total`` and an optional ``message``; ``None`` when
    the request carried no progress token."""


class _Failure(Exception):
    """A JSON-RPC error response for the current request."""

    def __init__(self, code: int, message: str, data: Any = None) -> None:
        super().__init__(message)
        self.code, self.message, self.data = code, message, data


@dataclass
class _Request:
    id: str | int
    method: str
    params: Json
    version: str
    """``MODERN`` or the negotiated legacy version."""


def _is_id(value: Any) -> bool:
    return isinstance(value, str) or (isinstance(value, int) and not isinstance(value, bool))


def _id_of(body: Json) -> str | int | None:
    """The id of a message, when it is a valid one (for the error response of a malformed request)."""
    value = body.get("id")
    return cast("str | int", value) if _is_id(value) else None


def _shape_tool(tool: Json, version: str) -> Json:
    if version == "2025-03-26":
        return {k: v for k, v in tool.items() if k != "title"}
    return tool


def _shape_call(result: Json, version: str) -> Json:
    if version == "2025-03-26":
        return {k: v for k, v in result.items() if k != "structuredContent"}
    return result


class Server:
    """The MCP server: :meth:`serve` reads ``inp`` until its end and writes to ``out``."""

    def __init__(
        self,
        backend: Backend,
        *,
        name: str,
        version: str,
        instructions: str = "",
        out: BinaryIO,
        log: TextIO | None = None,
    ) -> None:
        self.backend, self.out, self.log = backend, out, log if log is not None else sys.stderr
        self.info = {"name": name, "version": version}
        self.instructions = instructions
        self.legacy: str | None = None
        """The revision ``initialize`` negotiated, or ``None`` before it."""
        self._write = threading.Lock()
        self._calls: dict[str | int, Call] = {}
        self._calls_lock = threading.Lock()
        self._queue: queue.Queue[tuple[_Request, Call] | None] = queue.Queue()
        self._worker = threading.Thread(target=self._work, name="fenolite-mcp-calls", daemon=True)

    # ------------------------------------------------------------------ the stream

    def serve(self, inp: BinaryIO, *, drain: bool = False) -> int:
        """Answer every line of ``inp``; return 0 at its end. Without ``drain`` the calls still queued or
        running at the end are cancelled (the client closed the stream, as the stdio transport ends a
        session); with it they finish first (tests)."""
        self._worker.start()
        for raw in inp:
            line = raw.strip()
            if line:
                self.receive(line)
        if not drain:
            with self._calls_lock:
                for call in self._calls.values():
                    call.cancelled.set()
        self._queue.put(None)
        self._worker.join()
        return 0

    def receive(self, line: bytes) -> None:
        """Handle one line: a message, or an array of messages for a ``2025-03-26`` client."""
        try:
            message = json.loads(line.decode("utf-8"))
        except (UnicodeDecodeError, ValueError) as exc:
            self._send(self._error(None, PARSE_ERROR, f"not a JSON text: {exc}"))
            return
        if isinstance(message, list):
            self._batch(cast("list[Any]", message))
            return
        reply = self._message(message, batch=False)
        if reply is not None:
            self._send(reply)

    def _batch(self, items: list[Any]) -> None:
        if self.legacy != BATCHING or not items:
            self._send(
                self._error(None, INVALID_REQUEST, f"a batch is a message of protocol {BATCHING} only")
            )
            return
        replies = [reply for item in items if (reply := self._message(item, batch=True)) is not None]
        if replies:
            self._send(replies)

    def _send(self, message: Json | list[Json]) -> None:
        data = json.dumps(message, ensure_ascii=False, separators=(",", ":")).encode("utf-8") + b"\n"
        with self._write:
            self.out.write(data)
            self.out.flush()

    def _note(self, text: str) -> None:
        print(f"fenolite mcp: {text}", file=self.log, flush=True)

    # ------------------------------------------------------------------ messages

    @staticmethod
    def _error(request_id: str | int | None, code: int, message: str, data: Any = None) -> Json:
        error: Json = {"code": code, "message": message}
        if data is not None:
            error["data"] = data
        return {"jsonrpc": "2.0", "id": request_id, "error": error}

    def _message(self, message: Any, *, batch: bool) -> Json | None:
        """The response to ``message``, or ``None`` (a notification, a client's response, or a call that
        the worker answers)."""
        if not isinstance(message, dict):
            return self._error(None, INVALID_REQUEST, "a message is a JSON object")
        body = cast("Json", message)
        method = body.get("method")
        if body.get("jsonrpc") != "2.0":
            return self._error(_id_of(body), INVALID_REQUEST, 'jsonrpc must be "2.0"')
        if method is None:  # a response: a client writes none; nothing to answer
            return None
        params_raw = body.get("params", {})
        if not isinstance(params_raw, dict):
            return self._error(_id_of(body), INVALID_REQUEST, "params must be an object")
        params = cast("Json", params_raw)
        if "id" not in body:
            if isinstance(method, str):
                self._notification(method, params)
            return None
        if not _is_id(body["id"]) or not isinstance(method, str):
            return self._error(
                None, INVALID_REQUEST, "a request has a string or integer id and a string method"
            )
        request_id = cast("str | int", body["id"])
        try:
            request = self._request(request_id, method, params)
            if request.method == "tools/call" and not batch:
                self._enqueue(request)
                return None
            return {"jsonrpc": "2.0", "id": request_id, "result": self._result(request, Call())}
        except _Failure as failure:
            return self._error(request_id, failure.code, failure.message, failure.data)
        except Exception as exc:  # a defect: answered, logged, never a crash of the server
            self._note(f"internal error on {method}: {exc!r}")
            return self._error(request_id, INTERNAL_ERROR, f"internal error: {exc}")

    def _notification(self, method: str, params: Json) -> None:
        if method == "notifications/cancelled":
            request_id = params.get("requestId")
            with self._calls_lock:
                call = self._calls.get(cast("str | int", request_id)) if _is_id(request_id) else None
            if call is not None:
                call.cancelled.set()
                self._note(f"call {request_id!r} cancelled: {params.get('reason', 'no reason given')}")
        # notifications/initialized and any other notification need nothing

    def _request(self, request_id: str | int, method: str, params: Json) -> _Request:
        """The request with the version that serves it; raises :class:`_Failure` for an unserved version."""
        if method == "initialize":
            return _Request(request_id, method, params, LEGACY[0])
        meta = params.get("_meta")
        named = cast("Json", meta).get(VERSION_KEY) if isinstance(meta, dict) else None
        if named is not None:
            if named != MODERN:
                raise _Failure(
                    UNSUPPORTED_VERSION,
                    "Unsupported protocol version",
                    {"supported": [MODERN], "requested": named},
                )
            if not isinstance(cast("Json", meta).get(CAPABILITIES_KEY), dict):
                raise _Failure(INVALID_PARAMS, f"_meta lacks {CAPABILITIES_KEY}")
            return _Request(request_id, method, params, MODERN)
        if self.legacy is not None:
            return _Request(request_id, method, params, self.legacy)
        if method == "ping":
            return _Request(request_id, method, params, LEGACY[0])
        raise _Failure(
            INVALID_PARAMS,
            f"the request names no protocol version: put {VERSION_KEY} ({MODERN}) and {CAPABILITIES_KEY} in "
            "params._meta, or send initialize first",
        )

    def _result(self, request: _Request, call: Call) -> Json:
        modern = request.version == MODERN
        method, params = request.method, request.params
        if method == "initialize":
            return self._initialize(params)
        if method == "server/discover" and modern:
            result: Json = {
                "supportedVersions": [MODERN],
                "capabilities": {"tools": {}, "resources": {}},
                **({"instructions": self.instructions} if self.instructions else {}),
                **CACHE,
            }
        elif method == "ping" and not modern:
            return {}
        elif method == "tools/list":
            self._no_cursor(params)
            result = {"tools": [_shape_tool(tool, request.version) for tool in self.backend.tools()]}
            result |= CACHE if modern else {}
        elif method == "tools/call":
            result = self._call(params, call, request.version)
        elif method == "resources/list":
            self._no_cursor(params)
            result = {"resources": self.backend.resources()} | (CACHE if modern else {})
        elif method == "resources/read":
            uri = params.get("uri")
            if not isinstance(uri, str):
                raise _Failure(INVALID_PARAMS, "resources/read needs a string uri")
            contents = self.backend.read(uri)
            if contents is None:
                raise _Failure(
                    INVALID_PARAMS if modern else LEGACY_NOT_FOUND, "Resource not found", {"uri": uri}
                )
            result = {"contents": contents} | (CACHE if modern else {})
        else:
            raise _Failure(METHOD_NOT_FOUND, f"Method not found: {method}")
        if modern:
            meta = cast("Json", result.get("_meta", {}))
            result = {"resultType": "complete", **result, "_meta": {**meta, SERVER_INFO_KEY: self.info}}
        return result

    def _initialize(self, params: Json) -> Json:
        asked = params.get("protocolVersion")
        self.legacy = asked if isinstance(asked, str) and asked in LEGACY else LEGACY[0]
        result: Json = {
            "protocolVersion": self.legacy,
            "capabilities": {"tools": {}, "resources": {}},
            "serverInfo": self.info,
        }
        if self.instructions:
            result["instructions"] = self.instructions
        return result

    @staticmethod
    def _no_cursor(params: Json) -> None:
        if params.get("cursor") is not None:  # every list is one page: no cursor was ever given out
            raise _Failure(INVALID_PARAMS, "unknown cursor: every list of this server is one page")

    def _call(self, params: Json, call: Call, version: str) -> Json:
        name, arguments = params.get("name"), params.get("arguments", {})
        if not isinstance(name, str) or not isinstance(arguments, dict):
            raise _Failure(INVALID_PARAMS, "tools/call needs a string name and object arguments")
        try:
            result = self.backend.call(name, cast("Json", arguments), call)
        except UnknownTool:
            raise _Failure(INVALID_PARAMS, f"Unknown tool: {name}") from None
        return _shape_call(result, version)

    # ------------------------------------------------------------------ the worker

    def _enqueue(self, request: _Request) -> None:
        meta = request.params.get("_meta")
        token = cast("Json", meta).get("progressToken") if isinstance(meta, dict) else None
        call = Call()
        if _is_id(token):
            call.progress = self._reporter(cast("str | int", token), call)
        with self._calls_lock:
            self._calls[request.id] = call
        self._queue.put((request, call))

    def _reporter(self, token: str | int, call: Call) -> Callable[[float, float | None, str | None], None]:
        last: list[float] = []

        def report(progress: float, total: float | None, message: str | None) -> None:
            if call.cancelled.is_set() or (last and progress <= last[0]):
                return  # progress must increase, and a cancelled request gets no more messages
            last[:] = [progress]
            params: Json = {"progressToken": token, "progress": progress}
            if total is not None:
                params["total"] = total
            if message:
                params["message"] = message
            self._send({"jsonrpc": "2.0", "method": "notifications/progress", "params": params})

        return report

    def _work(self) -> None:
        while (item := self._queue.get()) is not None:
            request, call = item
            reply: Json | None = None
            try:
                if not call.cancelled.is_set():
                    try:
                        reply = {"jsonrpc": "2.0", "id": request.id, "result": self._result(request, call)}
                    except _Failure as failure:
                        reply = self._error(request.id, failure.code, failure.message, failure.data)
                    except Exception as exc:  # a defect of a tool: answered, logged
                        self._note(f"internal error on tools/call: {exc!r}")
                        reply = self._error(request.id, INTERNAL_ERROR, f"internal error: {exc}")
            finally:
                call.progress = None  # no progress after completion
                with self._calls_lock:
                    self._calls.pop(request.id, None)
            if reply is not None and not call.cancelled.is_set():
                self._send(reply)


__all__ = [
    "BATCHING",
    "LEGACY",
    "MODERN",
    "Backend",
    "Call",
    "Server",
    "UnknownTool",
]
