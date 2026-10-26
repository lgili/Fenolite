# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The MCP protocol layer (capability mcp-server, "MCP server on standard input and output" and "Version
refused"; change c0195), driven with a fake backend: the modern and the legacy eras, JSON-RPC errors, batches,
cancellation and progress."""

from __future__ import annotations

import io
import json
import threading
from typing import Any

from fenolite.mcp.protocol import LEGACY, MODERN, Call, Server, UnknownTool

META = {
    "io.modelcontextprotocol/protocolVersion": MODERN,
    "io.modelcontextprotocol/clientCapabilities": {},
    "io.modelcontextprotocol/clientInfo": {"name": "test", "version": "1"},
}
TOOL = {
    "name": "echo",
    "title": "echo",
    "description": "returns its arguments",
    "inputSchema": {"type": "object"},
    "annotations": {"readOnlyHint": True},
}


class Fake:
    """A backend with one tool, ``echo``, and one resource; ``slow`` waits until it is cancelled."""

    def __init__(self) -> None:
        self.started = threading.Event()

    def tools(self) -> list[dict[str, Any]]:
        return [TOOL]

    def call(self, name: str, arguments: dict[str, Any], call: Call) -> dict[str, Any]:
        if name == "slow":
            self.started.set()
            call.cancelled.wait(10)
            return {"content": [{"type": "text", "text": "late"}]}
        if name != "echo":
            raise UnknownTool(name)
        if call.progress:
            for step in (1, 1, 2):  # the repeated 1 must not be sent: progress increases
                call.progress(step, 2, f"step {step}")
        text = json.dumps(arguments)
        return {"content": [{"type": "text", "text": text}], "structuredContent": arguments, "isError": False}

    def resources(self) -> list[dict[str, Any]]:
        return [{"uri": "fenolite://guide/start", "name": "start", "mimeType": "text/markdown"}]

    def read(self, uri: str) -> list[dict[str, Any]] | None:
        if uri != "fenolite://guide/start":
            return None
        return [{"uri": uri, "mimeType": "text/markdown", "text": "# Start"}]


def exchange(*messages: Any, backend: Fake | None = None) -> list[Any]:
    """Every line the server writes for ``messages`` (each a JSON value, or ``bytes`` sent as they are)."""
    lines = b"".join(m if isinstance(m, bytes) else json.dumps(m).encode() + b"\n" for m in messages)
    out = io.BytesIO()
    server = Server(
        backend or Fake(),
        name="fenolite",
        version="0.0",
        instructions="read the guide",
        out=out,
        log=io.StringIO(),
    )
    server.serve(io.BytesIO(lines), drain=True)
    return [json.loads(line) for line in out.getvalue().splitlines()]


def request(
    rid: int, method: str, params: dict[str, Any] | None = None, *, meta: bool = True
) -> dict[str, Any]:
    body: dict[str, Any] = dict(params or {})
    if meta:
        body["_meta"] = {**META, **body.get("_meta", {})}
    return {"jsonrpc": "2.0", "id": rid, "method": method, "params": body}


INIT = {
    "jsonrpc": "2.0",
    "id": 0,
    "method": "initialize",
    "params": {
        "protocolVersion": "2025-06-18",
        "capabilities": {},
        "clientInfo": {"name": "old", "version": "1"},
    },
}
INITIALIZED = {"jsonrpc": "2.0", "method": "notifications/initialized"}


def test_discover() -> None:
    """Scenarios "Modern discovery" and "Discover names the modern version"."""
    (reply,) = exchange(request(1, "server/discover"))
    result = reply["result"]
    assert reply["id"] == 1 and result["resultType"] == "complete"
    assert result["supportedVersions"] == [MODERN]
    assert result["capabilities"] == {"tools": {}, "resources": {}}
    assert result["_meta"]["io.modelcontextprotocol/serverInfo"] == {"name": "fenolite", "version": "0.0"}
    assert result["instructions"] == "read the guide" and result["cacheScope"] == "private"


def test_modern_list_and_call() -> None:
    listed, called = exchange(
        request(1, "tools/list"), request(2, "tools/call", {"name": "echo", "arguments": {"a": 1}})
    )
    assert listed["result"]["tools"] == [TOOL] and listed["result"]["ttlMs"] == 0
    assert called["result"]["structuredContent"] == {"a": 1} and called["result"]["resultType"] == "complete"


def test_legacy_handshake() -> None:
    """Scenario "Legacy handshake": the client's version is answered, and served for the process."""
    init, listed, pong = exchange(
        INIT, INITIALIZED, request(1, "tools/list", meta=False), request(2, "ping", meta=False)
    )
    assert init["result"]["protocolVersion"] == "2025-06-18"
    assert init["result"]["serverInfo"]["name"] == "fenolite" and "resultType" not in init["result"]
    assert listed["result"] == {"tools": [TOOL]}  # no resultType or cache fields before 2026-07-28
    assert pong == {"jsonrpc": "2.0", "id": 2, "result": {}}


def test_legacy_version_not_served_gets_the_latest() -> None:
    old = {**INIT, "params": {**INIT["params"], "protocolVersion": "2024-11-05"}}
    (init,) = exchange(old)
    assert init["result"]["protocolVersion"] == LEGACY[0]


