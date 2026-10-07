# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The net names KiCad takes as a differential pair (capability kicad-oracle, "Differential pair names are
probed"; hypothesis H-K-DIFFPAIR-NAMES; change c0073; and H-K-DIFFPAIR-NAMES-2 for a tail of digits and
underscores, change c0104). ``build.diff-pair-name`` and ``model.pairs`` follow these outcomes."""

from __future__ import annotations

import _paircases as pc
import _rulebench as rb
import pytest
from _probes import run

from fenolite.lens.build import is_pair
from fenolite.model.pairs import pair_base
from fenolite.model.rules import RuleSubject, Selector

pytestmark = pytest.mark.needs_kicad


@pytest.mark.parametrize("case", sorted(pc.CASES))
def test_pair_names(case: str) -> None:
    result = pc.pairs()
    rb.require_canary(result.report, result.bench)
    expected = case in pc.PAIRED
    assert pc.recognised(result, case) is expected, f"{case}: KiCad and the expected outcome differ"
    assert run(f"dru-diffpair-{case}") == ("present" if expected else "absent")
    _, positive, negative = pc.CASES[case]
    names_pair = case in pc.NAMES_PAIR
    assert is_pair(positive, negative) is names_pair, f"{case}: build.diff-pair-name does not follow KiCad"
    base = pair_base(positive, negative)
    if expected:
        assert base is not None and Selector("diff_pair", pc.CASES[case][0]).matches(
            RuleSubject("track", net=positive, diff_pair=base)
        ), f"{case}: the model's base {base!r} is not selected by the rule's base"
    elif names_pair:
        assert base is not None and not Selector("diff_pair", pc.CASES[case][0]).matches(
            RuleSubject("track", net=positive, diff_pair=base)
        ), f"{case}: the model selects a pair that KiCad does not"
