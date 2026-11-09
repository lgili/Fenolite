# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""A written drawing is held to the code less what the source drawing disagrees with itself, pin by pin
(change c0470, design D5)."""

from __future__ import annotations

from fenolite.api import conversion
from fenolite.core.errors import Issue


def _pin(where: str) -> Issue:
    return Issue("drawn.netlist-differs", "error", f"{where} is on another net", where)


def _name(where: str) -> Issue:
    return Issue("drawn.net-name-differs", "error", f"the net at {where} is named otherwise", where)


def test_the_pins_the_source_has_wrong_itself_are_not_the_conversions() -> None:
    source = ([_pin("JP6-5"), _pin("JP6-6")], [_name("N1")])
    written = ([_pin("JP6-5"), _pin("JP6-6"), _pin("R1-1"), _pin("R1-2")], [_name("N1"), _name("N2")])
    found = conversion._net_differences(source, written)  # pyright: ignore[reportPrivateUsage]
    assert [d.where for d in found] == ["R1-1", "N2"]
    assert found[0].a == "the drawing does not mean the code: R1-1 is on another net (and 1 more)"
    assert all(d.kind == "drawn-net" for d in found)


def test_a_count_that_differs_does_not_hide_a_pin() -> None:
    """The summary of ``compare`` counts the pins; the source's own pins are taken by pin, not by message."""
    source = ([_pin("A-1")], [])
    assert conversion._net_differences(source, ([_pin("A-1")], [])) == []  # pyright: ignore[reportPrivateUsage]
    found = conversion._net_differences(source, ([_pin("B-1")], []))  # pyright: ignore[reportPrivateUsage]
    assert [d.a for d in found] == ["the drawing does not mean the code: B-1 is on another net"]
