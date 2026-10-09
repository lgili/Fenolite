# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Meanders in KiCad (capability kicad-oracle, "Meanders pass the oracle"; hypothesis H-K-NETLEN-MEANDER;
change c0106). Three design scripts of ``tests/_meanderdesign.py`` are built by ``fenolite build`` for the
running major: a segment along an axis meandered to a target, a pair on four layers whose other track
changes layer through two vias, matched with ``match``, and a segment at 30° meandered to a target. Each
board carries the scoped canary and the two length rules around the target of its meandered net; the pair
also carries a skew rule of 1 µm judged within the pair."""

from __future__ import annotations

import _lengthcases as lc
import pytest
from _probes import major, run, runner

pytestmark = pytest.mark.needs_kicad


@pytest.mark.parametrize("case", sorted(lc.MEANDER_CASES))
def test_meander(case: str) -> None:
    found = lc.meander_run(runner(), case)
    if not found.canary:
        pytest.fail("rules file not loaded: the canary violation is absent from a DRC report", pytrace=False)
    print(f"{case} {major()}: target {found.target} nm, total {found.total} nm")
    assert abs(found.total - found.target) <= 10, "the meandered net is not within 10 nm of its target"
    assert found.below, "KiCad does not report the net with the rule 1 µm below the target"
    assert not found.above, "KiCad reports the net with the rule 1 µm above the target"
    assert not found.extra, f"the meander adds violations: {found.extra}"
    assert found.skew == 0, "the pair has a skew violation at 1 µm"
    assert run(f"length-meander-{case}") == "equal"
