# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Probes first (c0031 Decision 15; hypotheses H-K-ZONE-DEFAULTS and H-K-ZONE-FAT9), run before the model
code. Stop rule: when ``zone-defaults-t10`` or ``zone-fat9`` gives another outcome, the ``ZoneSettings``
defaults or the target-9 form are corrected from the observation before the model is written.
``zone-clearance-drc`` records a fact for the copper check; Fenolite's behaviour does not depend on it."""

from __future__ import annotations

import pytest
from _probes import run

pytestmark = pytest.mark.needs_kicad


@pytest.mark.kicad_min_major(10)
def test_defaults() -> None:
    """A zone without setting children is re-saved with KiCad's new-zone values."""
    assert run("zone-defaults-t10") == "equal"


def test_fat9() -> None:
    """A target-9 fill is plotted as written with ``(filled_areas_thickness no)``, and 0.125 mm larger per
    side without it (9.0.9 and 10.0.6)."""
    assert run("zone-fat9") == "equal"


@pytest.mark.kicad_min_major(10)
def test_clearance_drc() -> None:
    """``pcb drc`` without a refill applies the zone's clearance to its fills."""
    assert run("zone-clearance-drc") == "present"
