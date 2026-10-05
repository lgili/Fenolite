# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Rule order in KiCad (capability rules-model, "Lowered rules follow priority"; hypothesis
H-K-DRU-ORDER; change c0018): two tracks with a 2 mm gap and ``overlap.kicad_dru`` (1 mm, then 3 mm)."""

from __future__ import annotations

import _kindcases as kc
import _rulebench as rb
import _rulecases as rc
import pytest
from _probes import run

pytestmark = pytest.mark.needs_kicad


def test_later_rule_wins() -> None:
    forward, reverse = rc.order("forward"), rc.order("reverse")
    rb.require_canary(forward.report, forward.bench)
    rb.require_canary(reverse.report, reverse.bench)
    assert forward.between("ord"), "1 mm then 3 mm: the 3 mm rule must govern"
    assert not reverse.between("ord"), "3 mm then 1 mm: the 1 mm rule must govern"
    assert run("dru-order-forward") == "present" and run("dru-order-reverse") == "absent"


def test_later_hole_to_hole_rule_wins() -> None:
    """The same order rule for a new kind (change c0071): two ``hole_to_hole`` rules on one via pair whose
    holes are 0.7 mm apart."""
    forward, reverse = kc.hole_order("forward"), kc.hole_order("reverse")
    for result in (forward, reverse):
        rb.require_canary(result.report, result.bench)
    types = kc.VIOLATION_TYPES["hole_to_hole"]
    assert forward.between("ord", types), "0.5 mm then 1 mm: the 1 mm rule must govern"
    assert not reverse.between("ord", types), "1 mm then 0.5 mm: the 0.5 mm rule must govern"
    assert run("dru-order-hole-forward") == "present" and run("dru-order-hole-reverse") == "absent"
