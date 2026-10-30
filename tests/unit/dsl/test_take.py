# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""``part.take`` (capability pin-assignment, "Taking an interface in the DSL"; change c0257). The devices are
the illustrative records of ``examples/pins/devices``."""

from __future__ import annotations

from pathlib import Path

import pytest

from fenolite.catalog.devices import parse_device
from fenolite.dsl import I2C, SPI, UART, Design, DslError, Net, connect, mm, pull_up, to_model
from fenolite.dsl.take import TakenInterface, apply_choices, design_takes, fixed_functions, pending
from fenolite.model.library import DeviceDef

DEVICES = Path(__file__).resolve().parents[3] / "examples" / "pins" / "devices"


def devices() -> list[DeviceDef]:
    return [parse_device(p.read_text(encoding="utf-8"), file=p.name) for p in sorted(DEVICES.glob("*.toml"))]


def design() -> Design:
    made = Design("t")
    made.devices(*devices())
    return made


def test_connect() -> None:
    """Scenario "Take and connect": the take key, the sensor pins on the role nets, no MCU pin yet."""
    d = design()
    mcu = d.part(name="mcu", device="Example:MCU_QFN32")
    sen = d.part(name="sen", device="Example:SENSOR_I2C")
    i2c = mcu.take(I2C)
    connect(i2c, sen.i2c)
    assert isinstance(i2c, TakenInterface) and i2c.take_key == "i2c#0" and i2c.key == "mcu/i2c#0"
    assert sen.connections["SDA"].group is i2c.members["sda"].group
    assert sen.connections["SCL"].group is i2c.members["scl"].group
    assert mcu.connections == {}
    assert i2c.members["sda"].name == "mcu/i2c#0/sda"


def test_take_keys_options_and_pins() -> None:
    d = design()
    mcu = d.part(name="mcu", device="Example:MCU_QFN32")
    first = mcu.take(I2C)
    debug = mcu.take(UART, option="UART2", name="debug")
    second = mcu.take("i2c", pins={"sda": mcu.PB9})
    adc = mcu.take("pin", option="ADC")
    assert [t.take_key for t in design_takes(d)] == ["i2c#0", "debug", "i2c#1", "pin#0"]
    assert (first.option, debug.option, dict(second.pins)) == (None, "UART2", {"sda": "PB9"})
    assert adc.kind == "pin" and list(adc.members) == ["io"]
    connect(Net("SENSE"), adc)  # a single-pin take is net-like


@pytest.mark.parametrize(
    ("call", "words"),
    [
        (lambda p: p.take(SPI, name="debug"), "already named"),
        (lambda p: p.take("usb2"), "offers no usb2 option"),
        (lambda p: p.take(int), "interface class"),
        (lambda p: p.take(I2C, pins={"tx": "PB7"}), "roles scl, sda"),
        (lambda p: p.take(I2C, option=""), "option is the name"),
        (lambda p: p.take(I2C, name="bad name"), "must match"),
    ],
)
def test_refused_at_the_call(call: object, words: str) -> None:
    d = design()
    mcu = d.part(name="mcu", device="Example:MCU_QFN32")
    mcu.take(UART, name="debug")
    with pytest.raises(DslError, match=words):
        call(mcu)  # type: ignore[operator]


def test_part_without_device_or_option_refused() -> None:
    d = design()
    plain = d.part("R1", "Device:R", "Resistor_SMD:R_0603_1608Metric", "1k")
    with pytest.raises(DslError, match="device"):
        plain.take(I2C)
    sen = d.part(name="sen", device="Example:SENSOR_I2C")
    with pytest.raises(DslError, match="offers no i2c option"):
        sen.take(I2C)


def test_pending_takes_solved_by_to_model_and_applied() -> None:
    """``to_model`` solves takes never applied against an empty lock, as it assigns refs."""
    d = design()
    d.board(mm(10), mm(10))
    mcu = d.part("U1", device="Example:MCU_QFN32")
    i2c = mcu.take(I2C)
    r1 = d.part("R1", device="Fenolite:R_0603", value="4k7")
    r2 = d.part("R2", device="Fenolite:R_0603", value="4k7")
    pull_up(i2c, Net("3V3"), r1, r2)  # helpers work before the solve
    connect(Net("RESET"), mcu.PB6)
    assert fixed_functions(mcu) == {"PB6"}
    assert pending(d) == ["U1/i2c#0"]
    model = to_model(d)
    assert pending(d) == [] and mcu.connections["PB9"] is i2c.members["sda"]
    sda = next(net for net in model.circuit.nets if net.name == "U1/i2c#0/sda")
    assert {m.pin for m in sda.members} == {"PB9", "P1"}


def test_apply_choices() -> None:
    d = design()
    mcu = d.part("U1", device="Example:MCU_QFN32")
    i2c = mcu.take(I2C)
    other = mcu.take(I2C)
    apply_choices(d, {"U1/i2c#0": {"scl": "PB10", "sda": "PB11"}})
    assert mcu.connections["PB11"] is i2c.members["sda"] and other.choice is None and pending(d) == []
