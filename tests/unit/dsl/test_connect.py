# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Connections, pin designators and net classes (capability design-dsl; change c0011)."""

from __future__ import annotations

import pytest

from fenolite.dsl import Design, DslError, Net, Part, connect, mm, to_model
from fenolite.model.circuit import PinRef


def two_parts() -> tuple[Design, Part, Part]:
    d, u1, r1 = Design("t"), Part("U1", "Mini:Mini_QFP32_IC"), Part("R1", "Mini:Mini_R")
    d.add(u1, r1)
    return d, u1, r1


def test_integer_and_string_designators() -> None:
    d, u1, _ = two_parts()
    vin = Net("VIN")
    connect(vin, u1[1])
    connect(vin, u1["1"])
    (net,) = to_model(d).circuit.nets
    u1_id = next(c.id for c in to_model(d).circuit.components if c.ref == "U1")
    assert net.name == "VIN" and net.members == (PinRef(u1_id, "1"),)


def test_designator_on_two_nets() -> None:
    _, _, r1 = two_parts()
    connect(Net("A"), r1["1"])
    with pytest.raises(DslError, match=r"R1 1"):
        connect(Net("B"), r1["1"])


def test_net_given_as_a_string() -> None:
    _, _, r1 = two_parts()
    with pytest.raises(DslError):
        connect("GND", r1["2"])  # type: ignore[arg-type]


def test_bad_designators() -> None:
    r1 = Part("R1", "Mini:Mini_R")
    for bad in ("", True, 1.5):
        with pytest.raises(DslError):
            r1[bad]  # type: ignore[index]


def test_designators_as_written() -> None:
    d, u1, _ = two_parts()
    connect(Net("GND"), u1["GND"])
    u1_id = next(c.id for c in to_model(d).circuit.components if c.ref == "U1")
    assert to_model(d).circuit.nets[0].members == (PinRef(u1_id, "GND"),)


def test_net_joins_through_an_added_part() -> None:
    r1 = Part("R1", "Mini:Mini_R")
    connect(Net("LATE"), r1["1"])
    d = Design("t")
    d.add(r1)
    assert "LATE" in d.nets
    connect(Net("NOW"), r1["2"])
    assert "NOW" in d.nets


def test_class_with_members() -> None:
    d, vin, gnd = Design("t"), Net("VIN"), Net("GND")
    d.rules.netclass("PWR", clearance=mm(0.2), track_width=mm(0.5), nets=(vin, gnd))
    model = to_model(d).circuit
    (cls,) = model.netclasses
    assert cls.name == "PWR" and cls.clearance == 200_000 and cls.track_width == 500_000
    assert {n.name: n.netclass_id for n in model.nets} == {"VIN": cls.id, "GND": cls.id}


def test_net_in_two_classes() -> None:
    d, vin = Design("t"), Net("VIN")
    d.rules.netclass("PWR", nets=(vin,))
    with pytest.raises(DslError, match="VIN.*PWR.*SIG"):
        d.rules.netclass("SIG", nets=(vin,))
    with pytest.raises(DslError):
        d.rules.netclass("PWR")
    with pytest.raises(DslError):
        d.rules.netclass("X", clearance=0.2)
