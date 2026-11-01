# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Rails, grounds, logic lines and interface parameters (capability design-dsl, "Rail interface" to "Interface
companions"; change c0252)."""

from __future__ import annotations

from typing import Any

import pytest

from fenolite.dsl import (
    I2C,
    Design,
    DslError,
    Ground,
    Logic,
    Net,
    Power,
    Rail,
    amp,
    between,
    block,
    ohm,
    pull_up,
    to_model,
    volt,
)
from fenolite.dsl.convert import key_id
from fenolite.dsl.interfaces import PARAMETERS
from fenolite.model import canonical
from fenolite.model.circuit import Decimal10


def _interface(design: Design, name: str) -> Any:
    return next(i for i in to_model(design).circuit.interfaces if i.name == name)


def test_power_is_rail() -> None:
    """Scenario "Power is Rail": same model texts, same class."""
    texts = []
    for cls in (Power, Rail):
        d = Design("t")
        d.add(cls(Net("VIN"), Net("GND")))
        texts.append(canonical.dump_texts(to_model(d)))
    assert texts[0] == texts[1] and Power is Rail
    assert Rail(Net("VIN")).name == "VIN" and set(Rail(Net("VIN")).members) == {"hv"}


def test_rail_with_a_voltage() -> None:
    d = Design("t")
    d.add(Rail(Net("3V3"), Net("GND"), voltage=volt("3.3").pct(3)))
    voltage = _interface(d, "3V3/GND").params["voltage"]
    assert (
        voltage.unit == "volt" and voltage.low == Decimal10(3201, -3) and voltage.high == Decimal10(3399, -3)
    )


def test_rail_wrong_unit_refused() -> None:
    with pytest.raises(DslError, match=r"voltage.*volt.*ampere"):
        Rail(Net("3V3"), voltage=amp(1))


def test_rail_current_on_a_design_rail_refused() -> None:
    with pytest.raises(DslError, match=r"current is set on ports only"):
        Rail(Net("3V3"), current=amp(1))


def test_rail_logic_with_a_reference_rail() -> None:
    d = Design("t")
    rail = Rail(Net("1V8"))
    d.add(Logic(Net("IRQ"), reference=rail))
    irq = _interface(d, "IRQ")
    assert irq.kind == "logic" and irq.reference == key_id("interface", "power", "1V8")
    assert irq.members == {"io": key_id("net", "IRQ")}
    with pytest.raises(DslError, match="reference"):
        Logic(Net("IRQ"), reference=Ground(Net("GND")))


def test_rail_in_one_call() -> None:
    d = Design("t")
    gnd = d.ground("GND")
    d.rail("V12", voltage=volt("12").pct(10), ground=gnd)
    model = to_model(d)
    assert {n.name for n in model.circuit.nets} == {"GND", "V12"}
    kinds = {i.name: i.kind for i in model.circuit.interfaces}
    assert kinds == {"GND": "ground", "V12/GND": "power"}
    assert "voltage" in _interface(d, "V12/GND").params
    with pytest.raises(DslError, match="already has a net"):
        d.rail("V12")


def test_reference_i2c_with_a_pullup_range() -> None:
    """Scenario "I2C with a reference and a pull-up range"."""
    d = Design("t")
    v33 = d.rail("3V3")
    d.add(I2C(Net("SDA"), Net("SCL"), reference=v33, pullup=between(ohm("2k"), ohm("10k"))))
    bus = _interface(d, "SDA/SCL")
    assert bus.reference == key_id("interface", "power", "3V3")
    assert (bus.params["pullup"].low, bus.params["pullup"].high) == (Decimal10(2, 3), Decimal10(1, 4))


@block
def buck(b: Any, *, vout: Any = None, current: Any = None) -> None:
    out = b.port("VOUT", Rail, direction="out")
    out.set(voltage=vout, current=current)
    b.port("GND", Ground)


def test_port_source_of_a_block() -> None:
    """Scenario "Source port of a block"."""
    d = Design("t")
    d.use(buck, "buck1", vout=volt("3.3").pct(3), current=amp(1))
    port = next(p for p in to_model(d).circuit.ports if p.name == "VOUT")
    assert port.params["current"].low == port.params["current"].high == Decimal10(1, 0)
    assert port.params["voltage"].low == Decimal10(3201, -3)


def test_port_current_on_a_pass_through_port_refused() -> None:
    @block
    def jumper(b: Any) -> None:
        b.port("VBUS", Rail, current=amp(1))

    with pytest.raises(DslError, match=r'VBUS.*current.*direction="in" or direction="out"'):
        Design("t").use(jumper, "j")


def test_threshold_logic_on_a_block_port() -> None:
    """Scenario "Logic thresholds on a block port"."""
    seen: list[Any] = []

    @block
    def sensor(b: Any) -> None:
        port = b.port("INT", Logic, direction="out", output_high_min=volt("2.4"), output_low_max=volt("0.4"))
        seen.append(port)

    d = Design("t")
    d.use(sensor, "s")
    port = next(p for p in to_model(d).circuit.ports if p.name == "INT")
    assert set(port.params) == {"output_high_min", "output_low_max"}
    assert port.params["output_low_max"].high == Decimal10(4, -1)
    with pytest.raises(DslError, match="input_high_min"):
        seen[0].set(input_high_min=volt("2"))
    with pytest.raises(DslError, match="set twice"):
        seen[0].set(output_low_max=volt("0.3"))


def test_parameter_table() -> None:
    assert PARAMETERS["power"]["voltage"].semantics == "alias"
    assert PARAMETERS["power"]["current"].semantics == "sum"
    assert PARAMETERS["power"]["current"].where == {"in", "out"}
    assert PARAMETERS["i2c"]["pullup"].unit == "ohm"
    assert PARAMETERS["logic"]["reference"].semantics == "link"
    assert PARAMETERS["ground"] == {}


def test_requires_a_sensor_port_that_needs_pullups() -> None:
    """Scenario "A sensor port that needs pull-ups"."""

    @block
    def sensor(b: Any, *, bad: bool = False) -> None:
        vdd = b.port("VDD", Rail, direction="in")
        b.port("I2C", I2C, requires=("chip_select",) if bad else ("supply", "pullup"), reference=vdd)

    d = Design("t")
    d.use(sensor, "s")
    port = next(p for p in to_model(d).circuit.ports if p.name == "I2C")
    assert port.requires == ("pullup", "supply") and port.reference == key_id("port", "s", "VDD")
    with pytest.raises(DslError, match=r"chip_select.*i2c"):
        Design("t").use(sensor, "s", bad=True)


def test_pull_up_on_a_logic_line() -> None:
    d = Design("t")
    v33 = d.rail("3V3")
    r = d.part("R1", "Fenolite:Resistor", footprint="Fenolite:Chip_0603", value="10k")
    irq = Logic(Net("IRQ"))
    d.add(irq)
    pull_up(irq, v33, r)
    nets = {n.name: {m.pin for m in n.members} for n in to_model(d).circuit.nets}
    assert nets["IRQ"] == {"1"} and nets["3V3"] == {"2"}
    with pytest.raises(DslError, match="1 resistor"):
        pull_up(irq, v33, r, r)
