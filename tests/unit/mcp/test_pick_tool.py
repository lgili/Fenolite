# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The MCP tool of ``fenolite pick`` follows the command (change c0254, task 4.3; mcp-server, "One tool per
public command")."""

from __future__ import annotations

from fenolite.cli.api import discover
from fenolite.mcp.tools import Catalog


def test_pick_tool_follows_the_command() -> None:
    catalog = Catalog(discover())
    definition = catalog.tools["fenolite_pick"].definition
    properties = set(definition["inputSchema"]["properties"])
    assert {
        "path",
        "candidates",
        "update",
        "update_all",
        "propose",
        "source",
        "supplier",
        "allow_offsite",
    } <= properties
    assert {"confirm", "plan", "limit"} <= properties
