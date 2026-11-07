# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""H-G-STARTER-ENCLOSURE: exact corner evaluation against the judged built ranges."""

from fractions import Fraction
from itertools import product

from hypothesis import given, settings
from hypothesis import strategies as st

from fenolite.blocks.tests._support import bench, high, low, part
from fenolite.core.generator_limits import I2C_MODES, LN_7_3, PI, i2c_limits


def ends(component):
    value = component.value_range
    assert value is not None and value.low is not None and value.high is not None
    return value.low.fraction(), value.high.fraction()


def encloses(value, corners):
    assert all(low(value) <= corner <= high(value) for corner in corners)


@settings(max_examples=4, derandomize=True, deadline=None)
@given(st.sampled_from(("1.8", "2.5", "3.3", "5")))
def test_divider_encloses_every_corner(vout):
    with bench("voltage_divider", f"vout=volt({vout!r}).pct(5)") as design:
        top, bot = ends(part(design, "divider_top")), ends(part(design, "divider_bot"))
        rows = design.requirements("dut/expect*")
        rail = Fraction("11.76"), Fraction("12.24")
        encloses(rows[0].value, [v / (1 + t / b) for v, t, b in product(rail, top, bot)])
        encloses(rows[1].limit, [v * v / r for v, r in product(rail, top)])
        encloses(rows[2].limit, [v * v / r for v, r in product(rail, bot)])


@settings(max_examples=3, derandomize=True, deadline=None)
@given(st.sampled_from((20, 30, 40)))
def test_rc_encloses_every_corner(percent):
    with bench(
        "rc_lowpass", f'corner=__import__("fenolite.dsl", fromlist=["hertz"]).hertz("1k").pct({percent})'
    ) as design:
        r, c = ends(part(design, "filter_R")), ends(part(design, "filter_C"))
        row = design.requirements("dut/expect#1")[0]
        encloses(row.value, [1 / (2 * pi * a * b) for pi, a, b in product(PI, r, c)])


@settings(max_examples=3, derandomize=True, deadline=None)
@given(st.sampled_from(("3.3", "4", "5")))
def test_led_encloses_every_corner(drive):
    with bench(
        "led_indicator", f'drive=volt({drive!r}).pct(5), vf=volt(2).pct(10), led_current_max=amp("20m")'
    ) as design:
        resistance = ends(part(design, "r"))
        rail = Fraction(drive) * Fraction(95, 100), Fraction(drive) * Fraction(105, 100)
        vf = Fraction("1.8"), Fraction("2.2")
        rows = design.requirements("dut/expect*")
        encloses(rows[0].value, [(v - f) / r for v, f, r in product(rail, vf, resistance)])
        encloses(rows[-1].limit, [(v - f) ** 2 / r for v, f, r in product(rail, vf, resistance)])


@settings(max_examples=3, derandomize=True, deadline=None)
@given(st.sampled_from(("standard", "fast", "fast-plus")))
def test_i2c_encloses_every_corner(mode):
    with bench("i2c_pullups", f"mode={mode!r}") as design:
        rows = design.requirements("dut/expect*")
        vol, iol, maximum = i2c_limits(mode, Fraction(200, 10**12))
        for index, name in ((0, "r_sda"), (2, "r_scl")):
            resistance = ends(part(design, name))
            encloses(rows[index].value, resistance)
            encloses(rows[index].limit, [(v - vol) / iol for v in (Fraction("3.135"), Fraction("3.465"))])
            assert rows[index].status == rows[index + 1].status == "pass"
            assert resistance[1] <= maximum
            # Both exact enclosure corners of the rise-time factor preserve the upper bound.
            for k, c in product(LN_7_3, (Fraction(10, 10**12), Fraction(200, 10**12))):
                assert resistance[1] * k * c <= I2C_MODES[mode][2]


@settings(max_examples=3, derandomize=True, deadline=None)
@given(st.sampled_from(("1.5k", "2k", "3k01")))
def test_protection_encloses_every_corner(resistance):
    params = (
        'protection="Example:IllustrativeTVS", clamp=volt("9.2").max(), abs_max=volt("3.6"), '
        f'r_series=ohm({resistance!r}), inject_max=amp("5m"), hold=volt("3.6")'
    )
    with bench("protected_input", params) as design:
        r = ends(part(design, "r"))
        row = design.requirements("dut/expect#2")[0]
        assert row.limit is not None
        assert all(
            (v - Fraction("3.6")) / a <= high(row.limit)
            for v, a in product((Fraction(0), Fraction("9.2")), r)
        )
        assert row.status == "pass"
