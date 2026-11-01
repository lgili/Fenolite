# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Device interface ports in the DSL and in the model (capability design-dsl, "Device interface ports in the
DSL"; design-model, "Device ports in the model"; change c0252)."""

from __future__ import annotations

import pytest
from _sensor_rails import sensor_devices

from fenolite.dsl import Design, DslError, Net, connect, to_model
from fenolite.dsl.convert import key_id
from fenolite.model.circuit import Decimal10


def test_device_port_recorded() -> None:
    d = Design("t")
    d.devices(*sensor_devices())
    sen = d.part("U3", device="Example:SENSOR_I2C")
    connect(Net("3V3"), sen.VDD)  # by function: no port reached
    model = to_model(d)
    vdd = next(p for p in model.circuit.ports if p.name == "vdd")
    assert vdd.owner == key_id("component", "U3") and vdd.id == key_id("port", "U3", "vdd")
    assert (vdd.kind, vdd.direction, vdd.evidence) == ("power", "in", "UNVERIFIED")
    assert vdd.members == {"hv": key_id("net", "3V3")}
    voltage = vdd.params["voltage"]
    assert (voltage.low, voltage.high) == (Decimal10(171, -2), Decimal10(36, -1))
    i2c = next(p for p in model.circuit.ports if p.name == "i2c")
    assert i2c.requires == ("pullup", "supply") and i2c.reference == key_id("port", "U3", "vdd")


def test_device_port_split() -> None:
    d = Design("t")
    d.devices(*sensor_devices())
    mcu = d.part("U2", device="Example:MCU_SO8")
    connect(Net("3V3"), mcu.VDD)
    connect(Net("3V3A"), mcu.VDDA)
    vdd = next(p for p in to_model(d).circuit.ports if p.name == "vdd")
    assert "hv" not in vdd.members
    assert vdd.split == {"hv": tuple(sorted((key_id("net", "3V3"), key_id("net", "3V3A"))))}


def test_device_port_access() -> None:
    d = Design("t")
    d.devices(*sensor_devices())
    mcu = d.part("U2", device="Example:MCU_SO8")
    assert mcu.port("vdd") is mcu.vdd and mcu.vdd.kind == "power"
    with pytest.raises(DslError, match="its ports: i2c1, pa3, vdd"):
        mcu.port("vcc")
    v33 = Net("3V3")
    connect(v33, mcu.vdd)
    connect(v33, mcu.VDDA)  # a pin of a reached port stays on the port's net
    nets = {n.name: {m.pin for m in n.members} for n in to_model(d).circuit.nets}
    assert nets["3V3"] == {"VDD", "VDDA"}
