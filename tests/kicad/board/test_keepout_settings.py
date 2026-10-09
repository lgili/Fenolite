# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""What each setting of a rule area forbids in KiCad, and whether a created area keeps its name
(``H-K-AREA-KEEPOUT``, ``H-K-AREA-NAME``; capability kicad-oracle, "Rule areas and area conditions are
probed"; change c0103). Every run carries the canary; a report without it fails."""

from __future__ import annotations

import _areacases as ac
import _rulebench as rb
import pytest
from _probes import major, run

pytestmark = pytest.mark.needs_kicad

EXPECTED = {
    "tracks": "present",
    "cross": "present",
    "vias": "present",
    "pads": "present",
    "footprints": "present",
    "layer": "absent",
    "pour": "absent",
}


@pytest.mark.parametrize("key", ac.KEEPOUT_KEYS)
def test_keepout_setting(key: str) -> None:
    """Scenario "Keep-out settings on both majors"."""
    bench = "tracks" if key in ("cross", "layer") else key
    found = ac.keepout(bench)
    rb.require_canary(found.report, found.bench)
    assert run(f"area-keepout-{key}") == EXPECTED[key]


def test_refill_leaves_the_area_out() -> None:
    if major() < 10:
        pytest.skip("pcb drc --refill-zones --save-board exists from 10.0")
    assert run("area-keepout-refill") == "equal"


def test_name_is_kept_on_resave() -> None:
    """The named benches load on both majors; 10.0 keeps the name when it saves the board."""
    found = ac.keepout("tracks")
    rb.require_canary(found.report, found.bench)
    if major() < 10:
        pytest.skip("pcb upgrade exists from 10.0")
    assert run("area-name-keep") == "equal"
