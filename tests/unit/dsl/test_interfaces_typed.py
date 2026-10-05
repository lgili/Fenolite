# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Typed interfaces (capability design-dsl, "Typed interfaces in the DSL" and "Attaching parts to
interfaces"; change c0073)."""

from __future__ import annotations

import pytest

import fenolite.dsl as dsl
from fenolite.dsl import (
    I2C,
    SPI,
    UART,
    USB2,
    Design,
    DslError,
    Interface,
    Net,
    Part,
    Power,
    no_connect,
    to_model,
)
from fenolite.dsl.convert import key_id
from fenolite.model.design import Design as ModelDesign


def nets(*names: str) -> list[Net]:
    return [Net(name) for name in names]


def part(ref: str) -> Part:
    return Part(ref, "Mini:Mini_QFP32_IC")


def members(model: ModelDesign, net: str) -> set[tuple[str, str]]:
    refs = {c.id: c.ref for c in model.circuit.components}
    found = next(n for n in model.circuit.nets if n.name == net)
    return {(refs[m.component_id], m.pin) for m in found.members}


# -- the four classes


def test_i2c_in_the_model() -> None:
    d = Design("t")
    sda, scl = nets("SDA", "SCL")
    d.add(I2C(sda, scl))
    (itf,) = to_model(d).circuit.interfaces
    assert (itf.name, itf.kind) == ("SDA/SCL", "i2c")
    assert itf.members == {"sda": key_id("net", "SDA"), "scl": key_id("net", "SCL")}
    assert itf.id == key_id("interface", "i2c", "SDA/SCL") and set(d.nets) == {"SDA", "SCL"}


def test_spi_chip_selects() -> None:
    d = Design("t")
    sck, mosi, miso, cs_flash, cs_adc = nets("SCK", "MOSI", "MISO", "CS_FLASH", "CS_ADC")
    d.add(SPI(sck, mosi, miso, cs=(cs_flash, cs_adc)))
    (itf,) = to_model(d).circuit.interfaces
    assert (itf.name, itf.kind) == ("SCK/MOSI", "spi")
    assert set(itf.members) == {"sck", "mosi", "miso", "cs0", "cs1"}
    assert (itf.members["cs0"], itf.members["cs1"]) == (key_id("net", "CS_FLASH"), key_id("net", "CS_ADC"))


def test_uart_usb2_and_names() -> None:
    d = Design("t")
    tx, rx, dp, dn, vbus, gnd = nets("A_TX", "A_RX", "USB_P", "USB_N", "VBUS", "GND")
    d.add(UART(tx, rx, name="console"), USB2(dp, dn, vbus=vbus, gnd=gnd), Power(vbus, gnd))
    found = {i.name: i for i in to_model(d).circuit.interfaces}
    assert found["console"].kind == "uart" and set(found["console"].members) == {"tx", "rx"}
    assert found["USB_P/USB_N"].kind == "usb2"
    assert set(found["USB_P/USB_N"].members) == {"dp", "dn", "vbus", "gnd"}
    assert set(to_model(Design("u")).circuit.interfaces) == set()
    assert set(USB2(*nets("P", "N")).members) == {"dp", "dn"}


@pytest.mark.parametrize(
    "call",
    [
        lambda a, b: USB2(a, a),
        lambda a, b: I2C(a, Net(a.name)),
        lambda a, b: SPI(a, b, a),
        lambda a, b: SPI(a, b, Net("C"), cs=(a,)),
        lambda a, b: SPI(a, b, Net("C"), cs=Net("D")),  # type: ignore[arg-type]
        lambda a, b: UART(a, "B"),  # type: ignore[arg-type]
        lambda a, b: USB2(a, b, vbus="V"),  # type: ignore[arg-type]
    ],
)
def test_refused_interfaces(call: object) -> None:
    with pytest.raises(DslError):
        call(Net("A"), Net("B"))  # type: ignore[operator]


def test_one_net_twice_names_the_net() -> None:
    dp = Net("USB_P")
    with pytest.raises(DslError, match="USB_P"):
        USB2(dp, dp)


def test_exports_and_base() -> None:
    assert all(name in dsl.__all__ for name in ("I2C", "SPI", "UART", "USB2"))
    assert all(issubclass(cls, Interface) for cls in (I2C, SPI, UART, USB2))


# -- attach


def test_i2c_attach_by_handle_and_designator() -> None:
    d, u1 = Design("t"), part("U1")
    d.add(u1)
    bus = I2C(*nets("SDA", "SCL"))
    d.add(bus)
    bus.attach(u1, sda=u1["PB7"], scl=6)
    model = to_model(d)
    assert members(model, "SDA") == {("U1", "PB7")} and members(model, "SCL") == {("U1", "6")}


