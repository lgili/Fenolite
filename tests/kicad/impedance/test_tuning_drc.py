# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""KiCad 10 tuning profiles judged by ``pcb drc`` (capability kicad-oracle, "Impedance targets pass the
oracle", scenario "Profiles on 10.0.6"; hypothesis H-K-PRO-TUNING-DRC; change c0105).

Each case runs the bench of ``_zbench`` once per session; a run whose scoped canary does not fire fails.
The outcomes are those the design of c0105 measured on 10.0.6; ``pro-tuning-gap-clearance-rule`` is
printed and recorded either way. The probes join ``_probes.PROBES`` in the commit that records them.
"""

from __future__ import annotations

import _rulecases as rc
import _zbench as zb
import pytest

pytestmark = pytest.mark.needs_kicad


@pytest.fixture(autouse=True)
def ten_only() -> None:
    if rc.major() != 10:
        pytest.skip("tuning profiles exist in KiCad 10 only")


@pytest.mark.parametrize("probe", sorted(zb.PROFILE_OUTCOMES))
def test_profile_case(probe: str) -> None:
    function, _majors = zb.tuning_probes()[probe]
    found = function()
    assert found != "inconclusive", "rules file not loaded: the canary violation is absent from a DRC report"
    assert found == zb.PROFILE_OUTCOMES[probe], probe


def test_gap_clearance_under_a_rule_is_recorded() -> None:
    function, _majors = zb.tuning_probes()["pro-tuning-gap-clearance-rule"]
    found = function()
    print("pro-tuning-gap-clearance-rule:", found, zb.dump(zb.profile_run("gap-clearance-rule", "ignore")))
    assert found in ("present", "absent")
