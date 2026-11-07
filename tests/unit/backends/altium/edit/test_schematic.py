# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The edit session of a binary Altium schematic document and its net-signature guard (c0241, task 3.4)."""

from __future__ import annotations

from pathlib import Path

import pytest

from fenolite.backends.altium import edit
from fenolite.backends.altium.adapter.parts import part_groups
from fenolite.backends.altium.edit.schematic import UNIT_NM, net_signature
from fenolite.backends.altium.read.sch import read_schematic

OPEN = dict.fromkeys(("move", "set_property", "delete"), True)


@pytest.fixture
def sheet(board: Path) -> Path:
    return board.with_suffix(".SchDoc")


def _session(path: Path, gates: dict[str, bool] | None = None) -> edit.SchematicSession:
    session = edit.open(path, gates=OPEN if gates is None else gates)
    assert isinstance(session, edit.SchematicSession)
    return session


def test_every_schematic_gate_is_off(sheet: Path, tmp_path: Path) -> None:
    assert not any(edit.SCHEMATIC_GATES.values())
    receipt = _session(sheet, {}).delete(edit.Part("R2")).commit(tmp_path / "never.SchDoc")
    assert not receipt.written and [i.code for i in receipt.issues] == ["altium.edit.gate"]
    assert "H-A-EDIT-SCH" in receipt.issues[0].message


def test_set_property_keeps_the_net_signature(sheet: Path, tmp_path: Path) -> None:
    out = tmp_path / "param.SchDoc"
    receipt = (
        _session(sheet).set_property(edit.Part("R1"), "Comment", "2k2", old="1k").commit(out, backup=False)
    )
    assert receipt.written and receipt.exit_code == 0, receipt.issues
    assert net_signature(read_schematic(out.read_bytes())) == net_signature(
        read_schematic(sheet.read_bytes())
    )
    assert b"2k2" in out.read_bytes() or "2k2".encode("utf-16-le") in out.read_bytes()
    wrong = _session(sheet).set_property(edit.Part("R1"), "Comment", "2k2", old="4k7")
    assert [i.code for i in wrong.commit(tmp_path / "never.SchDoc").issues] == ["altium.edit.assertion"]


def test_an_undeclared_change_of_the_nets_refuses(sheet: Path, tmp_path: Path) -> None:
    out = tmp_path / "never.SchDoc"
    receipt = _session(sheet).delete(edit.Part("R2")).commit(out)
    assert not receipt.written and not out.exists()
    assert [i.code for i in receipt.issues] == ["altium.edit.connectivity"]


def test_a_declared_deletion_reads_back_without_the_part(sheet: Path, tmp_path: Path) -> None:
    out = tmp_path / "deleted.SchDoc"
    receipt = _session(sheet).delete(edit.Part("R2")).declare_connectivity().commit(out, backup=False)
    assert receipt.written, receipt.issues
    refs = sorted(g.ref for g in part_groups(read_schematic(out.read_bytes())))
    assert "R2" not in refs and "R1" in refs and "D1" in refs


def test_a_move_is_whole_ten_mil_units(sheet: Path, tmp_path: Path) -> None:
    receipt = _session(sheet).move(edit.Part("R1"), UNIT_NM // 2, 0).commit(tmp_path / "never.SchDoc")
    assert [i.code for i in receipt.issues] == ["altium.edit.assertion"]
    out = tmp_path / "moved.SchDoc"
    moved = _session(sheet).move(edit.Part("R1"), UNIT_NM * 40, 0).declare_connectivity()
    assert moved.commit(out, backup=False).written
    assert not [i for i in read_schematic(out.read_bytes()).issues if i.severity == "error"]
