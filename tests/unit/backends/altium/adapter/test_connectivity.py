# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Connectivity within a sheet (capability altium-import, "Connectivity within a sheet"; change c0043)."""

from __future__ import annotations

import _altium_records as rec

from fenolite.backends.altium.adapter.connectivity import (
    Lines,
    bus_range,
    local_nets,
    on_segment,
    port_ends,
    side_point,
)
from fenolite.backends.altium.adapter.parts import part_groups

U = 100_000
"""SchLength.value steps in one schematic unit."""


def nets_of(sheet: rec.Sheet) -> list[tuple[list[tuple[str, str]], list[tuple[str, str]]]]:
    """Per local net: its pins as (ref, designator) and its identifiers as (kind, text)."""
    document = sheet.document()
    groups = part_groups(document)
    return [
        (
            sorted((groups[pin.group].ref, pin.designator) for pin in net.pins),
            [(ident.kind, ident.text) for ident in net.idents],
        )
        for net in local_nets(document, groups)
    ]


def pins_of(sheet: rec.Sheet) -> list[list[tuple[str, str]]]:
    return [pins for pins, _idents in nets_of(sheet) if pins]


def four_pins(sheet: rec.Sheet) -> None:
    sheet.component("A", [("1", 10, 20)])
    sheet.component("B", [("1", 30, 20)])
    sheet.component("C", [("1", 20, 10)])
    sheet.component("D", [("1", 20, 30)])


# --- geometry -------------------------------------------------------------------------------------------


def test_point_on_segment_is_exact() -> None:
    assert on_segment((20, 10), (10, 10), (30, 10)) and on_segment((10, 10), (10, 10), (30, 10))
    assert not on_segment((31, 10), (10, 10), (30, 10)) and not on_segment((20, 11), (10, 10), (30, 10))
    assert on_segment((2, 2), (0, 0), (4, 4)) and not on_segment((2, 3), (0, 0), (4, 4))
    assert on_segment((5, 5), (5, 5), (5, 5)) and not on_segment((5, 6), (5, 5), (5, 5))
    assert not on_segment((2 * U, 1 * U + 1), (0, 1 * U), (4 * U, 1 * U))


def test_segment_groups_of_lines() -> None:
    lines = Lines(
        [[(0, 0), (10, 0)], [(5, 0), (5, 9)], [(0, 5), (10, 5)], [(20, 0), (30, 0)], [(8, 0), (25, 0)]]
    )
    assert lines.at((5, 0)) == [0, 1, 4] or lines.at((5, 0)) == [0, 1]
    groups = lines.groups()
    assert groups[0] == groups[1] == groups[3] == groups[4]  # a T joint and collinear overlaps
    assert groups[2] != groups[0]  # a crossing without a junction
    assert Lines(lines.lines).groups(junctions=[(5, 5)]) == [0, 0, 0, 0, 0]
    assert Lines([]).groups() == [] and Lines([[(1, 1)]]).at((1, 1)) == [0]


def test_point_helpers() -> None:
    assert side_point((100, 200), 50, 40, 0, 10) == (100, 190)
    assert side_point((100, 200), 50, 40, 1, 10) == (150, 190)
    assert side_point((100, 200), 50, 40, 2, 10) == (110, 200)
    assert side_point((100, 200), 50, 40, 3, 10) == (110, 160)
    sheet = rec.Sheet()
    sheet.port("A", 10, 20, width=30)
    sheet.port("B", 10, 20, width=30, style=4)
    flat, upright = sheet.document().ports()
    assert port_ends(flat) == ((10 * U, 20 * U), (40 * U, 20 * U))
    assert port_ends(upright) == ((10 * U, 20 * U), (10 * U, 50 * U))
    assert bus_range("D[0..3]") == ("D", (0, 1, 2, 3)) and bus_range("DATA[3..0]") == ("DATA", (3, 2, 1, 0))
    assert bus_range("A[7..7]") == ("A", (7,)) and bus_range("A[x]") is None and bus_range("[0..3]") is None
    assert bus_range("D0") is None and bus_range("N[1]") is None


# --- wires and junctions --------------------------------------------------------------------------------


def test_wire_crossing_without_a_junction() -> None:
    sheet = rec.Sheet()
    four_pins(sheet)
    sheet.wire((10, 20), (30, 20))
    sheet.wire((20, 10), (20, 30))
    assert pins_of(sheet) == [[("A", "1"), ("B", "1")], [("C", "1"), ("D", "1")]]
    sheet.junction(20, 20)
    assert pins_of(sheet) == [[("A", "1"), ("B", "1"), ("C", "1"), ("D", "1")]]


def test_wire_t_joint_needs_no_junction() -> None:
    sheet = rec.Sheet()
    sheet.component("A", [("1", 10, 10)])
    sheet.component("B", [("1", 20, 30)])
    sheet.wire((10, 10), (30, 10))
    sheet.wire((20, 10), (20, 30))
    assert pins_of(sheet) == [[("A", "1"), ("B", "1")]]


def test_wire_ends_that_meet_and_collinear_overlap() -> None:
    sheet = rec.Sheet()
    sheet.component("A", [("1", 10, 10)])
    sheet.component("B", [("1", 50, 10)])
    sheet.component("C", [("1", 30, 40)])
    sheet.wire((10, 10), (30, 10))
    sheet.wire((25, 10), (50, 10))  # overlaps the first
    sheet.wire((50, 10), (50, 40), (30, 40))  # a corner, end to end with the second
    assert pins_of(sheet) == [[("A", "1"), ("B", "1"), ("C", "1")]]


