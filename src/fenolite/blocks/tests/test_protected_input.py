# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Plain tests use only the authored, UNVERIFIED Example device figures."""

from fractions import Fraction

from fenolite.blocks import protected_input
from fenolite.blocks.tests._support import bench, high, refused
from fenolite.dsl import Design, DslError

GOOD = (
    'protection="Example:IllustrativeTVS", clamp=volt("9.2").max(), abs_max=volt("3.6"), '
    'r_series=ohm("1.5k"), inject_max=amp("5m"), hold=volt("3.6")'
)


def test_injected_current() -> None:
    with bench("protected_input") as design:
        rows = design.requirements("dut/expect*")
        assert all(row.status == "pass" for row in rows)
        assert high(rows[1].limit) <= Fraction("0.003771044")
        assert high(rows[1].limit) >= Fraction("0.003771043")
    with bench("protected_input", GOOD.replace('ohm("1.5k")', 'ohm("1k")')) as design:
        row = design.requirements("dut/expect#2")[0]
        assert row.status == "unsure"
        assert Fraction("0.005656565") <= high(row.limit) <= Fraction("0.005656566")
        assert len(design.findings("circuit.expect-unsure")) == 1


def test_clamp_above_maximum() -> None:
    with bench(
        "protected_input",
        'protection="Example:IllustrativeTVS", clamp=volt("9.2").max(), abs_max=volt("3.6")',
    ) as design:
        assert design.requirements("dut/expect#2")[0].status == "unsure"
        assert len(design.findings("circuit.expect-unsure")) == 1


def test_working_voltage() -> None:
    refused(lambda: bench("protected_input", GOOD + ", signal=volt(6)"), "circuit.expect-failed")


def test_required_typed_metadata() -> None:
    for params in ({}, {"protection": "x", "clamp": "9.2V", "abs_max": "3.6V"}):
        try:
            Design("bad_protection").use(protected_input, "dut", **params)
        except DslError:
            pass
        else:
            raise AssertionError("required typed data were not checked")