def test_oldest_legacy_version_drops_new_fields() -> None:
    first = {**INIT, "params": {**INIT["params"], "protocolVersion": "2025-03-26"}}
    _, listed, called = exchange(
        first,
        request(1, "tools/list", meta=False),
        request(2, "tools/call", {"name": "echo", "arguments": {}}, meta=False),
    )
    assert "title" not in listed["result"]["tools"][0]
    assert "structuredContent" not in called["result"] and called["result"]["content"]


def test_unknown_version() -> None:
    """Scenario "Unknown version"."""
    (reply,) = exchange(
        request(1, "tools/list", {"_meta": {"io.modelcontextprotocol/protocolVersion": "1900-01-01"}})
    )
    assert reply["error"]["code"] == -32022
    assert reply["error"]["data"] == {"supported": [MODERN], "requested": "1900-01-01"}


def test_request_without_version_or_handshake() -> None:
    (reply,) = exchange(request(1, "tools/list", meta=False))
    assert reply["error"]["code"] == -32602 and "initialize" in reply["error"]["message"]


def test_modern_request_without_capabilities() -> None:
    body = request(1, "tools/list")
    del body["params"]["_meta"]["io.modelcontextprotocol/clientCapabilities"]
    (reply,) = exchange(body)
    assert reply["error"]["code"] == -32602


def test_json_rpc_errors() -> None:
    parse, invalid, no_id, unknown, ping = exchange(
        b"{not json\n",
        {"jsonrpc": "1.0", "id": 1, "method": "tools/list"},
        {"jsonrpc": "2.0", "id": None, "method": "tools/list"},
        request(4, "prompts/list"),
        request(5, "ping"),
    )
    assert parse["error"]["code"] == -32700 and parse["id"] is None
    assert invalid["error"]["code"] == -32600 and invalid["id"] == 1
    assert no_id["error"]["code"] == -32600
    assert unknown["error"]["code"] == -32601
    assert ping["error"]["code"] == -32601  # 2026-07-28 removed ping


def test_unknown_tool_and_bad_cursor() -> None:
    replies = exchange(request(1, "tools/call", {"name": "nope"}), request(2, "tools/list", {"cursor": "x"}))
    unknown, cursor = sorted(replies, key=lambda r: r["id"])  # the call's reply comes from the worker
    assert unknown["error"]["code"] == -32602 and "nope" in unknown["error"]["message"]
    assert cursor["error"]["code"] == -32602


def test_resources_by_era() -> None:
    listed, read, missing = exchange(
        request(1, "resources/list"),
        request(2, "resources/read", {"uri": "fenolite://guide/start"}),
        request(3, "resources/read", {"uri": "fenolite://guide/none"}),
    )
    assert listed["result"]["resources"][0]["uri"] == "fenolite://guide/start"
    assert read["result"]["contents"][0]["text"] == "# Start"
    assert missing["error"]["code"] == -32602 and missing["error"]["data"] == {"uri": "fenolite://guide/none"}
    _, legacy_missing = exchange(INIT, request(1, "resources/read", {"uri": "x"}, meta=False))
    assert legacy_missing["error"]["code"] == -32002


def test_batches_only_for_2025_03_26() -> None:
    (refused,) = exchange([request(1, "tools/list")])
    assert refused["error"]["code"] == -32600
    first = {**INIT, "params": {**INIT["params"], "protocolVersion": "2025-03-26"}}
    _, batch = exchange(
        first, [request(1, "ping", meta=False), INITIALIZED, request(2, "tools/list", meta=False)]
    )
    assert [reply["id"] for reply in batch] == [1, 2]


def test_notifications_get_no_reply() -> None:
    assert (
        exchange(
            INITIALIZED, {"jsonrpc": "2.0", "method": "notifications/cancelled", "params": {"requestId": 9}}
        )
        == []
    )


def test_progress_increases() -> None:
    call = request(1, "tools/call", {"name": "echo", "arguments": {}, "_meta": {"progressToken": "t"}})
    *notes, reply = exchange(call)
    assert [n["params"]["progress"] for n in notes] == [1, 2]
    assert notes[0]["params"] == {"progressToken": "t", "progress": 1, "total": 2, "message": "step 1"}
    assert reply["id"] == 1


def test_cancelled_call_gets_no_reply() -> None:
    backend = Fake()
    read_end, write_end = __import__("os").pipe()
    out = io.BytesIO()
    server = Server(backend, name="fenolite", version="0.0", out=out, log=io.StringIO())
    with open(read_end, "rb") as inp, open(write_end, "wb") as feed:
        runner = threading.Thread(target=server.serve, args=(inp,), kwargs={"drain": True})
        runner.start()
        feed.write(json.dumps(request(7, "tools/call", {"name": "slow"})).encode() + b"\n")
        feed.flush()
        assert backend.started.wait(10)
        cancel = {
            "jsonrpc": "2.0",
            "method": "notifications/cancelled",
            "params": {"requestId": 7, "reason": "test"},
        }
        feed.write(json.dumps(cancel).encode() + b"\n")
        feed.write(json.dumps(request(8, "tools/list")).encode() + b"\n")
        feed.flush()
        feed.close()
        runner.join(10)
    replies = [json.loads(line) for line in out.getvalue().splitlines()]
    assert [r["id"] for r in replies] == [8]  # nothing for the cancelled call


def test_output_is_one_message_per_line() -> None:
    out = exchange(request(1, "tools/call", {"name": "echo", "arguments": {"text": "a\nb"}}))
    assert out[0]["result"]["structuredContent"] == {"text": "a\nb"}  # the newline travels escaped
