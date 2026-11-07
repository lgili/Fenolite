# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Plain self-tests for the first-order RC low-pass."""

from fractions import Fraction

from fenolite.blocks import rc_lowpass
from fenolite.blocks.tests._support import high, low, part, refused
from fenolite.dsl import hertz
from fenolite.testing import instantiate


def test_default_filter() -> None:
    with instantiate(rc_lowpass) as design:
        assert part(design, "filter_R").value == "1k58"
        assert part(design, "filter_C").value == "100nF"
        rows = design.requirements("dut/expect*")
        assert all(r.status == "pass" for r in rows)
        assert Fraction("906.669") < low(rows[0].value) < Fraction("906.670")
        assert Fraction("1130.537") < high(rows[0].value) < Fraction("1130.539")


def test_narrow_window() -> None:
    refused(lambda: instantiate(rc_lowpass, corner=hertz("1k").pct(10)), "gen.unachievable")


def test_capacitor_may_be_chosen() -> None:
    with instantiate(rc_lowpass, c=None) as design:
        assert all(row.status == "pass" for row in design.requirements("dut/expect*"))
