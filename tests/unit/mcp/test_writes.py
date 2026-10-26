# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Writes through the MCP server (capability mcp-server, "Writes through a reviewed plan"; change c0195): a
dry run first, a confirmation of its plan second, never a write outside the root."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from fenolite.cli.api import discover
from fenolite.mcp.backend import FenoliteBackend
from fenolite.mcp.protocol import Call

COMMANDS = discover()


@pytest.fixture(autouse=True)
def state(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Plans are staged in the test's own state folder, which the child processes inherit."""
    monkeypatch.setenv("FENOLITE_STATE_DIR", str(tmp_path / "state"))


def server(root: Path, **options: Any) -> FenoliteBackend:
    root.mkdir(parents=True, exist_ok=True)
    return FenoliteBackend(COMMANDS, root=root, timeout=120, **options)


def test_dry_run_then_confirm_reviewed(tmp_path: Path) -> None:
    """Scenario "Dry run, then confirm"."""
    root = tmp_path / "project"
    tool = server(root)
    dry = tool.call("fenolite_init", {"dir": "demo"}, Call())
    result = dry["structuredContent"]["result"]
    assert dry["isError"] is False and result["plan"][0]["path"] == "demo/design.py"
    assert not (root / "demo" / "design.py").exists()  # a dry run writes nothing
    written = tool.call("fenolite_init", {"dir": "demo", "confirm": True, "plan": result["plan_id"]}, Call())
    assert written["isError"] is False, written["structuredContent"]
    receipt = written["structuredContent"]["receipt"]
    assert [row["path"] for row in receipt["written"]] == ["demo/design.py"]
    assert (root / "demo" / "design.py").is_file()


def test_confirm_needs_a_plan(tmp_path: Path) -> None:
    reply = server(tmp_path / "p").call("fenolite_init", {"dir": "demo", "confirm": True}, Call())
    assert reply["isError"] is True and reply["structuredContent"]["code"] == "FEN-2001"
    assert reply["structuredContent"]["where"] == "plan"
    assert not (tmp_path / "p" / "demo").exists()


def test_write_outside_the_root(tmp_path: Path) -> None:
    """Scenario "A write outside the root": a plan made in a wider folder is refused by a narrower server."""
    outer = server(tmp_path / "outer")
    plan = outer.call("fenolite_init", {"dir": "elsewhere"}, Call())["structuredContent"]["result"]["plan_id"]
    inner = server(tmp_path / "outer" / "inner")
    reply = inner.call("fenolite_init", {"dir": "elsewhere", "confirm": True, "plan": plan}, Call())
    assert reply["isError"] is True and reply["structuredContent"]["code"] == "FEN-2001"
    assert (
        "elsewhere" in reply["structuredContent"]["message"]
        and "outside" in reply["structuredContent"]["message"]
    )
    assert not (tmp_path / "outer" / "elsewhere").exists()


def test_plan_of_another_command(tmp_path: Path) -> None:
    tool = server(tmp_path / "p")
    plan = tool.call("fenolite_init", {"dir": "demo"}, Call())["structuredContent"]["result"]["plan_id"]
    reply = tool.call("fenolite_fmt", {"path": "b.kicad_pcb", "confirm": True, "plan": plan}, Call())
    assert reply["isError"] is True and "a plan of init" in reply["structuredContent"]["message"]


def test_read_only_lists_no_writer(tmp_path: Path) -> None:
    tool = server(tmp_path / "p", read_only=True)
    names = {d["name"] for d in tool.tools()}
    assert "fenolite_check" in names and not {"fenolite_init", "fenolite_fmt", "fenolite_route"} & names
