# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Net-like interfaces, whole interfaces joined by ``connect`` and the compatibility table (capability
design-dsl, "Net-like interfaces", "Connecting whole interfaces" and "Interface compatibility"; change
c0252)."""

from __future__ import annotations

from typing import Any

import pytest
from _sensor_rails import sensor_devices

from fenolite.dsl import SPI, UART, Design, DslError, Ground, Net, Rail, block, connect, to_model

R = "Fenolite:Resistor"
FP = "Fenolite:Chip_0603"


def nets(design: Design) -> dict[str, set[tuple[str, str]]]:
    model = to_model(design)
    paths = {c.id: c.properties["fenolite.path"] for c in model.circuit.components}
    return {n.name: {(paths[m.component_id], m.pin) for m in n.members} for n in model.circuit.nets}


def test_rail_joined_to_a_pin() -> None:
    d = Design("t")
    v12 = d.rail("V12")
    j1 = d.part("J1", "Fenolite:Connector_2", footprint="Fenolite:Header_1x2_P2.54")
    connect(v12, j1[1])
    assert nets(d)["V12"] == {("J1", "1")}


def _design() -> tuple[Design, Any, Any]:
    d = Design("t")
    d.devices(*sensor_devices())
    mcu = d.part("U2", device="Example:MCU_SO8")
    sen = d.part("U3", device="Example:SENSOR_I2C")
    return d, mcu, sen


def test_two_i2c_ports() -> None:
    from fenolite.dsl import I2C

    d, mcu, sen = _design()
    connect(I2C(Net("SDA"), Net("SCL")), mcu.i2c1, sen.i2c)
    found = nets(d)
    assert found["SDA"] == {("U2", "PB7"), ("U3", "SDA")}
    assert found["SCL"] == {("U2", "PB6"), ("U3", "SCL")}


def test_two_i2c_ports_name_their_nets_after_a_port() -> None:
    d, mcu, sen = _design()
    connect(mcu.i2c1, sen.i2c)
    found = nets(d)
    assert found["U2/i2c1.sda"] == {("U2", "PB7"), ("U3", "SDA")}
    assert found["U2/i2c1.scl"] == {("U2", "PB6"), ("U3", "SCL")}


@block
def link(b: Any) -> None:
    port = b.port("UART", UART)
    r_tx = b.part("R_TX", R, footprint=FP)
    r_rx = b.part("R_RX", R, footprint=FP)
    connect(port.tx, r_tx[1])
    connect(port.rx, r_rx[1])


def test_uart_ports_cross() -> None:
    d = Design("t")
    u1 = d.use(link, "u1")
    u2 = d.use(link, "u2")
    connect(u1.UART, u2.UART)
    found = nets(d)
    assert {("u1/R_TX", "1"), ("u2/R_RX", "1")} in found.values()
    assert {("u1/R_RX", "1"), ("u2/R_TX", "1")} in found.values()
    with pytest.raises(DslError, match="attach"):
        connect(UART(Net("TX"), Net("RX")), u1.UART)


@block
def buck(b: Any) -> None:
    vin = b.port("VIN", Rail, direction="in")
    r = b.part("R", R, footprint=FP)
    connect(vin, r[1])


def test_ground_on_a_rail_refused() -> None:
    d = Design("t")
    buck1 = d.use(buck, "buck1")
    gnd = d.ground("GND")
    with pytest.raises(DslError, match=r"ground `GND` to power port `buck1/VIN`"):
        connect(gnd, buck1.VIN)
    assert gnd.members["gnd"].group is None  # nothing was connected


def test_rail_joins_two_device_ports() -> None:
    """Scenario "Rail joined to two device ports"."""
    d, mcu, sen = _design()
    v33 = d.rail("3V3")
    connect(v33, mcu.vdd, sen.vdd)
    model = to_model(d)
    found = nets(d)
    assert found["3V3"] == {("U2", "VDD"), ("U2", "VDDA"), ("U3", "VDD")}
    net_id = next(n.id for n in model.circuit.nets if n.name == "3V3")
    vdd = [p for p in model.circuit.ports if p.name == "vdd"]
    assert len(vdd) == 2 and all(p.members["hv"] == net_id for p in vdd)


def test_incompatible_pairs_refused() -> None:
    d, mcu, _ = _design()
    gnd = Ground(Net("GND"))
    with pytest.raises(DslError, match="cannot connect"):
        connect(gnd, mcu.vdd)
    with pytest.raises(DslError, match="cannot connect power `A/B` to i2c port `U2/i2c1`"):
        connect(Rail(Net("A"), Net("B")), mcu.i2c1)


@block
def flash(b: Any, *, selects: int = 1) -> None:
    b.port("SPI", SPI, selects=selects)


def test_missing_required_member_refused() -> None:
    d = Design("t")
    one, two = d.use(flash, "f1"), d.use(flash, "f2", selects=2)
    with pytest.raises(DslError, match=r"no member cs1.*same chip selects"):
        connect(one.SPI, two.SPI)
