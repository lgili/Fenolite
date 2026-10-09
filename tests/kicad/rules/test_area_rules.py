# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Conditions that name a rule area in KiCad (``H-K-AREA-COND``; capability kicad-oracle, "Rule areas and
area conditions are probed"; change c0103): a 2 mm clearance rule scoped to an area and pairs 1 mm apart,
inside and outside. Every run carries the canary; a report without it fails."""

from __future__ import annotations

import _areacases as ac
import _rulebench as rb
import pytest
from _probes import major, run

from fenolite.backends.kicad import rulemap

pytestmark = pytest.mark.needs_kicad


@pytest.mark.parametrize("key", ac.CONDITIONS)
def test_area_condition(key: str) -> None:
    """Scenario "Area conditions on both majors"."""
    found = ac.condition(key)
    rb.require_canary(found.report, found.bench)
    assert ac.condition_selected(key) is ac.CONDITIONS[key], key
    probe = "dru-cond-area" if key == "area" else f"area-cond-{key}"
    assert run(probe) == ("present" if ac.CONDITIONS[key] else "absent")


def test_support_holds_the_running_major() -> None:
    """``SELECTOR_SUPPORT["area"]`` holds the running major exactly when ``dru-cond-area`` is present."""
    assert (major() in rulemap.SELECTOR_SUPPORT["area"]) == (run("dru-cond-area") == "present")
