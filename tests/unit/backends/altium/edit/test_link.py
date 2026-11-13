# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""A PCB component linked to its schematic part (change c0499, design D4), on the Part J kit project,
authored for Fenolite: the whole job of adding a part to a project through public names only."""

from __future__ import annotations

import ast
from pathlib import Path

from fenolite.backends.altium import edit
from fenolite.backends.altium.backend import AltiumBackend
from fenolite.backends.altium.edit.state import State
from tests.unit.backends.altium.edit.conftest import OPEN, mm

SCH_OPEN = dict.fromkeys(("add_part", "annotate", "create"), True)
MIL = 25_400
PIN, LEFT = (2900 * MIL, 6450 * MIL), (2700 * MIL, 6450 * MIL)


def _sheet(board: Path) -> edit.SchematicSession:
    session = edit.open(board.with_suffix(".SchDoc"), gates=SCH_OPEN, project=board.with_suffix(".PrjPcb"))
    assert isinstance(session, edit.SchematicSession)
    return session


def _board(board: Path) -> edit.Session:
    session = edit.open(board, gates=OPEN)
    assert isinstance(session, edit.Session)
    return session


def _add_part(board: Path) -> None:
    """R1 copied as R?, annotated R9, its pin 1 wired to a ``GND`` power port, and a net label on it."""
    sheet = board.with_suffix(".SchDoc")
    session = (
        _sheet(board)
        .add_part(sheet, "R1", at=(500 * MIL, 0))
        .annotate(edit.Part("R?"), "R9", old="R?")
        .add_wire([PIN, LEFT])
        .add_power_port("GND", LEFT)
        .add_net_label("GND", (2800 * MIL, 6450 * MIL))
    )
    receipt = session.declare_connectivity().commit(sheet, backup=False)
    assert receipt.written, receipt.issues


def _linked(board: Path, part: str = "R9") -> edit.Receipt:
    session = _board(board).add_component(board, "R1", designator="R9", at=(mm(32), mm(22)))
    session.link("R9", project=board.with_suffix(".PrjPcb"), part=part)
    return session.commit(board, backup=False)


def test_a_copied_component_is_linked(board: Path) -> None:
    """Scenario "A copied component linked": the import links R9's footprint to the part R9 by its path."""
    _add_part(board)
    receipt = _linked(board)
    assert receipt.written, receipt.issues
    [record] = [
        r for r in State.of(board.read_bytes()).properties("Components6") if r.get("SOURCEDESIGNATOR") == "R9"
    ]
    [cls] = [c for c in State.of(board.read_bytes()).properties("Classes6") if c.get("NAME") == "edit"]
    assert record.get("SOURCEHIERARCHICALPATH") == "" and record.get("CHANNELOFFSET") == "3"
    assert (
        record.get("SOURCELIBREFERENCE") == "Mini_R" and record.get("SOURCECOMPONENTLIBRARY") == "edit.SchLib"
    )
    assert cls.get("M3") == "R9"
    result = AltiumBackend().read(board.with_suffix(".PrjPcb"))
    codes = {i.code for i in result.issues}
    assert not codes & {"altium.import.pcb-net-conflict", "altium.import.pcb-only-component",
                        "altium.import.linked-by-designator"}, codes  # fmt: skip
    design = result.design
    assert design.board is not None
    refs = sorted(c.ref for c in design.circuit.components)
    assert refs == ["D1", "R1", "R2", "R9"]
    owners = [f.component_id for f in design.board.footprints]
    assert len(owners) == len(set(owners)) == 4


def test_a_footprint_the_part_does_not_name_refuses(board: Path, tmp_path: Path) -> None:
    """Scenario "A footprint the part does not name": the part D1 names another pattern."""
    before = board.read_bytes()
    session = _board(board).add_component(board, "R1", designator="R9", at=(mm(32), mm(22)))
    receipt = session.link("R9", project=board.with_suffix(".PrjPcb"), part="D1").commit(
        tmp_path / "never.PcbDoc"
    )
    [issue] = receipt.issues
    assert issue.code == "altium.edit.assertion" and "Mini_LED_THT_3mm" in issue.message
    assert "Mini_R_0603" in issue.message and not (tmp_path / "never.PcbDoc").exists()
    assert board.read_bytes() == before
    missing = (
        _board(board)
        .link("R1", project=board.with_suffix(".PrjPcb"), part="R7")
        .commit(tmp_path / "x.PcbDoc")
    )
    assert [i.code for i in missing.issues] == ["altium.edit.assertion"]


def test_link_gate_is_off(board: Path, tmp_path: Path) -> None:
    session = edit.open(board)
    assert isinstance(session, edit.Session)
    receipt = session.link("R1", project=board.with_suffix(".PrjPcb"), part="R1").commit(
        tmp_path / "x.PcbDoc"
    )
    assert [i.code for i in receipt.issues] == ["altium.edit.gate"] and "H-A-EDIT-LINK" in receipt.issues[
        0
    ].message


def test_public_only(board: Path) -> None:
    """Task 4.2: the whole job runs through public names; this module imports no private name of the edit
    package."""
    _add_part(board)
    assert _linked(board).written
    tree = ast.parse(Path(__file__).read_text(encoding="utf-8"))
    names = [
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
        and (node.module or "").startswith("fenolite.backends.altium.edit")
        for alias in node.names
    ]
    assert names and not [n for n in names if n.startswith("_")]
