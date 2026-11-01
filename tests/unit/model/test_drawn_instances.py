# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Repeated drawn sheets and their instances (capability drawn-schematic, "Repeated drawn sheets"; change
c0276)."""

from __future__ import annotations

import _drawn

from fenolite.core.coords import Point, Size
from fenolite.model.drawn import DrawnSchematic, DrawnSheet, DrawnSheetRef
from fenolite.model.drawn_connect import instances


def _ref(key: str, sheet: str) -> DrawnSheetRef:
    return DrawnSheetRef(key, sheet, key, key, Point(0, 0), Size(1, 1), "2")


def test_two_channels_one_sheet() -> None:
    """Scenario "Two channels, one sheet"."""
    value = _drawn.drawn("repeat")
    found, issues = instances(value)
    assert issues == () and len(found) == 3
    channel = value.sheet("channel")
    assert channel is not None and channel.symbols[0].part == "R1"
    assert [i.component("R1") for i in found if i.sheet == "channel"] == ["ch0/R1", "ch1/R1"]


def test_cycle_refused() -> None:
    """Scenario "Cycle refused"."""
    value = DrawnSchematic(
        "root",
        (
            DrawnSheet("root", sheet_refs=(_ref("a", "a"),)),
            DrawnSheet("a", sheet_refs=(_ref("b", "b"),)),
            DrawnSheet("b", sheet_refs=(_ref("a", "a"),)),
        ),
    )
    _found, issues = instances(value)
    assert [i.code for i in issues] == ["drawn.sheet-unknown"]
    assert "a" in issues[0].message and "b" in issues[0].message and issues[0].severity == "error"


def test_unknown_and_unreached_sheets() -> None:
    value = DrawnSchematic(
        "root", (DrawnSheet("root", sheet_refs=(_ref("x", "nowhere"),)), DrawnSheet("lost"))
    )
    _found, issues = instances(value)
    assert [i.code for i in issues] == ["drawn.sheet-unknown", "drawn.sheet-unknown"]
    assert "nowhere" in issues[0].message and "lost" in issues[1].message
