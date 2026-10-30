# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Interface ports of a device record (capability fenolite-component-catalog, "Interface ports of a device"
and "Refused device interfaces"; change c0252). The records are authored for Fenolite and illustrative."""

from __future__ import annotations

import pytest

from fenolite.catalog.devices import DeviceFormatError, device_text, parse_device
from fenolite.model.circuit import Decimal10

HEAD = """schema = "fenolite.device.v0"
id = "Proj:SENSOR"
summary = "Illustrative sensor"
symbol = "Proj:Sensor"
footprint = "Fenolite:SOT23_6_TI_DBV0006A"
ref_prefix = "U"
evidence = "UNVERIFIED"

[pins]
VDD = "1"
GND = "2"
SDA = "3"
SCL = "4"
INT = "5"
"""
VDD = """
[[interfaces]]
name = "vdd"
kind = "power"
direction = "in"
members = { hv = ["VDD"], lv = ["GND"] }
voltage = { min = "1.71V", max = "3.6V" }
current = { max = "12mA" }
"""
I2C = """
[[interfaces]]
name = "i2c1"
kind = "i2c"
direction = "inout"
members = { sda = ["SDA"], scl = ["SCL"] }
reference = "vdd"
requires = ["pullup", "supply"]
input_high_min = "1.3V"
output_low_max = "0.4V"
evidence = "INFERRED"
"""


def test_valid_ports_load() -> None:
    device = parse_device(HEAD + VDD + I2C, file="sensor.toml")
    i2c, vdd = device.interfaces
    assert (vdd.name, vdd.kind, vdd.direction, vdd.members) == (
        "vdd",
        "power",
        "in",
        {"hv": ("VDD",), "lv": ("GND",)},
    )
    assert vdd.params["current"].low == Decimal10(0, 0) and vdd.params["current"].high == Decimal10(12, -3)
    assert vdd.params["voltage"].low == Decimal10(171, -2) and vdd.evidence == "UNVERIFIED"
    assert i2c.reference == "vdd" and i2c.requires == ("pullup", "supply") and i2c.evidence == "INFERRED"
    assert i2c.params["input_high_min"].low == i2c.params["input_high_min"].high == Decimal10(13, -1)
    assert parse_device(device_text(device)) == device


@pytest.mark.parametrize(
    ("extra", "rule"),
    [
        (I2C.replace('scl = ["SCL"]', 'scl = ["SCK"]'), "names no function"),
        (I2C.replace('name = "i2c1"', 'name = "INT"'), "is a function of the device"),
        (I2C.replace('name = "i2c1"', 'name = "place"'), "attribute of Part"),
        (I2C.replace('reference = "vdd"', 'reference = "i2c1"'), "no other power interface"),
        (
            '\n[[interfaces]]\nname = "irq"\nkind = "logic"\ndirection = "out"\nmembers = { io = ["INT"] }\n'
            'current = "1mA"\n',
            "not a key of a logic interface",
        ),
        (
            VDD.replace('name = "vdd"', 'name = "vbus"').replace('direction = "in"', 'direction = "inout"'),
            "not allowed on an inout power interface",
        ),
        (I2C.replace('requires = ["pullup", "supply"]', 'requires = ["chip_select"]'), "not taken by a i2c"),
        (I2C.replace('kind = "i2c"', 'kind = "can"'), "not an interface kind"),
        (I2C.replace('scl = ["SCL"]', 'scl = ["SDA"]'), "also in the member"),
    ],
)
def test_bad_ports_refused(extra: str, rule: str) -> None:
    with pytest.raises(DeviceFormatError) as found:
        parse_device(HEAD + VDD + extra, file="sensor.toml")
    assert found.value.code == "FEN-3004" and rule in str(found.value)
    assert "sensor.toml" in str(found.value) or found.value.file == "sensor.toml"
    assert "interfaces[" in str(found.value)


def test_part_attributes_are_the_dsl_part_attributes() -> None:
    from fenolite.catalog.devices import PART_ATTRIBUTES
    from fenolite.dsl import Design

    part = Design("t").part("R1", "Fenolite:Resistor", footprint="Fenolite:Chip_0603")
    assert {name for name in dir(part) if not name.startswith("_")} == PART_ATTRIBUTES


PIN_THRESHOLDS = HEAD.replace('SDA = "3"\nSCL = "4"\n', "") + (
    'SDA = { pins = ["3"], input_high_min = "1.4V" }\nSCL = { pins = ["4"], input_high_min = "1.3V" }\n'
)


def _port(record: str):  # type: ignore[no-untyped-def]
    from fenolite.dsl import Design, to_model

    device = parse_device(record, file="sensor.toml")
    design = Design("thresholds")
    design.devices(device)
    u1 = design.part("U1", device="Proj:SENSOR")
    u1.port("i2c1")
    (port,) = [p for p in to_model(design).circuit.ports if p.name == "i2c1"]
    return port


def test_a_port_takes_its_pins_thresholds() -> None:
    """Scenario "A port takes its pins' thresholds" (change c0274): a bus port that omits a threshold takes
    the strictest of its member pins' (the highest ``input_high_min``); one it states stays its own."""
    taken = _port(PIN_THRESHOLDS + VDD + I2C.replace('input_high_min = "1.3V"\n', ""))
    assert taken.params["input_high_min"].low == Decimal10(14, -1)
    assert taken.params["input_high_min"].high == Decimal10(14, -1)
    assert taken.params["output_low_max"].high == Decimal10(4, -1)
    own = _port(PIN_THRESHOLDS + VDD + I2C.replace('input_high_min = "1.3V"', 'input_high_min = "1.2V"'))
    assert own.params["input_high_min"].low == Decimal10(12, -1)