def test_wire_one_unit_apart_does_not_connect() -> None:
    sheet = rec.Sheet()
    sheet.component("A", [("1", 10, 10)])
    sheet.component("B", [("1", 31, 10)])
    sheet.wire((10, 10), (30, 10))
    assert pins_of(sheet) == [[("A", "1")], [("B", "1")]]


def test_pin_end_inside_a_segment_is_a_point_on_the_wire() -> None:
    sheet = rec.Sheet()
    sheet.component("A", [("1", 10, 10)])
    sheet.component("B", [("1", 20, 10)])
    sheet.wire((10, 10), (30, 10))
    assert pins_of(sheet) == [[("A", "1"), ("B", "1")]]


def test_two_points_at_one_position_connect() -> None:
    sheet = rec.Sheet()
    sheet.component("A", [("1", 10, 10)])
    sheet.component("B", [("1", 10, 10)])
    sheet.power("GND", 10, 10)
    assert nets_of(sheet) == [([("A", "1"), ("B", "1")], [("power", "GND")])]


def test_bus_line_is_no_wire_segment() -> None:
    sheet = rec.Sheet()
    sheet.component("A", [("1", 10, 10)])
    sheet.component("B", [("1", 10, 30)])
    sheet.bus((40, 0), (40, 50))
    sheet.wire((10, 10), (38, 10))
    sheet.wire((10, 30), (38, 30))
    sheet.bus_entry((38, 10), (40, 12))
    sheet.bus_entry((38, 30), (40, 32))
    sheet.label("A0", 20, 10)
    sheet.label("A1", 20, 30)
    assert nets_of(sheet) == [([("A", "1")], [("label", "A0")]), ([("B", "1")], [("label", "A1")])]


# --- names, marks and order -----------------------------------------------------------------------------


def test_labels_of_one_name_join_without_letter_case() -> None:
    sheet = rec.Sheet()
    sheet.component("A", [("1", 10, 10)])
    sheet.component("B", [("1", 10, 30)])
    sheet.wire((10, 10), (30, 10))
    sheet.wire((10, 30), (30, 30))
    sheet.label("CLK", 20, 10)
    sheet.label("clk", 20, 30)
    assert nets_of(sheet) == [([("A", "1"), ("B", "1")], [("label", "CLK"), ("label", "clk")])]


def test_label_and_power_port_of_one_name_do_not_join() -> None:
    sheet = rec.Sheet()
    sheet.component("A", [("1", 10, 10)])
    sheet.component("B", [("1", 10, 30)])
    sheet.wire((10, 10), (30, 10))
    sheet.label("GND", 20, 10)
    sheet.power("GND", 10, 30)
    sheet.power("GND", 90, 90)
    assert nets_of(sheet) == [
        ([("A", "1")], [("label", "GND")]),
        ([("B", "1")], [("power", "GND"), ("power", "GND")]),
    ]


def test_port_connects_at_both_ends_and_off_sheet_connectors_are_their_own_kind() -> None:
    sheet = rec.Sheet()
    sheet.component("A", [("1", 10, 10)])
    sheet.component("B", [("1", 70, 10)])
    sheet.port("EN", 30, 10, width=20)
    sheet.wire((10, 10), (30, 10))
    sheet.wire((50, 10), (70, 10))
    sheet.power("EN", 90, 90, off_sheet=True)
    assert nets_of(sheet) == [([("A", "1"), ("B", "1")], [("port", "EN")]), ([], [("offsheet", "EN")])]


def test_hidden_pin_joins_by_its_position_only() -> None:
    """H-A-IMP-HIDDEN-PIN: no source row gives a key for a hidden pin's net, so none is read."""
    sheet = rec.Sheet()
    fields = {"8": {"PINCONGLOMERATE": "4", "HIDDENNETNAME": "VCC"}}
    sheet.component("U1", [("8", 10, 10)], pin_fields=fields)  # type: ignore[arg-type]
    sheet.component("R1", [("1", 30, 10)])
    sheet.wire((10, 10), (30, 10))
    sheet.power("VCC", 90, 90)
    assert nets_of(sheet) == [([("R1", "1"), ("U1", "8")], []), ([], [("power", "VCC")])]


def test_no_erc_marks_a_lone_pin() -> None:
    sheet = rec.Sheet()
    sheet.component("U1", [("1", 10, 10), ("2", 10, 20), ("3", 10, 30)])
    sheet.component("R1", [("1", 30, 20)])
    sheet.no_erc(10, 10)
    sheet.no_erc(10, 20)  # on a pin that a wire joins to another pin: no mark
    sheet.wire((10, 20), (30, 20))
    sheet.no_erc(10, 30)
    sheet.label("X", 10, 30)  # a label at the pin: no mark
    document = sheet.document()
    found = local_nets(document)
    assert [(len(net.pins), net.no_connect) for net in found] == [(1, True), (2, False), (1, False)]


def test_local_nets_come_in_stream_order() -> None:
    sheet = rec.Sheet()
    sheet.component("Z9", [("1", 10, 10)])
    sheet.component("A1", [("1", 10, 30)])
    sheet.label("LATE", 90, 90)
    sheet.label("B", 10, 30)
    first = local_nets(sheet.document())
    assert [net.locators[0] for net in first] == ["FileHeader#4", "FileHeader#8", "FileHeader#9"]
    assert first == local_nets(sheet.document())
