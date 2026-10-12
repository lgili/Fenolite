# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Tolerant texts and nets of a read circuit (c0160 task 4.2)."""

from __future__ import annotations

import dataclasses

import pytest
from _convert import two_layer

from fenolite.backends.altium import lower, project
from fenolite.backends.altium.read.sch import read_schematic
from fenolite.model.circuit import Net, PinRef


def test_binary_unicode_comment_and_ascii_refusal() -> None:
    design = two_layer()
    first = dataclasses.replace(design.circuit.components[0], value="1 kΩ 世界")
    circuit = dataclasses.replace(design.circuit, components=(first, *design.circuit.components[1:]))
    design = dataclasses.replace(design, circuit=circuit)
    written = lower.write_design(design, allow_lossy=True)
    data = written.files[f"{written.inputs.name}.SchDoc"]
    assert b"|%UTF8%TEXT=" + first.value.encode() in data
    assert b"|TEXT=1 k? ??" in data
    assert any(r.props.text("TEXT") == first.value for r in read_schematic(data).records)
    with pytest.raises(ValueError):
        project.write_project(
            written.inputs.schematic, name=written.inputs.name, form="ascii", read_circuit=True
        )
    # A new script still gets the existing validation contract.
    with pytest.raises(ValueError):
        project.write_project(written.inputs.schematic, name=written.inputs.name, form="binary")


def test_altium_parameter_reference_is_retained() -> None:
    design = two_layer()
    first = dataclasses.replace(
        design.circuit.components[0], value="=PartValue", properties={"PartValue": "1k"}
    )
    circuit = dataclasses.replace(design.circuit, components=(first, *design.circuit.components[1:]))
    written = lower.write_design(dataclasses.replace(design, circuit=circuit), allow_lossy=True)
    data = written.files[f"{written.inputs.name}.SchDoc"]
    assert b"|TEXT==PartValue" in data
    assert any(r.props.text("TEXT") == "=PartValue" for r in read_schematic(data).records)


@pytest.mark.parametrize("tie", (False, True))
def test_pin_uses_largest_net_then_name(tie: bool) -> None:
    design = two_layer()
    first, second = design.circuit.components[:2]
    shared = PinRef(first.id, first.pins[0].number)
    other = PinRef(first.id, first.pins[1].number)
    third = PinRef(second.id, second.pins[0].number)
    small = Net(id="net-small", name="A", members=(shared, third) if tie else (shared,))
    large = Net(id="net-large", name="Z", members=(shared, other))
    circuit = dataclasses.replace(design.circuit, nets=(large, small))
    inputs = lower.from_design(dataclasses.replace(design, circuit=circuit), issues=[])
    winner = "A" if tie else "Z"
    assert [n.name for n in inputs.schematic.circuit.nets if shared in n.members] == [winner]
    assert sum(len(ids) for ids in inputs.lost["pin-net"].values()) == 1
    with pytest.raises(lower.LossyWriteError):
        lower.write_design(dataclasses.replace(design, circuit=circuit))


def test_empty_imported_comment_stays_empty() -> None:
    design = two_layer()
    first = dataclasses.replace(design.circuit.components[0], value="")
    design = dataclasses.replace(
        design,
        circuit=dataclasses.replace(design.circuit, components=(first, *design.circuit.components[1:])),
    )
    written = lower.write_design(design, allow_lossy=True)
    assert written.inputs.schematic.circuit.components[0].value == ""
    assert (
        next(
            p
            for p in project.part_specs(written.inputs.schematic, form="binary", read_circuit=True)
            if p.ref == first.ref
        ).comment
        == ""
    )


def test_membership_of_absent_pin_is_reported() -> None:
    design = two_layer()
    first = design.circuit.components[0]
    net = Net(id="net-absent", name="ABSENT", members=(PinRef(first.id, "999"),))
    design = dataclasses.replace(design, circuit=dataclasses.replace(design.circuit, nets=(net,)))
    inputs = lower.from_design(design, issues=[])
    assert inputs.schematic.circuit.nets[0].members == ()
    assert tuple(inputs.lost["pin-net"].values()) == ((f"{first.id}:999",),)


def test_colliding_imported_symbols_get_distinct_storage_names() -> None:
    design = two_layer()
    first, second = design.circuit.components[:2]
    parts = (
        dataclasses.replace(first, lib_symbol_ref="public_one:R"),
        dataclasses.replace(second, lib_symbol_ref="public_two:R"),
        *design.circuit.components[2:],
    )
    design = dataclasses.replace(design, circuit=dataclasses.replace(design.circuit, components=parts))
    written = lower.write_design(design, allow_lossy=True)
    assert f"{written.inputs.name}.SchDoc" in written.files
    refs = [c.lib_symbol_ref for c in written.inputs.schematic.circuit.components[:2]]
    assert refs == [f"{written.inputs.name}.SchLib:PART_{c.ref}" for c in parts[:2]]
