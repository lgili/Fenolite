# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Rule order in KiCad (capability rules-model, "Lowered rules follow priority"; hypothesis
H-K-DRU-ORDER; change c0018): two tracks with a 2 mm gap and ``overlap.kicad_dru`` (1 mm, then 3 mm)."""

from __future__ import annotations

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
