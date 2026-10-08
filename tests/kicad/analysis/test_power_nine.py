# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The KiCad 9 half of the power and insulation benches of change c0115 (tasks 1.2 and 11.1): what
``pcb drc`` of 9.0.9 reports on the plain neck, written for target 9 with its fill stored (9.0.9 has no
``--refill-zones``), at a ``connection_width`` minimum of 1.95 mm and of 2.05 mm, and on copper of two
nets on two inner layers.

The observations are printed (``-rA``) and written to the census file when one is named; they are not
registered as probes, so ``tests/kicad/test_probe_results.py`` asks nothing of ``9.0.9.json`` until the
outcome is read from a run and the probes take major 9.
"""

from __future__ import annotations

import _powerbench
import pytest
from _boards import census
from _probes import major, runner

pytestmark = pytest.mark.needs_kicad
OUTCOMES = ("equal", "different", "absent")


@pytest.mark.parametrize("name", _powerbench.NINE)
def test_nine_observation(name: str) -> None:
    if major() != 9:
        pytest.skip("the 9.0.9 half of the c0115 benches runs on KiCad 9")
    seen = _powerbench.observe(runner(), name, target=9)
    census("analysis", f"power-{name}-9", seen)
    print(name, seen, _powerbench.outcome(name, seen))
    assert _powerbench.outcome(name, seen) in OUTCOMES


def test_ten_only_benches_refuse_target_nine() -> None:
    """``neck-split`` has no stored fill and ``groove-slot`` and ``creepage-split`` are stated for 10."""
    for name in set(_powerbench.BENCHES) - set(_powerbench.NINE):
        with pytest.raises(ValueError, match="target 10 only"):
            _powerbench.run_drc(runner(), name, target=9)
