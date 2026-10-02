# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Probes first (c0011 Decision 25; hypotheses H-K-BUILD-PATHPROP, H-K-BUILD-LIBTABLE, H-K-BUILD-TRIAD):
the unrouted blink layout through the model API. Outcomes are the ``build-*`` probes."""

from __future__ import annotations

import _buildcases as bc
import pytest
from _probes import major, run

pytestmark = pytest.mark.needs_kicad
TARGETS = [pytest.param(10, marks=pytest.mark.kicad_min_major(10), id="t10"), pytest.param(9, id="t9")]


@pytest.mark.parametrize("target", TARGETS)
def test_pathprop(target: int) -> None:
    expected = "present" if major() >= 10 else "load"
    assert run(f"build-pathprop-t{target}") == expected


@pytest.mark.parametrize("target", TARGETS)
def test_libtable(target: int) -> None:
    outcome = run(f"build-libtable-t{target}")
    print(f"KiCad {major()}: build-libtable-t{target} {outcome}")
    if major() >= 10:
        assert outcome == "equal"


@pytest.mark.parametrize("target", TARGETS)
def test_baseline(target: int) -> None:
    assert run(f"build-baseline-t{target}") == "absent"
    assert run(f"build-offboard-t{target}") in ("present", "absent")
    clean, moved = bc.violation_types(target, False), bc.violation_types(target, True)
    print(f"KiCad {major()}: clean {clean}, offboard {moved}")
