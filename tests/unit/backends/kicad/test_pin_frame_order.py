# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The order of the rotation and the mirror of a schematic symbol instance (capability kicad-schematic,
"Pin connection points"; change c0137). KiCad turns a symbol first and mirrors the turned symbol; the
fact is read from the demo sheets of the corpus (``docs/formats/kicad/schematic.md``,
``H-K-SCH-PINFRAME-ORDER``).
Hermetic: no tool runs."""

from __future__ import annotations

from dataclasses import replace

import _pinframe
import pytest
from _buildhelp import blink, build

from fenolite.backends.kicad import sch, sch_netlist, schlayout
from fenolite.backends.kicad.schlayout import SymbolPlacement, label_angle, pin_point
from fenolite.core.coords import Point
from fenolite.model.schematic import SchematicSheet

MM = 1_000_000
PIN = Point(-10 * MM, 5 * MM)
"""A library pin position (Y up) that no rotation or mirror maps onto itself."""
SHEET_POINTS: dict[tuple[int, str], tuple[int, int]] = {
    (0, ""): (-10, -5),
    (90, ""): (-5, 10),
    (180, ""): (10, 5),
    (270, ""): (5, -10),
    (0, "x"): (-10, 5),
    (90, "x"): (-5, -10),
    (180, "x"): (10, -5),
    (270, "x"): (5, 10),
    (0, "y"): (10, -5),
    (90, "y"): (5, 10),
    (180, "y"): (-10, 5),
    (270, "y"): (-5, -10),
}
"""Where ``PIN`` connects on the sheet (Y down, millimetres) for an instance at the origin, worked by hand:
turn counter-clockwise in the library frame, then negate the turned y (``"x"``) or x (``"y"``), then flip
y for the sheet."""
LABEL_ANGLES: dict[tuple[int, str], int] = {
    (0, ""): 180,
    (90, ""): 270,
    (180, ""): 0,
    (270, ""): 90,
    (0, "x"): 180,
    (90, "x"): 90,
    (180, "x"): 0,
    (270, "x"): 270,
    (0, "y"): 0,
    (90, "y"): 270,
    (180, "y"): 180,
    (270, "y"): 90,
}
"""The angle of the label of a pin drawn at 0 degrees in its library (a pin on the left edge), by hand."""


@pytest.mark.parametrize(("rotation", "mirror"), sorted(SHEET_POINTS), ids=lambda v: str(v or "none"))
def test_the_pin_point_of_every_frame(rotation: int, mirror: str) -> None:
    x, y = SHEET_POINTS[(rotation, mirror)]
    assert pin_point(Point(0, 0), PIN, rotation, mirror) == Point(x * MM, y * MM)
    origin = Point(127 * MM, 76_200_000)
    assert pin_point(origin, PIN, rotation, mirror) == Point(origin.x + x * MM, origin.y + y * MM)


@pytest.mark.parametrize(("rotation", "mirror"), sorted(LABEL_ANGLES), ids=lambda v: str(v or "none"))
def test_the_label_angle_of_every_frame(rotation: int, mirror: str) -> None:
    assert label_angle(0, rotation, mirror) == LABEL_ANGLES[(rotation, mirror)]


def test_the_order_matters_only_for_a_mirrored_quarter_turn() -> None:
    """Turning first and mirroring the turned symbol equals mirroring about the other axis first when the
    turn is 90 or 270 degrees, and the same axis first when it is 0 or 180 degrees."""
    other = {"x": "y", "y": "x", "": ""}
    for (rotation, mirror), _point in SHEET_POINTS.items():
        swapped = other[mirror] if rotation in (90, 270) else mirror
        assert pin_point(Point(0, 0), PIN, rotation, mirror) == _pinframe.mirror_first(
            Point(0, 0), PIN, rotation, swapped
        )
    assert _pinframe.distinguishing() == [5, 7, 9, 11]  # (90, x), (270, x), (90, y), (270, y)


def test_a_read_sheet_puts_every_pin_on_its_label() -> None:
    """The authored sheet of the twelve frames, read back: the own netlist puts each pin on the label set
    at the point of the frame, mirrored and turned instances included."""
    sheet = sch.read_schematic(_pinframe.frame_sheet(10), file="frames.kicad_sch")
    assert [(s.rotation // MM, s.mirror) for s in sheet.symbols] == list(_pinframe.FRAMES)
    assert sch_netlist.grammar_issues(sheet) == ()
    found = sch_netlist.own_netlist(sheet, project="frames")
    on = {(node.ref, node.pin): net.name for net in found.nets for node in net.nodes}
    assert on == _pinframe.expected()


def test_labels_of_the_other_order_leave_the_mirrored_quarter_turns_open() -> None:
    """The control: labels set where the old order put the pins lie on no pin of the four mirrored and
    turned instances, so the grammar refuses the sheet."""
    sheet = sch.read_schematic(_pinframe.frame_sheet(10, _pinframe.mirror_first), file="frames.kicad_sch")
    reasons = [issue.message for issue in sch_netlist.grammar_issues(sheet)]
    assert any(reason.startswith("label-off-pin") for reason in reasons), reasons
    assert "12 label(s)" in next(r for r in reasons if r.startswith("label-off-pin"))


def test_a_mirrored_quarter_turn_rests_on_the_corpus() -> None:
    """The evidence of a sheet with a mirrored instance at 90 or 270 degrees names the order's row at its
    level; a sheet without one keeps the evidence it had."""
    sheet = sch.read_schematic(_pinframe.frame_sheet(10), file="frames.kicad_sch")
    found = sch_netlist.evidence_of(sheet)
    assert found.level is sch_netlist.FRAME_ORDER_EVIDENCE.level
    assert "H-K-SCH-PINFRAME-ORDER" in found.hypotheses
    assert set(sch_netlist.EVIDENCE.hypotheses) <= set(found.hypotheses)
    plain = replace(
        sheet, symbols=tuple(s for s in sheet.symbols if not s.mirror or s.rotation % 180_000_000 == 0)
    )
    assert sch_netlist.frame_evidence((plain,)) == ()
    output = build(blink())
    assert output.schematic is not None
    assert sch_netlist.evidence_of(output.schematic.sheet) == sch_netlist.EVIDENCE


def test_every_frame_is_one_a_placements_file_may_ask_for() -> None:
    assert schlayout.PROVED_FRAMES == frozenset(SHEET_POINTS)


def _nodes(sheet: SchematicSheet) -> dict[tuple[str, str], str]:
    found = sch_netlist.own_netlist(sheet, project="blink")
    return {(node.ref, node.pin): net.name for net in found.nets for node in net.nodes}


@pytest.mark.parametrize(("rotation", "mirror"), [(90, "x"), (270, "x"), (90, "y"), (270, "y"), (0, "y")])
def test_a_placed_unit_keeps_its_nets_in_every_frame(rotation: int, mirror: str) -> None:
    """The blink's controller placed mirrored and turned: the generated sheet sets each label where the
    pin connects, so the own netlist of the sheet is that of the blink in its own layout, and the build
    names the order's row only for a mirrored quarter turn."""
    plain = build(blink())
    place = SymbolPlacement(203_200_000, 101_600_000, rotation, mirror)
    placed = build(blink(), symbol_placements={"U1": place})
    assert not [i for i in placed.issues if i.severity == "error"], placed.issues
    assert plain.schematic is not None and placed.schematic is not None
    assert _nodes(placed.schematic.sheet) == _nodes(plain.schematic.sheet)
    quarter = rotation in (90, 270)
    assert ("H-K-SCH-PINFRAME-ORDER" in placed.evidence.hypotheses) is quarter
    assert "H-K-SCH-PINFRAME-ORDER" not in plain.evidence.hypotheses
