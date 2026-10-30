# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Block ports and port nets: binding, naming, refusals, interface ports and net-like handles (capability
design-dsl, "Connections and pin designators", "Block ports in the DSL" and "Net-like ports"; change
c0251)."""

from __future__ import annotations

from typing import Any

import pytest

from fenolite.dsl import I2C, SPI, Design, DslError, Harness, Net, block, connect, decouple, to_model
from fenolite.dsl.portnets import PortNet

R = "Fenolite:Resistor"
C = "Fenolite:Capacitor"
FP = "Fenolite:Chip_0603"


@block
def channel(b: Any) -> None:
    vin = b.port("VIN")
    en = b.port("EN", optional=True)
    r = b.part("R_EN", R, footprint=FP)
    connect(vin, r[2])
    connect(en, r[1])


@block
def stage(b: Any) -> None:
    vout = b.port("VOUT", direction="out")
    vin = b.port("VIN", direction="in")
    r = b.part("R", R, footprint=FP)
    connect(vin, r[1])
    connect(vout, r[2])


def nets(design: Design) -> dict[str, set[tuple[str, str]]]:
    model = to_model(design)
    paths = {c.id: c.properties["fenolite.path"] for c in model.circuit.components}
    return {n.name: {(paths[m.component_id], m.pin) for m in n.members} for n in model.circuit.nets}


def test_nets_port_net_takes_the_outside_name() -> None:
    design = Design("t")
    ch0 = design.use(channel, "ch0")
    connect(Net("VIN48"), ch0.VIN)
    found = nets(design)
    assert ("ch0/R_EN", "2") in found["VIN48"] and "ch0/VIN" not in found


def test_nets_unnamed_group_named_by_its_source_port() -> None:
    for order in (("buck1", "buck2"), ("buck2", "buck1")):
        design = Design("t")
        made = {name: design.use(stage, name) for name in order}
        connect(made["buck1"].VOUT, made["buck2"].VIN)
        found = nets(design)
        assert found["buck1/VOUT"] == {("buck1/R", "2"), ("buck2/R", "1")}
        assert "buck2/VIN" not in found


def test_nets_two_named_nets_through_a_port() -> None:
    design = Design("t")
    ch0 = design.use(channel, "ch0")
    connect(Net("A"), ch0.VIN)
    with pytest.raises(DslError, match=r"(A.*B|B.*A).*ch0/VIN"):
        connect(Net("B"), ch0.VIN)


def test_nets_unwired_inner_port_is_named_by_its_path() -> None:
    design = Design("t")
    design.use(channel, "ch0")
    found = nets(design)
    assert found["ch0/VIN"] == {("ch0/R_EN", "2")} and found["ch0/EN"] == {("ch0/R_EN", "1")}


def test_nets_rename_on_a_later_connect() -> None:
    design = Design("t")
    ch0 = design.use(channel, "ch0")
    assert "ch0/VIN" in nets(design)
    connect(Net("VIN48"), ch0.VIN)
    found = nets(design)
    assert "VIN48" in found and "ch0/VIN" not in found


def test_nets_pin_on_two_groups_refused() -> None:
    design = Design("t")
    ch0 = design.use(channel, "ch0")
    with pytest.raises(DslError, match=r"R_EN.*2.*already on net"):
        connect(Net("X"), ch0.part("R_EN")[2])
    connect(ch0.VIN, ch0.part("R_EN")[2])  # the same group keeps one membership


def test_nets_connection_helpers_take_port_nets() -> None:
    @block
    def decoupled(b: Any) -> None:
        vin = b.port("VIN", direction="in")
        gnd = b.port("GND", direction="in")
        c = b.part("C1", C, footprint=FP)
        decouple(vin.net, gnd.net, c)

    design = Design("t")
    inst = design.use(decoupled, "u1")
    connect(Net("3V3"), inst.VIN)
    connect(Net("GND"), inst.GND)
    found = nets(design)
    assert found["3V3"] == {("u1/C1", "1")} and found["GND"] == {("u1/C1", "2")}


def test_interface_port() -> None:
    @block
    def sensor(b: Any) -> None:
        bus = b.port("I2C", I2C)
        u = b.part("U", "Fenolite:Resistor", footprint=FP)
        connect(bus.sda, u[1])
        connect(bus["scl"], u[2])

    design = Design("t")
    sen = design.use(sensor, "sen")
    sda, scl = Net("SDA"), Net("SCL")
    connect(sda, sen.I2C.sda)
    connect(scl, sen.I2C.scl)
    model = to_model(design)
    by_name = {n.name: n for n in model.circuit.nets}
    (port,) = model.circuit.ports
    assert (port.name, port.kind, port.direction) == ("I2C", "i2c", "inout")
    assert port.members == {"sda": by_name["SDA"].id, "scl": by_name["SCL"].id}
    assert len(by_name["SDA"].members) == 1 and len(by_name["SCL"].members) == 1


def test_interface_port_is_not_net_like() -> None:
    @block
    def sensor(b: Any) -> None:
        b.port("I2C", I2C)

    inst = Design("t").use(sensor, "sen")
    with pytest.raises(DslError, match=r"members sda, scl"):
        connect(Net("X"), inst.I2C)
    with pytest.raises(DslError, match="no member 'mosi'"):
        _ = inst.I2C.mosi


def test_harness_and_spi_members() -> None:
    @block
    def ports(b: Any) -> None:
        h = b.port("H", Harness, members=("a", "b"))
        s = b.port("S", SPI, selects=2)
        assert tuple(h.members) == ("a", "b")
        assert tuple(s.members) == ("sck", "mosi", "miso", "cs0", "cs1")
        with pytest.raises(DslError, match="members"):
            b.port("H2", Harness)
        with pytest.raises(DslError, match="selects belongs"):
            b.port("X", I2C, selects=1)

    Design("t").use(ports, "p")


def test_bad_direction() -> None:
    @block
    def bad(b: Any) -> None:
        b.port("EN", direction="both")

    with pytest.raises(DslError, match="both"):
        Design("t").use(bad, "u1")


def test_bad_kind() -> None:
    @block
    def bad(b: Any) -> None:
        b.port("EN", int)

    with pytest.raises(DslError, match="kind is Net"):
        Design("t").use(bad, "u1")


def test_port_as_a_net() -> None:
    @block
    def chan(b: Any) -> None:
        en = b.port("EN")
        r = b.part("R_EN", R, footprint=FP)
        connect(en, r[1])

    design = Design("t")
    ch0 = design.use(chan, "ch0")
    connect(Net("CH0_EN"), ch0.EN)
    assert nets(design)["CH0_EN"] == {("ch0/R_EN", "1")}
    assert isinstance(ch0.EN.net, PortNet) and ch0.EN["net"] is ch0.EN.net


def test_shadowing_name_refused() -> None:
    @block
    def shadow(b: Any) -> None:
        b.port("path")

    with pytest.raises(DslError, match="path"):
        Design("t").use(shadow, "u1")


def test_nested_port_through_a_port() -> None:
    @block
    def outer(b: Any) -> None:
        vin = b.port("VIN", direction="in")
        inner = b.use(stage, "s")
        connect(vin, inner.VIN)

    design = Design("t")
    o = design.use(outer, "o")
    connect(Net("VIN"), o.VIN)
    found = nets(design)
    assert found["VIN"] == {("o/s/R", "1")} and found["o/s/VOUT"] == {("o/s/R", "2")}
