# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The recorded KiCad behaviours of change c0115 (capability board-analyses, "Power and insulation KiCad
probes"; scenario "Probes recorded"). Supporting data: a probe fails only when it is missing.

Run on KiCad 10. ``analysis-neck-plain`` and ``insulation-layers`` are also registered for major 9, where
``test_power_nine.py`` observes them on the benches written for target 9.
"""

from __future__ import annotations

import _powerbench
import pytest
from _boards import census
from _probes import PROBES, major, run, runner

pytestmark = [pytest.mark.needs_kicad, pytest.mark.kicad_min_major(10)]
OUTCOMES = ("equal", "different", "absent")


@pytest.mark.parametrize("name", _powerbench.BENCHES)
def test_probe_recorded(name: str) -> None:
    probe = _powerbench.PROBE_IDS[name]
    assert probe in PROBES and PROBES[probe].majors == _powerbench.MAJORS[name]
    assert run(probe) in OUTCOMES


@pytest.mark.parametrize("name", _powerbench.BENCHES)
def test_probe_observation(name: str) -> None:
    """What KiCad reported on the bench, printed (``-rA``) and written to the census file when one is
    named."""
    seen = _powerbench.observe(runner(), name)
    census("analysis", f"power-{name}-{major()}", seen)
    print(name, seen, _powerbench.outcome(name, seen))
    assert _powerbench.outcome(name, seen) in OUTCOMES
