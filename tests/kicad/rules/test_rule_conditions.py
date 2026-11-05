# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Each selector op in KiCad (capability rules-model, "Each op selects its items in KiCad"; hypotheses
H-K-DRU-COND and H-K-DRU-GLOB; change c0018). One bench per op with a probe pair and a control pair 4 mm
apart and a 5 mm rule; ``netclass`` compares ``'Default'`` with an absent class in two runs. Letter case
is recorded, not asserted."""

from __future__ import annotations

import _rulebench as rb
import _rulecases as rc
import pytest
from _probes import run

from fenolite.model.rules import NO_NET

pytestmark = pytest.mark.needs_kicad


@pytest.mark.parametrize("key", rc.CONDITION_KEYS)
def test_condition(key: str) -> None:
    runs = rc.condition(key)
    for result in runs:
        rb.require_canary(result.report, result.bench)
    if key == "netclass":
        hit, miss = runs
        assert hit.between("probe") and not miss.between("probe")
    else:
        (only,) = runs
        assert only.between("probe", None), f"{key}: the probe pair has no violation"
        assert not only.between("control", None), f"{key}: the control pair has a violation"
    assert run(f"dru-cond-{key}") == "present"


def test_no_net() -> None:
    """``A.NetName == ''`` selects the items without a net (change c0409, ``H-K-DRU-NONET``): a netless
    track 4 mm from a netted one violates a 5 mm rule, a netted pair as far apart does not."""
    made = rb.builder()
    made.pair("probe", "", "NN1")
    made.pair("control", "NN2", "NN3")
    (result,) = (rc.run(made.build(), rc.lowered(rc.rule(a=NO_NET))),)
    rb.require_canary(result.report, result.bench)
    assert result.between("probe", None), "the netless track has no violation"
    assert not result.between("control", None), "the netted pair has a violation"


def test_letter_case_recorded() -> None:
    (result,) = rc.condition("case")
    rb.require_canary(result.report, result.bench)
    assert run("dru-cond-case") in ("present", "absent")
