# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""``fenolite mcp`` (capability cli-contract, "MCP command"; change c0195): its usage errors, ``--list``, its
entry in ``capabilities``, and a session on standard input and output with the real command."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import IO, Any, cast

from fenolite.cli.main import main
from fenolite.mcp.protocol import LEGACY, MODERN


def run(capsys: Any, *argv: str) -> tuple[int, Any, Any]:
    code = main(list(argv))
    captured = capsys.readouterr()
    out = json.loads(captured.out) if captured.out.strip() else None
    err = json.loads(captured.err.strip().splitlines()[-1]) if captured.err.strip() else None
    return code, out, err


def test_unknown_tool_name(capsys: Any) -> None:
    """Scenario "Unknown tool name"."""
    code, _, err = run(capsys, "mcp", "--tools", "nope", "--json")
    assert code == 2 and err["code"] == "FEN-2001" and "nope" in err["message"]


def test_root_not_a_folder(capsys: Any, tmp_path: Path) -> None:
    code, _, err = run(capsys, "mcp", "--root", str(tmp_path / "none"), "--list", "--json")
    assert code == 2 and err["where"] == "--root"


def test_list(capsys: Any, tmp_path: Path) -> None:
    code, out, _ = run(capsys, "mcp", "--root", str(tmp_path), "--tools", "check,route", "--list", "--json")
    assert code == 0 and out["result"]["tools"] == ["fenolite_check", "fenolite_route"]
    assert out["result"]["versions"] == [MODERN, *LEGACY]
    assert "fenolite://guide/start" in out["result"]["resources"]


def test_capabilities_names_the_versions(capsys: Any) -> None:
    code, out, _ = run(capsys, "capabilities", "--no-tools", "--json")
    entry = next(c for c in out["result"]["commands"] if c["name"] == "mcp")
    assert code == 0 and entry["protocol_versions"] == [MODERN, *LEGACY]


def _send(pipe: IO[bytes], message: dict[str, Any]) -> None:
    pipe.write(json.dumps(message).encode() + b"\n")
    pipe.flush()


def _reply(pipe: IO[bytes], request_id: int) -> dict[str, Any]:
    while True:
        message = json.loads(pipe.readline())
        if message.get("id") == request_id:
            return cast("dict[str, Any]", message)


def test_session_on_stdio(tmp_path: Path) -> None:
    """A legacy client and a modern client on one real server process; nothing but messages on stdout."""
    server = subprocess.Popen(
        [sys.executable, "-m", "fenolite", "mcp", "--root", str(tmp_path), "--read-only"],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )  # fmt: skip
    inp, out = cast("IO[bytes]", server.stdin), cast("IO[bytes]", server.stdout)
    meta = {
        "io.modelcontextprotocol/protocolVersion": MODERN,
        "io.modelcontextprotocol/clientCapabilities": {},
    }
    try:
        _send(inp, {"jsonrpc": "2.0", "id": 1, "method": "server/discover", "params": {"_meta": meta}})
        assert _reply(out, 1)["result"]["supportedVersions"] == [MODERN]
        call = {"name": "fenolite_guide", "arguments": {"topic": "start"}, "_meta": meta}
        _send(inp, {"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": call})
        result = _reply(out, 2)["result"]
        assert result["isError"] is False and result["structuredContent"]["result"]["topic"] == "start"
        assert result["_meta"]["fenolite/exit"] == 0
    finally:
        inp.close()
        rest = out.read()
        server.wait(30)
    assert server.returncode == 0 and rest == b""  # no envelope after the last message
