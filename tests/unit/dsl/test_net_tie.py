# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Net-tie groups in authored footprints (capability dsl-footprint-authoring, "Net-tie groups in authored
footprints"; change c0114)."""

from __future__ import annotations

import pytest

from fenolite.backends.kicad.mod import read_footprint, write_footprint
from fenolite.backends.kicad.sexpr import Node, parse
from fenolite.dsl import DslError, Footprint, mm


def two_pads(name: str = "Tie") -> Footprint:
    footprint = Footprint("Local", name, kind="smd")
    footprint.pad("1", at=(mm(-0.5), mm(0)), size=(mm(0.5), mm(0.5)))
    footprint.pad("2", at=(mm(0.5), mm(0)), size=(mm(0.5), mm(0.5)))
    footprint.line((mm(-0.5), mm(0)), (mm(0.5), mm(0)), layer="F.Cu", width=mm(0.3))
    return footprint


@pytest.mark.parametrize("target", [9, 10])
def test_emit_form(target: int) -> None:
    """Scenario "Emitted form": the child follows ``attr`` and joins the numbers with ``", "``."""
    footprint = two_pads()
    footprint.net_tie("1", "2")
    assert footprint.definition.net_ties == (("1", "2"),)
    text = write_footprint(footprint.definition, target=target)
    assert '(net_tie_pad_groups "1, 2")' in text
    heads = [child.name for child in parse(text).children if isinstance(child, Node)]
    assert heads[heads.index("attr") + 1] == "net_tie_pad_groups"
    assert read_footprint(text, library="Local").net_ties == (("1", "2"),)


def test_emit_several_groups_in_call_order() -> None:
    footprint = Footprint("Local", "Four", kind="smd")
    for number, x in (("1", -1.5), ("2", -0.5), ("3", 0.5), ("4", 1.5)):
        footprint.pad(number, at=(mm(x), mm(0)), size=(mm(0.5), mm(0.5)))
    footprint.net_tie("4", "3")
    footprint.net_tie("1", "2")
    assert footprint.definition.net_ties == (("4", "3"), ("1", "2"))
    assert '(net_tie_pad_groups "4, 3" "1, 2")' in write_footprint(footprint.definition, target=10)


def test_refused_groups() -> None:
    """Scenario "Refused groups"."""
    footprint = two_pads()
    with pytest.raises(DslError, match="at least two"):
        footprint.net_tie("1")
    with pytest.raises(DslError, match="twice"):
        footprint.net_tie("1", "1")
    with pytest.raises(DslError, match="non-empty"):
        footprint.net_tie("1", "")
    with pytest.raises(DslError, match="comma"):
        footprint.net_tie("1", "2,3")
    assert footprint.definition.net_ties == ()
    footprint.net_tie("1", "9")
    with pytest.raises(DslError, match="'9'"):
        _ = footprint.definition
    three = Footprint("Local", "Three", kind="smd")
    for number, x in (("1", -1), ("2", 0), ("3", 1)):
        three.pad(number, at=(mm(x), mm(0)), size=(mm(0.5), mm(0.5)))
    three.net_tie("1", "2")
    three.net_tie("2", "3")
    with pytest.raises(DslError, match="pad '2' is in two net-tie groups"):
        _ = three.definition


@pytest.mark.parametrize("target", [9, 10])
def test_no_group_same_bytes(target: int) -> None:
    """Scenario "No group, same bytes": a footprint without ``net_tie`` writes no child, and its text is
    the tied footprint's text without that one line."""
    plain = write_footprint(two_pads().definition, target=target)
    assert "net_tie_pad_groups" not in plain
    tied = two_pads()
    tied.net_tie("1", "2")
    lines = write_footprint(tied.definition, target=target).splitlines(keepends=True)
    assert "".join(line for line in lines if "net_tie_pad_groups" not in line) == plain