def test_uart_crossed_for_the_second_device() -> None:
    d, u1, u2 = Design("t"), part("U1"), part("U2")
    d.add(u1, u2)
    uart = UART(*nets("A_TX", "A_RX"))
    d.add(uart)
    uart.attach(u1, side="a", tx=u1["TX"], rx=u1["RX"])
    uart.attach(u2, side="b", tx=u2["TX"], rx=u2["RX"])
    model = to_model(d)
    assert members(model, "A_TX") == {("U1", "TX"), ("U2", "RX")}
    assert members(model, "A_RX") == {("U1", "RX"), ("U2", "TX")}
    with pytest.raises(DslError, match="side"):
        uart.attach(u1, side="c", tx="TX", rx="RX")


def test_spi_peripheral_on_its_chip_select() -> None:
    d, u1, u3 = Design("t"), part("U1"), part("U3")
    d.add(u1, u3)
    sck, mosi, miso, cs_flash, cs_adc = nets("SCK", "MOSI", "MISO", "CS_FLASH", "CS_ADC")
    spi = SPI(sck, mosi, miso, cs=(cs_flash, cs_adc))
    d.add(spi)
    spi.attach(u1, role="controller", sck="SCK", mosi="MOSI", miso="MISO", cs=(u1["CS0"], u1["CS1"]))
    spi.attach(u3, role="peripheral", sck="SCK", mosi="SDI", miso="SDO", cs=u3["CS"], cs_index=1)
    model = to_model(d)
    assert members(model, "CS_ADC") == {("U1", "CS1"), ("U3", "CS")}
    assert members(model, "CS_FLASH") == {("U1", "CS0")}
    assert members(model, "MOSI") == {("U1", "MOSI"), ("U3", "SDI")}


@pytest.mark.parametrize(
    "kwargs",
    [
        {"role": "controller", "cs": ("CS0",)},
        {"role": "controller", "cs": "CS0"},
        {"role": "controller", "cs": ("CS0", "CS1"), "cs_index": 0},
        {"role": "controller"},
        {"role": "peripheral", "cs": "CS"},
        {"role": "peripheral", "cs": ("CS",), "cs_index": 0},
        {"role": "peripheral", "cs": "CS", "cs_index": 2},
        {"role": "peripheral", "cs_index": 0},
        {"role": "master", "cs": "CS", "cs_index": 0},
    ],
)
def test_spi_attach_refusals(kwargs: dict[str, object]) -> None:
    u1 = part("U1")
    spi = SPI(*nets("SCK", "MOSI", "MISO"), cs=nets("CS_A", "CS_B"))
    with pytest.raises(DslError):
        spi.attach(u1, sck="SCK", mosi="MOSI", miso="MISO", **kwargs)  # type: ignore[arg-type]
    assert u1.connections == {}


def test_pin_of_another_part_connects_nothing() -> None:
    u1, u2 = part("U1"), part("U2")
    bus = I2C(*nets("SDA", "SCL"))
    with pytest.raises(DslError, match="U2"):
        bus.attach(u1, scl=u1["SCL"], sda=u2["SDA"])
    assert u1.connections == {} and u2.connections == {}


def test_attach_keeps_the_rules_of_connect() -> None:
    u1 = part("U1")
    bus = I2C(*nets("SDA", "SCL"))
    dsl.connect(Net("OTHER"), u1["SCL"])
    with pytest.raises(DslError, match="already on net OTHER"):
        bus.attach(u1, sda="SDA", scl="SCL")
    no_connect(u1["NC"])
    with pytest.raises(DslError, match="not connected"):
        bus.attach(u1, sda="SDA2", scl="NC")
    with pytest.raises(DslError, match="two nets"):
        bus.attach(u1, sda="X", scl="X")
    assert set(u1.connections) == {"SCL"}
    with pytest.raises(DslError, match="Part"):
        bus.attach("U1", sda="SDA", scl="SCL")  # type: ignore[arg-type]


def test_usb2_role_without_a_net() -> None:
    u1 = part("U1")
    usb = USB2(*nets("USB_P", "USB_N"), gnd=Net("GND"))
    with pytest.raises(DslError, match="vbus"):
        usb.attach(u1, dp="DP", dn="DM", vbus="VBUS")
    assert u1.connections == {}
    usb.attach(u1, dp="DP", dn="DM", gnd="GND")
    assert {d: n.name for d, n in u1.connections.items()} == {"DP": "USB_P", "DM": "USB_N", "GND": "GND"}
