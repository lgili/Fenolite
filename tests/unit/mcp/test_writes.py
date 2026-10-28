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


SCRIPT = 'from fenolite.dsl import Design\n\nWIDTH_MM = 20\ndesign = Design("demo")\n'


def test_edit_through_the_server(tmp_path: Path) -> None:
    """Scenario "Edit through the server"."""
    root = tmp_path / "p"
    tool = server(root, allow_edit=True)
    (root / "design.py").write_text(SCRIPT, encoding="utf-8")
    pairs = [{"old": "WIDTH_MM = 20", "new": "WIDTH_MM = 25"}]
    dry = tool.call("fenolite_edit", {"path": "design.py", "edits": pairs}, Call())
    result = dry["structuredContent"]["result"]
    assert dry["isError"] is False and "+WIDTH_MM = 25" in result["diff"]
    assert (root / "design.py").read_text(encoding="utf-8") == SCRIPT
    confirm = {"path": "design.py", "edits": pairs, "confirm": True, "plan": result["plan_id"]}
    written = tool.call("fenolite_edit", confirm, Call())
    assert written["isError"] is False, written["structuredContent"]
    assert "WIDTH_MM = 25" in (root / "design.py").read_text(encoding="utf-8")
    assert list((tmp_path / "state" / "mcp-inputs").iterdir()) == []  # no input file is left


def test_edit_confirmed_with_another_content(tmp_path: Path) -> None:
    """A confirmation whose content differs from its dry run's is refused by the command line."""
    root = tmp_path / "p"
    tool = server(root, allow_edit=True)
    (root / "design.py").write_text(SCRIPT, encoding="utf-8")
    plan = tool.call("fenolite_edit", {"path": "design.py", "content": SCRIPT + "# a\n"}, Call())
    plan_id = plan["structuredContent"]["result"]["plan_id"]
    other = {"path": "design.py", "content": SCRIPT + "# b\n", "confirm": True, "plan": plan_id}
    reply = tool.call("fenolite_edit", other, Call())
    assert reply["isError"] is True and reply["structuredContent"]["code"] == "FEN-4002"
    assert (root / "design.py").read_text(encoding="utf-8") == SCRIPT


@pytest.mark.parametrize(
    "arguments",
    [
        {"path": "design.py"},
        {"path": "design.py", "content": "x", "edits": []},
        {"path": "design.py", "edits": [{"old": "a"}]},
        {"path": "design.py", "content_file": "/etc/hostname"},
    ],
)
def test_edit_inputs_refused(tmp_path: Path, arguments: dict[str, Any]) -> None:
    reply = server(tmp_path / "p", allow_edit=True).call("fenolite_edit", arguments, Call())
    assert reply["isError"] is True and reply["structuredContent"]["code"] == "FEN-2001"
