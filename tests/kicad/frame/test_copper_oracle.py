# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Script copper on the running ``kicad-cli`` (``H-G-FRAME-UUID``, ``H-G-FRAME-ROUTE``; capability
kicad-oracle, "Script copper passes the oracle"; change c0028)."""

from __future__ import annotations

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
