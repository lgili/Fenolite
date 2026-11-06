# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""A negative ``silk_clearance`` minimum is read and lets silkscreen overlap by up to its size (hypothesis
H-K-DRU-NEG-SILK; change c0427). An Altium silk to silk rule may hold one, and ``design.rules.rule()``
takes it. The bench is two ``Mini_R_0603`` copies whose facing silkscreen lines overlap by 0.05 mm: under a
board-wide rule of minimum 0 KiCad reports the overlap; under one of minimum -0.1 mm it reports none. The
scoped canary proves that the rules file was loaded both times (a rule KiCad cannot read disables them all,
H-K-TOK-RULES-SILENT)."""

from __future__ import annotations

from functools import cache

import _kindcases as kc
import _rulebench as rb
import pytest

pytestmark = pytest.mark.needs_kicad

OVERLAP = -50_000
TYPES = frozenset({"silk_overlap"})


@cache
def _bench() -> rb.Bench:
    made = rb.builder()
    made.silk_pair("silk_negative", ("SN1", "SN2"), gap=OVERLAP, target=kc.target())
    return made.build()


def _overlap(minimum: int) -> bool:
    result = kc.run(_bench(), kc.rules_text(kc.rule_text("fenolite_0_silk", "silk_clearance", minimum)))
    rb.require_canary(result.report, result.bench)
    return result.any_of(("SN1", "SN2"), TYPES)


def test_a_negative_silk_clearance_lets_silkscreen_overlap() -> None:
    assert _overlap(0), "the overlap is not reported under a minimum of 0"
    assert not _overlap(-100_000), "the overlap is reported under a minimum of -0.1 mm"
