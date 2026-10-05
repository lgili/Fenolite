# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Script copper on the running ``kicad-cli`` (``H-G-FRAME-UUID``, ``H-G-FRAME-ROUTE``; capability
kicad-oracle, "Script copper passes the oracle"; change c0028), and its arcs and via kinds
(``H-G-FRAME-ARC``, ``H-K-COPPER-VIAKINDS``; "Arcs and via kinds pass the oracle"; change c0068)."""

from __future__ import annotations

import _arccases as ac
import pytest
from _probes import major, run

pytestmark = pytest.mark.needs_kicad


def test_copper_uuids_load() -> None:
    """Scenario "Copper uuids survive a re-save", load part: target 9 on both majors, target 10 on 10.0."""
    assert run("pcb-frame-uuid-9") == "load"
    if major() >= 10:
        assert run("pcb-frame-uuid-10") == "load"


def test_copper_uuids_survive_a_resave() -> None:
    if major() < 10:
        pytest.skip("pcb upgrade exists on kicad-cli 10 only")
    assert run("pcb-frame-uuid-keep") == "equal"


def test_routed_nets_are_connected() -> None:
    """Scenario "Routed nets are connected": no unconnected item and no clearance or short on script copper;
    exactly one unconnected item with the cut; none after ``D1`` moved and the build ran again."""
    assert run("pcb-frame-route") == "absent"
    assert run("pcb-frame-route-cut") == "present"


def test_route_follows_a_moved_footprint() -> None:
    assert run("pcb-frame-route-moved") == "absent"


def test_arc_connects_its_ends() -> None:
    """Scenario "An arc connects its ends": no unconnected item and no violation naming the arc; exactly
    one unconnected item with the arc taken out."""
    assert run("pcb-frame-arc") == "absent"
    assert run("pcb-frame-arc-cut") == "present"


def test_arc_keeps_its_uuid_through_a_resave() -> None:
    if major() < 10:
        pytest.skip("pcb upgrade exists on kicad-cli 10 only")
    assert run("pcb-frame-arc-keep") == "equal"


@pytest.mark.parametrize("kind", ["blind", "micro", "buried"])
def test_via_kinds_load_and_connect(kind: str) -> None:
    """Scenario "Via kinds load and connect": the via joins the tracks of its two layers, and nothing names
    it. The control takes the via out and must see its track fall apart."""
    if kind == "buried" and major() < 10:
        pytest.skip("a buried via needs a target-10 board, which kicad-cli 9 does not load")
    assert kind in ac.kinds_for(major())
    assert run(f"pcb-frame-via-{kind}") == "absent"
    assert ac.via_cut_loose(kind, major()), "the control is silent: an open track is not reported"
