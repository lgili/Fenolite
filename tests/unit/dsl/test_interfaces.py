# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Interfaces in the DSL (capability design-dsl, "Interfaces in the DSL"; change c0011)."""

from __future__ import annotations

import pytest

from fenolite.dsl import Design, DiffPair, DslError, Interface, Net, Power, to_model
from fenolite.dsl.convert import key_id


def test_power_interface() -> None:
    d, vin, gnd = Design("t"), Net("VIN"), Net("GND")
    d.add(Power(vin, gnd))
    (itf,) = to_model(d).circuit.interfaces
    assert (itf.name, itf.kind) == ("VIN/GND", "power")
    assert itf.members == {"hv": key_id("net", "VIN"), "lv": key_id("net", "GND")}
    assert set(d.nets) == {"VIN", "GND"}


def test_diff_pair_and_names() -> None:
    d = Design("t")
    d.add(DiffPair(Net("USB_P"), Net("USB_N")), Power(Net("A"), Net("B"), name="rail"))
    kinds = {i.name: i.kind for i in to_model(d).circuit.interfaces}
    assert kinds == {"USB_P/USB_N": "diff_pair", "rail": "power"}


def test_interface_checks() -> None:
    d = Design("t")
    d.add(Interface("bus", "i2c", {"sda": Net("SDA")}))
    with pytest.raises(DslError):
        d.add(Interface("bus", "i2c", {"scl": Net("SCL")}))
    with pytest.raises(DslError):
        Interface("x", "i2c", {"sda": "SDA"})  # type: ignore[dict-item]
