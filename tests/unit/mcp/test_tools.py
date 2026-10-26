# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The tools of the MCP server (capability mcp-server, "One tool per public command", "Commands not exposed";
change c0195): names, schemas from the commands' parsers, annotations and command lines."""

from __future__ import annotations

import pytest

from fenolite.cli.api import discover
from fenolite.cli.describe import describe
from fenolite.mcp.tools import NOT_TOOLS, Catalog, InputRefused, tool_name

COMMANDS = discover()
CATALOG = Catalog(COMMANDS)
PUBLIC = sorted(name for name, command in COMMANDS.items() if not command.hidden and name not in NOT_TOOLS)


def test_tools_listed() -> None:
    """Scenario "Tools follow the commands": one tool per public command, in name order."""
    assert [d["name"] for d in CATALOG.definitions()] == [tool_name(name) for name in PUBLIC]
    for definition in CATALOG.definitions():
        command = COMMANDS[definition["title"]]
        own = {a.name for a in describe(command).arguments} - {"dry_run", "confirm", "plan"}
        properties = set(definition["inputSchema"]["properties"])
        assert own - {"serve", "port", "no_browser"} <= properties, definition["name"]
        assert {"fields", "limit", "cursor", "seed", "timestamp"} <= properties
        assert ({"confirm", "plan"} <= properties) == command.mutates
        assert definition["inputSchema"]["additionalProperties"] is False


def test_tools_excluded() -> None:
    """Scenario "Excluded commands"."""
    names = {d["name"] for d in CATALOG.definitions()}
    assert not {"fenolite_mcp", "fenolite_skill", "fenolite__echo"} & names
    assert "serve" not in CATALOG.tools["fenolite_view"].definition["inputSchema"]["properties"]


def test_tool_schema_follows_the_parser() -> None:
    properties = CATALOG.tools["fenolite_view"].definition["inputSchema"]
    assert properties["required"] == ["path"]
    overlay = properties["properties"]["overlay"]
    assert overlay["type"] == "array" and overlay["items"] == {"type": "string"}
    kicad = CATALOG.tools["fenolite_check"].definition["inputSchema"]["properties"]["kicad_version"]
    assert kicad["enum"] == [9, 10] and kicad["default"] == 10


def test_annotations() -> None:
    check = CATALOG.tools["fenolite_check"].definition["annotations"]
    fmt = CATALOG.tools["fenolite_fmt"].definition["annotations"]
    fetch = CATALOG.tools["fenolite_fetch"].definition["annotations"]
    assert check["readOnlyHint"] is True and check["openWorldHint"] is False
    assert fmt["readOnlyHint"] is False and fmt["destructiveHint"] is True
    assert fetch["openWorldHint"] is True


def test_read_only_and_only() -> None:
    read_only = Catalog(COMMANDS, read_only=True)
    assert all(not COMMANDS[t.command].mutates for t in read_only.tools.values())
    assert list(Catalog(COMMANDS, only=["route", "check"]).tools) == ["fenolite_check", "fenolite_route"]
    with pytest.raises(KeyError):
        Catalog(COMMANDS, only=["nope"])


def test_command_line() -> None:
    words = CATALOG.command_line(
        "fenolite_fmt", {"path": "-odd.kicad_pcb", "fields": ["a", "b.c"]}, dry_run=True
    )
    assert words == ["fmt", "--fields=a,b.c", "--dry-run", "--", "-odd.kicad_pcb"]
    view = CATALOG.command_line("fenolite_view", {"path": "p", "overlay": ["x", "y"]}, dry_run=False)
    assert view == ["view", "--overlay=x", "--overlay=y", "--", "p"]
    check = CATALOG.command_line(
        "fenolite_check", {"path": "b", "kicad_version": 9, "limit": 3}, dry_run=False
    )
    assert check == ["check", "--limit=3", "--kicad-version=9", "--", "b"]


@pytest.mark.parametrize(
    ("arguments", "where"),
    [
        ({"path": "b", "nope": 1}, "nope"),
        ({}, "path"),
        ({"path": 3}, "path"),
        ({"path": "b", "kicad_version": 8}, "kicad_version"),
        ({"path": "b", "limit": True}, "limit"),
        ({"path": ["a", "b"]}, "path"),
        ({"path": "b", "fields": "a,b"}, "fields"),
    ],
)
def test_tool_unknown_or_wrong_argument(arguments: dict[str, object], where: str) -> None:
    """An argument outside the schema, or of the wrong type, is refused with the command line's FEN-2001."""
    with pytest.raises(InputRefused) as refused:
        CATALOG.command_line("fenolite_check", arguments, dry_run=False)
    assert refused.value.error.code == "FEN-2001" and refused.value.error.where == where
