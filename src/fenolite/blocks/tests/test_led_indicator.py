# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Plain LED tests: every electrical number is supplied by the caller."""

from fractions import Fraction

from fenolite.blocks import led_indicator
from fenolite.blocks.tests._support import bench, high, low, part, refused
from fenolite.dsl import Design, DslError, amp, volt
from fenolite.testing import instantiate


def test_default_indicator() -> None:
    with instantiate(led_indicator, vf=volt(2).pct(10), led_current_max=amp("20m")) as design:
        assert part(design, "r").value == "649R"
        rows = design.requirements("dut/expect*")
        assert all(row.status == "pass" for row in rows)
        assert Fraction("0.001426413") <= low(rows[0].value)
        assert high(rows[0].value) <= Fraction("0.002591400")
        assert high(rows[-1].limit) < Fraction("0.004314680")
        light = design.ref("dut/led")
        assert design.connected(light[2], design.net("dut/LO"))


def test_pin_cannot_drive() -> None:
    refused(
        lambda: instantiate(
            led_indicator, vf=volt(2).pct(10), led_current_max=amp("20m"), source_limit=amp("1m")
        ),
        "circuit.expect-failed",
    )


def test_forward_voltage_stated() -> None:
    try:
        Design("missing_led_data").use(led_indicator, "dut")
    except DslError as error:
        assert "vf" in str(error) and "led" in str(error)
    else:
        raise AssertionError("forward voltage was silently invented")


def test_led_data_from_authored_device() -> None:
    # Authored illustrative electrical data, not specifications of a real LED.
    text = """schema = "fenolite.device.v1"
id = "Example:TestLED"
version = "1.0.0"
summary = "Illustrative LED used only by the plain test"
category = "Device"
licence = "CC0-1.0"
evidence = "UNVERIFIED"
sources = []
symbol = "Fenolite:LED"
footprint = "Fenolite:LED0603_Kingbright_APT1608SURCK"
ref_prefix = "D"
value = "TEST"
ends = ["A", "K"]
[pins.A]
map = { "1" = "2" }
[pins.K]
map = { "2" = "1" }
[ratings]
voltage = { operating = { min = "1.8V", max = "2.2V" } }
current = { abs_max = "20mA" }
"""
    with bench("led_indicator", 'led="Example:TestLED"', device_text=text) as design:
        assert all(row.status == "pass" for row in design.requirements("dut/expect*"))
