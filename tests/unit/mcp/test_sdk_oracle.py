# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The official MCP SDK's client against ``fenolite mcp`` (capability mcp-server, "Official client as
oracle"; change c0195). The SDK is in the ``oracles`` extra, imported here and nowhere in ``src``; the test is
skipped where it is not installed, and fails then under ``FENOLITE_REQUIRE=mcp-sdk``, which the CI job ``mcp``
sets. One session opens with ``initialize`` (a
legacy client) and one with ``server/discover`` (a modern client); each lists the tools, calls
``fenolite_capabilities`` and reads a guide page."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import pytest
from _resources import required_resources

from fenolite.mcp.protocol import LEGACY, MODERN

try:
    import anyio  # installed with the SDK
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
except ImportError:  # pragma: no cover - the job "mcp" installs it and sets FENOLITE_REQUIRE=mcp-sdk
    if "mcp-sdk" in required_resources():
        pytest.fail("the official MCP SDK is required (FENOLITE_REQUIRE) but not installed", pytrace=False)
    pytest.skip("the official MCP SDK is in the oracles extra", allow_module_level=True)


async def _session(era: str, root: Path) -> dict[str, Any]:
    params = StdioServerParameters(
        command=sys.executable, args=["-m", "fenolite", "mcp", "--root", str(root), "--read-only"]
    )
    async with stdio_client(params) as (read, write), ClientSession(read, write) as session:
        if era == "legacy":
            version = (await session.initialize()).protocol_version
        else:
            version = MODERN if (await session.discover()).supported_versions == [MODERN] else None
        tools = await session.list_tools()
        called = await session.call_tool("fenolite_capabilities", {"no_tools": True})
        page = await session.read_resource("fenolite://guide/start")
        return {"version": version, "tools": tools, "called": called, "page": page}


@pytest.mark.parametrize("era", ["legacy", "modern"])
def test_official_client_agrees(era: str, tmp_path: Path) -> None:
    """Scenario "The official client agrees"."""
    found = anyio.run(_session, era, tmp_path)
    assert found["version"] == (LEGACY[0] if era == "legacy" else MODERN)
    names = [tool.name for tool in found["tools"].tools]
    assert "fenolite_check" in names and "fenolite_fmt" not in names  # --read-only
    called = found["called"]
    assert called.is_error is False
    envelope = json.loads(called.content[0].text)
    assert envelope["command"] == "capabilities" and envelope["ok"] is True
    assert (called.structured_content or {}).get("command") == "capabilities"
    assert found["page"].contents[0].text.startswith("# ")
