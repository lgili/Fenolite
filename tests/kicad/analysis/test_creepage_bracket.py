# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The recorded KiCad bracket of Fenolite's creepage (``H-K-AN-CREEP``; capability board-analyses, "KiCad
creepage bracket is recorded"; change c0047).

KiCad 10 has a ``creepage`` rule constraint (S-0272). On each bench a rule 50 µm below Fenolite's value and
one 50 µm above are run through ``pcb drc``. The outcomes are supporting data: they gate nothing and raise
no label. ``tests/kicad/test_probe_results.py`` pins them per version; this test fails only when a probe is
missing or gives a value outside the three it may give.
"""

from __future__ import annotations

import _creepbench
import pytest
from _boards import census
from _probes import PROBES, major, run, runner

pytestmark = [pytest.mark.needs_kicad, pytest.mark.kicad_min_major(10)]
OUTCOMES = ("equal", "different", "absent")


@pytest.mark.parametrize("name", _creepbench.BENCHES)
def test_bracket_recorded(name: str) -> None:
    probe = _creepbench.probe_id(name)
    assert probe in PROBES and PROBES[probe].majors == (10,)
    assert run(probe) in OUTCOMES


@pytest.mark.parametrize("name", _creepbench.BENCHES)
def test_bracket_observation(name: str) -> None:
    """What KiCad reported below and above the value, written to the census file when one is named."""
    seen = _creepbench.observe(runner(), name)
    census("analysis", f"creepage-{name}-{major()}", seen)
    assert seen["fenolite_nm"] in (11_000_000, 5_100_000)
