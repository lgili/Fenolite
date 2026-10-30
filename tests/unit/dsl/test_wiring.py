# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Connection helpers of the DSL (capability design-dsl, "Named ends of two-pin parts", "Series chains in
the DSL", "Decoupling in the DSL", "Pull resistors in the DSL", "Unused pins marked in the DSL"; change
c0247): what each helper lowers to in ``to_model`` and what it refuses at the call."""

from __future__ import annotations

import subprocess
import sys

import pytest

from fenolite.dsl import (
    I2C,
    SPI,
    Design,
    DslError,
    Net,
    Part,
    connect,
    decouple,
    mm,
    no_connect,
    ohm,
    pull_down,
    pull_up,
    series,
    to_model,
)
from fenolite.dsl.convert import key_id, two_terminal, unused_marks
from fenolite.model.circuit import PinRef
from fenolite.model.rules import PadSelection, ProximityRule


def _members(design: Design) -> dict[str, tuple[PinRef, ...]]:
    """Net name → members, in ``PinRef`` order (the tests list them sorted too)."""
    return {net.name: tuple(sorted(net.members)) for net in to_model(design).circuit.nets}


def _pin(ref: str, pin: str) -> PinRef:
    return PinRef(key_id("component", ref), pin)


def _design(*refs: str) -> tuple[Design, list[Part]]:
    design = Design("t")
    design.board(mm(50), mm(30))
    parts = [Part(ref, "Mini:Mini_QFP32_IC" if ref.startswith("U") else "Mini:Mini_R") for ref in refs]
    design.add(*parts)
    return design, parts


# -- ends


def test_ends_are_pins_one_and_two() -> None:
    design, (r1,) = _design("R1")
    assert not r1.two_terminal
    connect(Net("A"), r1.a)
    connect(Net("B"), r1.b)
    assert _members(design) == {"A": (_pin("R1", "1"),), "B": (_pin("R1", "2"),)}
    assert r1.two_terminal and two_terminal(design) == ("R1",)


def test_ends_of_an_unused_part_leave_it_unchecked() -> None:
    design, (r1, r2) = _design("R1", "R2")
    connect(Net("A"), r1[1], r2.a)
    assert two_terminal(design) == ("R2",)


# -- series


def test_series_fuse_and_diode() -> None:
    design, (f1, d1) = _design("F1", "D1")
    vin, vprot = Net("VIN"), Net("VPROT")
    made = series(vin, f1, d1, vprot)
    assert [net.name for net in made] == ["F1-D1"]
    assert _members(design) == {
        "F1-D1": tuple(sorted((_pin("D1", "1"), _pin("F1", "2")))),
        "VIN": (_pin("F1", "1"),),
        "VPROT": (_pin("D1", "2"),),
    }
    assert two_terminal(design) == ("D1", "F1")


def test_series_part_turned_around_and_named_joint() -> None:
    design, (r1, d1) = _design("R1", "D1")
    led_drv, led_a, gnd = Net("LED_DRV"), Net("LED_A"), Net("GND")
    assert series(led_drv, r1, led_a, (d1.b, d1.a), gnd) == ()
    members = _members(design)
    assert members["LED_A"] == tuple(sorted((_pin("D1", "2"), _pin("R1", "2"))))
    assert members["GND"] == (_pin("D1", "1"),)
    assert members["LED_DRV"] == (_pin("R1", "1"),)


def test_series_joint_names_take_module_paths() -> None:
    from fenolite.dsl import Module

    design = Design("t")
    psu = Module("psu")
    f1, d1 = Part("F1", "Mini:Mini_R"), Part("D1", "Mini:Mini_R")
    psu.add(f1, d1)
    design.add(psu)
    (joint,) = series(Net("VIN"), f1, d1, Net("VOUT"))
    assert joint.name == "psu/F1-psu/D1"


def test_series_refused_chains() -> None:
    design, (f1, d1) = _design("F1", "D1")
    vin, vout, a, b = Net("VIN"), Net("VOUT"), Net("A"), Net("B")
    for call in (
        lambda: series(f1, vin),
        lambda: series(vin, vout),
        lambda: series(vin, f1, a, b, d1, vout),
        lambda: series(vin, (f1.a, d1.b), vout),
        lambda: series(vin, "F1", vout),
        lambda: series(vin, (f1[1], f1[1]), vout),
        lambda: series(vin, ohm("10k"), vout),
    ):
        with pytest.raises(DslError):
            call()
    assert f1.connections == {} and d1.connections == {} and design.nets == {}


def test_series_generated_name_taken() -> None:
    design, (f1, d1, r1) = _design("F1", "D1", "R1")
    connect(Net("F1-D1"), r1[1])
    with pytest.raises(DslError, match="two distinct nets are named 'F1-D1'"):
        series(Net("VIN"), f1, d1, Net("VOUT"))
    assert f1.connections == {} and d1.connections == {}


def test_series_pin_on_another_net_connects_nothing() -> None:
    _design_, (f1, d1) = _design("F1", "D1")
    connect(Net("X"), d1[2])
    with pytest.raises(DslError, match="D1 2 is already on net X"):
        series(Net("VIN"), f1, d1, Net("VOUT"))
    assert f1.connections == {} and not f1.two_terminal


# -- decouple


def test_decouple_rule_recorded() -> None:
    design, (u1, c1) = _design("U1", "C1")
    vin, gnd = Net("VIN"), Net("GND")
    decouple(vin, gnd, c1, near=u1.pad(9), within=mm(3))
    model = to_model(design)
    members = {net.name: net.members for net in model.circuit.nets}
    assert members == {"GND": (_pin("C1", "2"),), "VIN": (_pin("C1", "1"),)}
    assert model.rules is not None
    assert model.rules.proximity == (
        ProximityRule("decouple/C1", (PadSelection("C1"),), (PadSelection("U1", "9"),), 3_000_000),
    )
    assert c1.two_terminal


def test_decouple_without_a_rule() -> None:
    design, (c1, c2) = _design("C1", "C2")
    decouple(Net("VIN"), Net("GND"), c1, c2)
    model = to_model(design)
    assert {net.name: len(net.members) for net in model.circuit.nets} == {"GND": 2, "VIN": 2}
    assert model.rules is None or model.rules.proximity == ()


def test_decouple_refused() -> None:
    design, (u1, c1) = _design("U1", "C1")
    vin, gnd = Net("VIN"), Net("GND")
    for call in (
        lambda: decouple(vin, gnd),
        lambda: decouple(vin, gnd, c1, near=u1.pad(9)),
        lambda: decouple(vin, vin, c1),
        lambda: decouple(vin, gnd, c1, near=u1.pad(9), within=mm(0)),
    ):
        with pytest.raises(DslError):
            call()
    with pytest.raises(DslError, match=r"part\.pad\(<number>\)"):
        decouple(vin, gnd, c1, near=u1[9], within=mm(3))
    assert c1.connections == {} and design.near_rules == {}


def test_decouple_a_part_in_no_design() -> None:
    _design_, (u1,) = _design("U1")
    c9 = Part("C9", "Mini:Mini_R")
    with pytest.raises(DslError, match="add C9 to a design"):
        decouple(Net("VIN"), Net("GND"), c9, near=u1.pad(9), within=mm(3))
    decouple(Net("VIN"), Net("GND"), c9)  # without a rule, a part need not be in a design yet
    assert set(c9.connections) == {"1", "2"}


def test_decouple_rule_refused_after_a_good_one_records_nothing() -> None:
    design, (u1, c1, c2) = _design("U1", "C1", "C2")
    design.near("decouple/C2", c2, u1, within=mm(1))
    with pytest.raises(DslError, match="declared twice"):
        decouple(Net("VIN"), Net("GND"), c1, c2, near=u1.pad(9), within=mm(3))
    assert list(design.near_rules) == ["decouple/C2"] and c1.connections == {}


# -- pull resistors


def test_i2c_pull_ups() -> None:
    design, (r3, r4) = _design("R3", "R4")
    sda, scl, v33 = Net("SDA"), Net("SCL"), Net("3V3")
    pull_up(I2C(sda, scl), v33, r3, r4)
    assert _members(design) == {
        "3V3": tuple(sorted((_pin("R3", "2"), _pin("R4", "2")))),
        "SCL": (_pin("R4", "1"),),
        "SDA": (_pin("R3", "1"),),
    }


def test_a_pull_down_on_one_net() -> None:
    design, (r5,) = _design("R5")
    pull_down(Net("EN"), Net("GND"), r5)
    assert _members(design) == {"EN": (_pin("R5", "1"),), "GND": (_pin("R5", "2"),)}


def test_refused_pull_resistors() -> None:
    _design_, (r3, r4, r5) = _design("R3", "R4", "R5")
    sda, scl, v33 = Net("SDA"), Net("SCL"), Net("3V3")
    bus = I2C(sda, scl)
    with pytest.raises(DslError, match="2 resistor"):
        pull_up(bus, v33, r3)
    with pytest.raises(DslError, match="3V3 is the rail"):
        pull_up(v33, v33, r3)
    with pytest.raises(DslError, match="spi"):
        pull_up(SPI(Net("SCK"), Net("MOSI"), Net("MISO")), v33, r3, r4, r5)  # pyright: ignore[reportArgumentType]
    with pytest.raises(DslError, match="a value does not choose a part"):
        pull_up(sda, v33, ohm("4k7"))  # pyright: ignore[reportArgumentType]
    with pytest.raises(DslError):
        pull_down("EN", v33, r3)  # pyright: ignore[reportArgumentType]
    assert all(not part.connections for part in (r3, r4, r5))


# -- unused pins


def test_unused_request_recorded_model_unchanged() -> None:
    design, (u1,) = _design("U1")
    connect(Net("VIN"), u1[9])
    u1.unused_no_connect()
    assert to_model(design).circuit.no_connects == ()
    assert unused_marks(design) == {"U1": ()}


def test_unused_keep_as_written_in_order() -> None:
    design, (u1, u2) = _design("U1", "U2")
    u2.unused_no_connect(keep=(9, "PA7", "10"))
    assert unused_marks(design) == {"U2": ("10", "9", "PA7")}
    assert u1.unused_request is None


def test_unused_called_twice() -> None:
    _design_, (u1,) = _design("U1")
    u1.unused_no_connect()
    with pytest.raises(DslError, match="U1"):
        u1.unused_no_connect()


def test_unused_refused_keep() -> None:
    _design_, (u1,) = _design("U1")
    for keep in ("PA7", 5, (True,), ("",), (1.5,)):
        with pytest.raises(DslError):
            u1.unused_no_connect(keep=keep)  # pyright: ignore[reportArgumentType]
    assert u1.unused_request is None


def test_unused_then_connect_and_mark_stay_allowed() -> None:
    design, (u1,) = _design("U1")
    u1.unused_no_connect()
    connect(Net("VIN"), u1[9])
    no_connect(u1[11])
    assert to_model(design).circuit.no_connects == (_pin("U1", "11"),)


# -- re-exports


def test_reexport() -> None:
    code = "from fenolite.dsl import series, decouple, pull_up, pull_down; print(series.__module__)"
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=True)
    assert out.stdout.strip() == "fenolite.dsl.wiring"
