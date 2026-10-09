# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Copper given in a part's frame on the running ``kicad-cli`` (``H-G-FRAME-ANCHOR``, ``H-K-VIA-IN-PAD``;
capability kicad-oracle, "Anchored copper passes the oracle"; change c0111): where anchored points land,
thermal arrays inside a pad, and anchored copper after ``fenolite place`` moved its part."""

from __future__ import annotations

import _anchorbench as ab
import pytest
from _probes import major, run

pytestmark = pytest.mark.needs_kicad


def test_frame_anchors_land_in_their_pads() -> None:
    """Scenario "Anchors land in their pads": KiCad names every marker via with the net of the pad its
    anchor names, at 0° and 90° on the top and at 30° on the bottom, and reports no short for one."""
    assert ab.frame_problems(major()) == []
    assert run("copper-anchor-frame") == "equal"
    assert "copper.short" in ab.frame_built(major()).codes(), "each marker shorts its pad on purpose"


def test_frame_control_swaps_the_nets() -> None:
    """The control of the frame probe: board points computed without the mirror land in the other pad."""
    assert run("copper-anchor-frame-control") == "different"


def test_thermal_array_passes_drc() -> None:
    """Scenario "A thermal array passes DRC": joined on the other outer layer, nothing names the array."""
    assert run("copper-anchor-thermal") == "absent"
    assert ab.guard_findings(ab.thermal_built(major(), True)) == []


def test_thermal_array_alone_is_dangling() -> None:
    """Without the track each via of the array gives one ``via_dangling`` warning and nothing else."""
    assert run("copper-anchor-thermal-alone") == "present"
    assert ab.guard_findings(ab.thermal_built(major(), False)) == []


def test_moved_part_takes_its_anchored_copper() -> None:
    """Scenario "Anchored copper follows a moved part": after ``fenolite place --move`` and a rebuild the
    array lies in its pad at the new place, and the rebuild regenerated each via and track of it."""
    assert run("copper-anchor-moved") == "absent"
    built = ab.moved_built(major(), False)
    vias, track = ab.array_uuids()
    assert vias | track <= ab.regenerated(built) and len(vias | track) == 17
    assert "place.copper-left" in built.codes(1), "place itself leaves script copper where it is"
    assert ab.guard_findings(built) == []


def test_moved_control_leaves_its_copper_behind() -> None:
    """The control: the same array given as board points stays behind and its vias dangle."""
    assert run("copper-anchor-moved-control") == "present"
