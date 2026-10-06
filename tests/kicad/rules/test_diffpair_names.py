# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The net names KiCad takes as a differential pair (capability kicad-oracle, "Differential pair names are
probed"; hypothesis H-K-DIFFPAIR-NAMES; change c0073). ``build.diff-pair-name`` follows these outcomes."""

from __future__ import annotations

import _paircases as pc
import _rulebench as rb
import pytest
from _probes import run

from fenolite.lens.build import is_pair

pytestmark = pytest.mark.needs_kicad


@pytest.mark.parametrize("case", sorted(pc.CASES))
def test_pair_names(case: str) -> None:
    result = pc.pairs()
    rb.require_canary(result.report, result.bench)
    expected = case in pc.PAIRED
    assert pc.recognised(result, case) is expected, f"{case}: KiCad and the expected outcome differ"
    assert run(f"dru-diffpair-{case}") == ("present" if expected else "absent")
    _, positive, negative = pc.CASES[case]
    assert is_pair(positive, negative) is expected, f"{case}: build.diff-pair-name does not follow KiCad"
