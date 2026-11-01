# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The emitted ``design.py`` (capability board-to-code, "Emitted design content"; change c0275)."""

from __future__ import annotations

from pathlib import Path

from _importcode import PROJECT, build, built_board, imported

from fenolite.core.coords import Point


def test_positions_survive_exactly(tmp_path: Path) -> None:
    reply = imported(tmp_path, PROJECT, "--confirm")
    assert reply.exit_code == 0, reply.error
    text = (tmp_path / "out" / "design.py").read_text(encoding="utf-8")
    assert 'j1.place(mm("2.54"), mm("10"), rot=90, locked=True)' in text
    assert build(tmp_path / "out").exit_code == 0
    board = built_board(tmp_path / "out").design
    refs = {c.id: c.ref for c in board.circuit.components}
    assert board.board is not None
    (j1,) = [fp for fp in board.board.footprints if refs[fp.component_id] == "J1"]
    assert (j1.position, j1.rotation, j1.locked) == (Point(102_540_000, 110_000_000), 90_000_000, True)


def test_section_order(tmp_path: Path) -> None:
    assert imported(tmp_path, PROJECT, "--confirm").exit_code == 0
    text = (tmp_path / "out" / "design.py").read_text(encoding="utf-8")
    marks = [
        "# SPDX-License-Identifier",
        "from fenolite.dsl import",
        'design = Design("two_sheet")',
        "design.board(",
        'Net("GND")',
        "design.rules.netclass(",
        "Part(",
        "Module(",
        "connect(",
        ".place(",
        "design.zone(",
        "design.rule_area(",
        "design.line(",
        "copper.apply(design",
    ]
    places = [text.index(mark) for mark in marks]
    assert places == sorted(places)


def test_net_classes_kept(tmp_path: Path) -> None:
    assert imported(tmp_path, PROJECT, "--confirm").exit_code == 0
    assert build(tmp_path / "out").exit_code == 0
    design = built_board(tmp_path / "out").design
    from fenolite.backends.kicad.pro import apply_project, read_project

    info = read_project(tmp_path / "out" / "built" / "two_sheet.kicad_pro")
    design = apply_project(design, info)
    (power,) = [cls for cls in design.circuit.netclasses if cls.name == "Power"]
    assert (power.clearance, power.track_width) == (200_000, 500_000)
    members = sorted(net.name for net in design.circuit.nets if net.netclass_id == power.id)
    assert members == ["GND", "VIN"]
