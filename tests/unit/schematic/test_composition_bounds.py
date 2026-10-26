# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Bounds include text, pins, labelled stubs and usable paper margins."""

from dataclasses import replace

from fenolite.schematic.bounds import content_region, field_boxes, unit_bounds, visible_envelopes
from fenolite.schematic.composition import GRID, Box, Pin, Unit


def sample():
    return Unit(
        "R1#1",
        "R1",
        1,
        "root",
        "R1",
        "1k",
        Box(0, 0, 2 * GRID, GRID),
        (Pin("1", "", (-GRID, 0), (0, 0), 2, "SIGNAL"),),
    )


def test_long_values_and_net_names_expand_bounds():
    unit = sample()
    longer = replace(unit, value="LONG_VALUE_" * 12)
    assert unit_bounds(longer).width > unit_bounds(unit).width
    for visible in visible_envelopes(longer):
        assert unit_bounds(longer).contains(visible.box)
    assert field_boxes(longer, 1)[0].height == GRID


def test_quarter_turns_and_pin_precision_are_kept():
    unit = sample()
    for q in range(4):
        assert all(unit_bounds(unit, q).contains(v.box) for v in visible_envelopes(unit, q))
    assert unit_bounds(unit, 1) != unit_bounds(unit)


def test_content_region_respects_all_margins():
    assert content_region(Box(0, 0, 100, 200), (10, 20, 30, 40)) == Box(10, 30, 80, 160)
