# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Level S: two drawn schematics compared (capability design-equivalence, "Level S compares drawn
schematics"; changes c0276 and c0278). Hermetic: the authored drawn fixtures and the mini library only."""

from __future__ import annotations

import dataclasses

import _drawn
import pytest

from fenolite.backends.kicad import drawn as kdrawn
from fenolite.checks.equivalence import SCHEMATIC_LEVEL, Tolerances, compare_drawn
from fenolite.checks.equivalence.drawn import merged
from fenolite.core.coords import Point
from fenolite.core.units import parse_length
from fenolite.model.drawn import DrawnJunction, DrawnSchematic


def mm(value: float) -> int:
    return parse_length(f"{value}mm")


def at(x: float, y: float) -> Point:
    return Point(mm(x), mm(y))


def replaced(value: DrawnSchematic, **changes: object) -> DrawnSchematic:
    """``value`` with its root sheet changed."""
    root = value.sheets[0]
    return dataclasses.replace(value, sheets=(dataclasses.replace(root, **changes), *value.sheets[1:]))  # type: ignore[arg-type]


def level(a: DrawnSchematic, b: DrawnSchematic, name: str = "flat", **kwargs: object):  # type: ignore[no-untyped-def]
    return compare_drawn(a, b, pins_a=_drawn.pins(a, name), pins_b=_drawn.pins(b, name), **kwargs)  # type: ignore[arg-type]


@pytest.mark.parametrize("name", _drawn.NAMES)
def test_a_drawing_against_itself(name: str) -> None:
    """Scenario "A drawing against itself": the value extracted from the written sheets of each fixture."""
    output = _drawn.build(name)
    root, children = _drawn.sheets(output)
    found = kdrawn.extract_with_pins(
        root,
        children,
        components=kdrawn.refs_to_paths(output.design.circuit),
        root_file=_drawn.root_name(output),
    )
    result = compare_drawn(found.drawn, found.drawn, pins_a=found.pins, pins_b=found.pins)
    assert result.level == SCHEMATIC_LEVEL and result.differences == ()
    assert result.summary["instances"] >= 1 and result.summary["pins"] > 0  # type: ignore[operator]


def test_hier_file_against_its_extraction() -> None:
    """The drawn file of ``hier`` and the drawing its written sheets give back are the same drawing but for
    the field poses that the file leaves to the target."""
    output = _drawn.build("hier")
    root, children = _drawn.sheets(output)
    found = kdrawn.extract_with_pins(
        root,
        children,
        components=kdrawn.refs_to_paths(output.design.circuit),
        root_file=_drawn.root_name(output),
    )
    file = _drawn.drawn("hier")
    result = compare_drawn(file, found.drawn, pins_a=_drawn.pins(file, "hier"), pins_b=found.pins)
    # the file leaves the field poses to the target, which the written sheets then hold
    assert result.differences
    assert all(".fields." in f".{d.field}" and d.a == "" for d in result.differences)


def test_wire_split_differently() -> None:
    """Scenario "Wire split differently"."""
    a = _drawn.drawn("flat")
    first = a.sheets[0].wires[0]
    assert first == (at(114.3, 57.15), at(127, 57.15), at(127, 59.69))
    split = ((first[0], at(120.65, 57.15)), (at(120.65, 57.15), first[1], first[2]), *a.sheets[0].wires[1:])
    b = replaced(a, wires=split)
    assert level(a, b).differences == ()


def test_junction_removed() -> None:
    """Scenario "Junction removed": R1 pin 1 reaches U1's wire through a crossing that a junction joins."""
    base = _drawn.drawn("flat")
    wires = (
        (at(114.3, 57.15), at(130.81, 57.15)),
        (at(127, 50.8), at(127, 59.69)),
        (at(120.65, 57.15), at(120.65, 60.96)),
    )
    a = replaced(
        base, wires=wires, junctions=(DrawnJunction(at(120.65, 57.15)), DrawnJunction(at(127, 57.15)))
    )
    b = replaced(a, junctions=(DrawnJunction(at(120.65, 57.15)),))
    found = level(a, b).differences
    assert [(d.kind, d.field) for d in found] == [("item-missing", "junction"), ("drawn-net", "net")]
    missing, net = found
    assert missing.where == f"/:junction@{mm(127)},{mm(57.15)}" and missing.b == ""
    assert net.where == "R1-1" and "U1-17" in net.a and "U1-17" not in net.b


def test_symbol_pose_and_tolerance() -> None:
    a = _drawn.drawn("flat")
    moved = tuple(
        dataclasses.replace(s, at=Point(s.at.x + 1000, s.at.y)) if s.part == "R1" else s
        for s in a.sheets[0].symbols
    )
    b = replaced(a, symbols=moved)
    # the pins move with the symbol: the wire no longer ends on R1 pin 1
    poses = [d for d in level(a, b).differences if d.kind == "symbol-pose"]
    assert [(d.where, d.field) for d in poses] == [("/:R1:1", "at")]
    loose = level(a, b, tolerances=Tolerances(length_nm=1000)).differences
    assert not [d for d in loose if d.kind == "symbol-pose"]


def test_label_text_is_an_item_field() -> None:
    a = _drawn.drawn("flat")
    labels = tuple(dataclasses.replace(label, text="SCL") for label in a.sheets[0].labels)
    found = [d for d in level(a, replaced(a, labels=labels)).differences if d.kind == "item-field"]
    assert [(d.field, d.a, d.b) for d in found] == [("label.local.text", "SDA", "SCL")]


def test_sheet_missing() -> None:
    a = _drawn.drawn("hier")
    b = dataclasses.replace(a, sheets=(dataclasses.replace(a.sheets[0], sheet_refs=()), *a.sheets[1:]))
    found = level(a, b, "hier").differences
    assert ("sheet-missing", "/child") in [(d.kind, d.where) for d in found]


def test_merged_segments() -> None:
    p = Point
    assert merged(((p(0, 0), p(5, 0)), (p(10, 0), p(5, 0)), (p(20, 0), p(30, 0)))) == (
        (p(0, 0), p(10, 0)),
        (p(20, 0), p(30, 0)),
    )
    assert merged(((p(0, 0), p(4, 4)), (p(2, 2), p(6, 6)), (p(0, 1), p(0, 1)))) == ((p(0, 0), p(6, 6)),)
