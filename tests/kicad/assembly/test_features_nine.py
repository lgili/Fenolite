# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The KiCad 9 half of the probes of change c0118 (tasks 1.2, 1.3 and 4.4): every probe of
``_featurebench.feature_probes`` that is stated for both majors, run on ``kicad-cli`` 9.0.9 and compared
with the outcome that 10.0.6 recorded and ``design.md`` states.

The probes are registered for major 10 only (``_featurebench.MAJORS``), so
``tests/kicad/test_probe_results.py`` asks nothing of ``9.0.9.json``. This file prints each outcome
(``-rA``) and writes it to the census file when one is named; once a run has shown them, ``MAJORS``
becomes ``(9, 10)`` and the outcomes go into ``9.0.9.json``.
"""

from __future__ import annotations

import _featurebench as fb
import _probes
import pytest
from _boards import census

pytestmark = pytest.mark.needs_kicad
EXPECTED = {
    **{f"pad-fabprop-{value}": "equal" for value in fb.FUNCTIONS},
    "pad-fabprop-outputs": "equal",
    "pad-fabprop-padstack": "equal",
    "pad-fabprop-lib-mismatch": "present",
    "pad-fabprop-lib-same": "absent",
    "asm-fiducial-drc": "absent",
    "asm-fiducial-mask": "equal",
    "asm-fiducial-d356": "equal",
    "asm-keepout-track": "present",
    "asm-testpoint-d356": "equal",
}
"""The outcomes recorded on 10.0.6 for the probes stated for both majors (``design.md``)."""


def _both_majors() -> list[str]:
    probes = fb.feature_probes(_probes.runner)
    return sorted(pid for pid in probes if pid not in fb.TEN_ONLY)


def test_expected_names_every_probe_of_both_majors() -> None:
    """The table above covers exactly the probes that are not of KiCad 10 alone."""
    assert sorted(EXPECTED) == _both_majors()


@pytest.mark.parametrize("probe", sorted(EXPECTED))
def test_nine_observation(probe: str) -> None:
    if _probes.major() != 9:
        pytest.skip("the 9.0.9 half of the c0118 probes runs on KiCad 9")
    function, _ = fb.feature_probes(_probes.runner)[probe]
    outcome = function()
    census("assembly", f"{probe}-9", outcome)
    print(probe, outcome, "expected", EXPECTED[probe])
    assert outcome in _probes.OUTCOMES
