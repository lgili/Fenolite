# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""How KiCad's DRC counts coupled length (capability kicad-oracle, "Pair coupling in KiCad's DRC is
probed"; hypothesis H-K-DRU-PAIRCOUPLE; change c0110): a pair 0.15 mm apart and one 1.07 mm apart of script
copper, judged with a gap rule, an uncoupled rule, both and none. Runs where ``kicad-cli`` is (the local
10.0.6, the pinned 9.0.9 image, and the CI jobs that have it)."""

from __future__ import annotations

import _couplebench as cb
import _rulebench as rb
import pytest

pytestmark = pytest.mark.needs_kicad


@pytest.mark.parametrize("case", cb.CASES)
def test_four_rules_files(case: str) -> None:
    """Scenario "Four rules files": the gap rule alone reports only the gap of the wide pair; the uncoupled
    rule alone reports at most the wide pair, below its routed length; both report the wide pair as
    uncoupled over its whole length; no rule reports nothing."""
    result = cb.judged(case)
    rb.require_canary(result.report, result.bench)
    assert cb.holds(case), (case, cb.uncoupled_length(result, "CA"), cb.uncoupled_length(result, "CB"))
    assert cb.probe(case) == "present"
